"""output_forms 私有子模块 _index：包级产出清单：渲染/复算/越界判据、逐包校验、机验率计量、基线重签。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List

from core import atomic_write
from core.json_schema import pattern_issue as _pattern_issue

from ._checkers import _check_csv, _check_domain_report, _check_domain_spec, _check_dot, _check_graphml, _check_json, _check_jsonl, _check_markdown, _check_mermaid, _check_quant_metrics, _check_toml, _check_vega_lite, _check_xml, _check_yaml, json_schema_check
from ._const import INDEX_REL, TIERS
from ._gen_b import GENERATORS, _check_combo_cert
from ._registry import _pack_dirs, _read_bytes_cached, _read_json, _read_text_cached, _rel, detect
from ._util import _declared_out_rel, _dump, _gen_id



_FORM_CHECK: Dict[str, Callable[[str, str], List[str]]] = {
    "json": _check_json, "json-schema": _check_json, "vega-lite": _check_vega_lite,
    "vega": _check_json, "jsonl": _check_jsonl, "csv": _check_csv, "xml": _check_xml,
    "markdown": _check_markdown, "toml": _check_toml, "yaml": _check_yaml,
    "mermaid": _check_mermaid, "graphviz-dot": _check_dot, "graphml": _check_graphml,
    "svg": _check_xml, "json-graph-format": _check_json,
    "quant-metrics": _check_quant_metrics, "performance-report": _check_json,
    "concept-closure": _check_json, "system-card": _check_json,
    "domain-spec": _check_domain_spec, "domain-report": _check_domain_report,
    # 惰性引用：_check_combo_cert 定义在本表之后（避免前向引用 NameError）
    "combo-cert": lambda r, x: _check_combo_cert(r, x),
}



def _gen_missing(out_rel: str, entry: dict) -> Tuple[List[str], Dict[str, Any]]:
    return ["%s 声明复算 %r 无对应引擎（不得假装可复算）" % (out_rel, _gen_id(entry))], {}


def _fresh_diffs(fresh: Any, on_disk: bytes) -> Tuple[List[str], str]:
    """复算值与在盘字节的差异清单；不可解析时第二项给问题文本。"""
    if isinstance(fresh, str):
        if on_disk == _dump(fresh).encode("utf-8"):
            return [], ""
        return ["文本面与复算不一致（逐字节）"], ""
    try:
        declared = json.loads(on_disk.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [], "在盘产物不可解析 %s" % exc
    diffs = _deep_diff(fresh, {k: declared.get(k) for k in fresh})
    if b"\r\n" in on_disk:
        diffs.append("在盘产物含 CRLF（仓库 EOL 契约 = LF）")
    return diffs, ""


def _recompute_entry(root: str, entry: dict) -> Tuple[List[str], Dict[str, Any]]:
    """T4 复算：生成器重算 → 与在盘产物比对（JSON 逐字段 / 文本逐字节）。"""
    out_rel = entry["path"]
    gen = GENERATORS.get(_gen_id(entry))
    if gen is None:
        return _gen_missing(out_rel, entry)
    try:
        fresh, errs = gen(root, entry)
    except ValueError as exc:                     # 外来清单里的越界路径 → 复算失败，不读盘
        return ["%s: %s" % (out_rel, exc)], {}
    if fresh is None:
        return ["%s: %s" % (out_rel, e) for e in errs], {}
    try:
        disk_rel = _declared_out_rel(root, str(entry.get("_pkg") or ""), out_rel)
    except ValueError as exc:
        return ["%s: %s" % (out_rel, exc)], {}
    on_disk = _read_bytes_cached(_rel(root, disk_rel))
    diffs, parse_err = _fresh_diffs(fresh, on_disk)
    if parse_err:
        return ["%s: %s" % (out_rel, parse_err)], {}
    return ["%s: 复算与在盘不一致 %s" % (out_rel, d) for d in diffs], {"diff": len(diffs)}



def _write_if_changed(dest: Path, text: str, write: bool, changed: bool) -> bool:
    """按需落盘（LF + 原子写）；返回「本次是否真的写了」。"""
    if not write or not changed:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    # EOL 纪律：仓库 = LF（.gitattributes `* text=auto eol=lf`）；Windows 文本模式
    # 默认会把 \n 写成 \r\n → 必须显式 newline="\n"（check33 编码卫生会判 FAIL）
    # 原子写（2026-09-30 收口）：产出面落点在仓库内，写入期间有人跑 check32/33
    # 会读到半截产物（`atomic_write` 内部同样按 LF 落盘）。
    atomic_write.write_text(dest, text)
    return True


def _render_one(root: str, pkg: str, entry: dict,
                write: bool) -> Tuple[List[str], Dict[str, Any] | None]:
    """渲染单条产出面 → (issues, row|None)。越界/缺生成器只报问题，不写盘。"""
    gid = _gen_id(entry)
    if not gid:
        return [], None
    gen = GENERATORS.get(gid)
    if gen is None:
        return ["%s/%s: 未登记生成器 %r" % (pkg, entry.get("path"), gid)], None
    try:
        value, errs = gen(root, {**entry, "_pkg": pkg})
    except ValueError as exc:                 # 清单里的越界路径 → 问题，不渲染
        return ["%s/%s: %s" % (pkg, entry.get("path"), exc)], None
    if value is None:
        return ["%s/%s: %s" % (pkg, entry.get("path"), e) for e in errs], None
    try:
        dest = _rel(root, _declared_out_rel(root, pkg, entry["path"]))
    except ValueError as exc:                 # 落点越界 → 问题，**不写盘**
        return ["%s/%s: %s" % (pkg, entry.get("path"), exc)], None
    text = _dump(value)
    # 逐字节比对（含 EOL）：产物契约 = LF，故 CRLF 也算「需要重渲染」
    changed = (not dest.is_file()) or dest.read_bytes() != text.encode("utf-8")
    written = _write_if_changed(dest, text, write, changed)
    return [], {"package": pkg, "path": entry["path"], "generator": gid,
                "changed": changed, "written": written}


def render_outputs(root: str = ".", package: str = "", write: bool = False
                   ) -> Tuple[List[str], List[Dict[str, Any]]]:
    """渲染包内声明的产出面（数据 / 图表）：--write 才落盘；缺生成器即报错不静默。"""
    issues: List[str] = []
    rows: List[Dict[str, Any]] = []
    for pkg in _pack_dirs(root):
        if package and pkg != package:
            continue
        idx, err = _read_json(_rel(root, "community/%s/%s" % (pkg, INDEX_REL)))
        if err:
            issues.append("%s: %s" % (pkg, err))
            continue
        for entry in (idx.get("outputs") or []):
            sub, row = _render_one(root, pkg, entry, write)
            issues += sub
            if row is not None:
                rows.append(row)
    return issues, rows



def _dict_diff(a: dict, b: dict, path: str, out: List[str]) -> None:
    for k in sorted(set(a) | set(b)):
        if k not in a:
            out.append("%s.%s 仅存于在盘" % (path, k))
        elif k not in b:
            out.append("%s.%s 仅存于复算" % (path, k))
        else:
            _deep_diff(a[k], b[k], "%s.%s" % (path, k), out)


def _list_diff(a: list, b: list, path: str, out: List[str]) -> None:
    if len(a) != len(b):
        out.append("%s 长度 %d≠%d" % (path, len(a), len(b)))
    for i, (x, y) in enumerate(zip(a, b, strict=False)):  # 长度不等已在上方报出
        _deep_diff(x, y, "%s[%d]" % (path, i), out)


def _num_diff(a: float, b: float, path: str, out: List[str]) -> None:
    if abs(float(a) - float(b)) > 1e-9:
        out.append("%s 数值 %r≠%r" % (path, a, b))


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _deep_diff(a: Any, b: Any, path: str = "$", out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        _dict_diff(a, b, path, out)
    elif isinstance(a, list) and isinstance(b, list):
        _list_diff(a, b, path, out)
    elif _is_number(a) and _is_number(b):
        _num_diff(a, b, path, out)
    elif a != b:
        out.append("%s %r≠%r" % (path, a, b))
    return out




def _dual_key_re(ds: dict):
    """key_pattern → (regex, None) 或 (None, issues)。

    投稿者可写 `key_pattern`——与 schema 的 `pattern` 同一类风险（指数回溯把门禁挂死），
    故复用同一条形态闸门：命中即判 FAIL，**不拿它去 findall**（2026-09-30）。
    """
    key_text = str(ds.get("key_pattern") or r"`([A-Z][A-Z0-9_]{2,})`")
    why = _pattern_issue(key_text, "dual_source.key_pattern")
    if why:
        return None, ["双源 key_pattern 不合形态：%s" % why]
    return re.compile(key_text), None


def _apply_drops(md_keys: set, ds: dict) -> set:
    for drop in (ds.get("exclude") or []):
        md_keys.discard(str(drop))
    return md_keys


def _data_field_keys(data: dict, field: str) -> set:
    """数据面任意列表（metrics / declared_only …）里 `field` 的取值集。"""
    data_keys = set()
    for _key, value in data.items():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and item.get(field):
                data_keys.add(str(item[field]))
    return data_keys


def _dual_diff_issues(md_keys: set, data_keys: set) -> List[str]:
    only_md = sorted(md_keys - data_keys)
    only_data = sorted(data_keys - md_keys)
    out = []
    if only_md:
        out.append("双源不一致：散文面独有键 %s" % only_md[:6])
    if only_data:
        out.append("双源不一致：数据面独有键 %s" % only_data[:6])
    return out


def _dual_source_check(root: str, pkg: str, path: str, ds: dict) -> List[str]:
    """双源一致：数据面 vs 散文面（键集必须互为子集）。"""
    md_rel = ds.get("markdown") or ""
    key_re, key_err = _dual_key_re(ds)
    if key_err is not None:
        return key_err
    try:
        md_full = _declared_out_rel(root, pkg, md_rel)
    except ValueError as exc:
        return [str(exc)]
    md_path = _rel(root, md_full)
    if not md_path.is_file():
        return ["双源对照件不存在：%s" % md_rel]
    md_keys = _apply_drops(set(key_re.findall(_read_text_cached(md_path))), ds)
    data, err = _read_json(_rel(root, path))
    if err:
        return [err]
    data_keys = _data_field_keys(data, ds.get("field") or "id")
    return _dual_diff_issues(md_keys, data_keys)
