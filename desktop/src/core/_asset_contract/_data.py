"""asset_contract 私有子模块 _data：数据面：JSON/CSV/Markdown/YAML/TOML/JSONL/GraphML/Mermaid 判据。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from ._base import _dig, _read, _schema_doc, _strict_json, digest_of, resolve
from ._const import FORMATS, _MISSING, _MMD_KINDS



# ---------------------------------------------------------------- 数据面
def _data_json(root: str, rel: str, text: str, spec: Dict[str, Any]
               ) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    stats: Dict[str, Any] = {}
    try:
        obj = _strict_json(text)
    except ValueError as exc:
        return ["数据件 %s 不是合法 JSON：%s（修复指引：修好语法或换 format）" % (rel, exc)], {}
    sch_rel = str(spec.get("schema") or "")
    if not sch_rel:
        # schema 兄弟候选（D2）：按 {stem} 约定在同目录找，先命中先用；全不命中则记 no_schema
        # 并**只**跳过 schema 面（必填字段仍判）——不许把「没 schema」当成「没问题」。
        for tmpl in spec.get("schema_siblings") or []:
            cand = (Path(rel).parent / str(tmpl).replace("{stem}", Path(rel).stem)).as_posix()
            if (Path(root) / cand).is_file():
                sch_rel = cand
                break
    if sch_rel:
        sch, err = _schema_doc(root, sch_rel)
        if err:
            issues.append("数据件 %s 的 schema 读不到：%s" % (rel, err))
        else:
            from core import json_schema as js
            try:
                errs = js.json_schema_check(obj, sch or {})
            except ValueError as exc:
                errs = ["schema 本身不是合法 JSON：%s" % exc]
            issues += ["数据件 %s 不符 schema %s：%s" % (rel, sch_rel, e) for e in errs[:5]]
    for field in spec.get("required_fields") or []:
        if _dig(obj, field) is _MISSING:
            issues.append("数据件 %s 缺必填字段 %s（修复指引：补字段或从声明里删掉——声明即契约）"
                          % (rel, field))
    if spec.get("schema_siblings") and not sch_rel:
        stats["no_schema"] = 1          # 可见缺口：有 schema 兄弟约定但该件没有 schema
    stats["fields"] = len(spec.get("required_fields") or [])
    return issues, stats



def _csv_rows(text: str) -> List[List[str]]:
    return [row for row in csv.reader(io.StringIO(text))]



def _data_csv(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    rows = _csv_rows(text)
    if not rows:
        return ["数据件 %s 是空 CSV（修复指引：至少要有表头行）" % rel], {"rows": 0}
    header = [c.strip() for c in rows[0]]
    if any(not c for c in header):
        issues.append("数据件 %s 表头有空列名（修复指引：每列都要有名字）" % rel)
    width = len(header)
    data = [r for r in rows[1:] if r != [""]]
    bad = [i for i, r in enumerate(data, 2) if len(r) != width]
    if bad:
        issues.append("数据件 %s 第 %s 行列数 != 表头 %d（修复指引：补齐/删除多余的分隔符）"
                      % (rel, ",".join(str(b) for b in bad[:3]), width))
    missing = [c for c in spec.get("required_columns") or [] if c not in header]
    if missing:
        issues.append("数据件 %s 缺必需列 %s（修复指引：加列或改声明）" % (rel, ",".join(missing)))
    any_cols = [str(c) for c in spec.get("required_any_columns") or []]
    if any_cols and not any(c in header for c in any_cols):
        # 表头**族**各不相同（实测 CASES.csv 有 11 种表头），故只判「至少含一个」而非全等。
        issues.append("数据件 %s 表头不含任一必需列 %s（实为 %s）（修复指引：改用族内表头或改声明）"
                      % (rel, "|".join(any_cols), ",".join(header[:6])))
    low = int(spec.get("min_rows") or 0)
    if len(data) < low:
        issues.append("数据件 %s 数据行 %d < min_rows %d（修复指引：补样例或下调声明）"
                      % (rel, len(data), low))
    return issues, {"rows": len(data), "columns": width}



def _md_tables(text: str) -> List[List[List[str]]]:
    """按连续竖线行切表 → 每张表是行列表（表头 + 分隔行 + 数据行）。"""
    tables: List[List[List[str]]] = []
    cur: List[List[str]] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 2:
            cur.append([c.strip() for c in s.strip("|").split("|")])
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables



def _data_markdown(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    issues: List[str] = []
    if spec.get("frontmatter") and not text.startswith("---"):
        issues.append("数据件 %s 缺 frontmatter（修复指引：件首补 --- 块）" % rel)
    n = 0
    for table in _md_tables(text):
        if len(table) < 2:
            continue
        header = table[0]
        body = [r for r in table[1:] if not all(set(c) <= set("-:") for c in r)]
        ragged = [r for r in body if len(r) != len(header)]
        if ragged:
            issues.append("数据件 %s 有一张表列数不齐：表头 %d 列 vs 数据 %d 列（修复指引：对齐竖线"
                "）"
                          % (rel, len(header), len(ragged[0])))
        n += 1
    return issues, {"tables": n}



def _data_link(root: str, rel: str, spec: Dict[str, Any], obj: Any) -> List[str]:
    """输入输出一致性：路径字段指向的文件必须在场，其行数必须等于计数字段。"""
    link = spec.get("link") or {}
    issues: List[str] = []
    target = _dig(obj, str(link.get("path_field") or ""))
    if not isinstance(target, str) or not target:
        return ["数据件 %s 的 link.path_field=%s 取不到字符串路径（修复指引：核对字段名）"
                % (rel, link.get("path_field"))]
    rel_dir = Path(rel).parent
    bases = [str(link.get("base"))] if link.get("base") else [str(rel_dir), str(rel_dir.parent)]
    found = None
    for base in bases:
        cand = Path(root) / base / target
        if cand.is_file():
            found = cand
            break
    if found is None:
        return ["数据件 %s 指向的 %s 不在场（修复指引：补件或修正 link.base）" % (rel, target)]
    rows_field = str(link.get("rows_field") or "")
    if rows_field:
        want = _dig(obj, rows_field)
        got = len(_csv_rows(found.read_text(encoding="utf-8"))[1:])
        if want != got:
            issues.append("数据件 %s 的 %s=%s 与 %s 数据行 %d 不一致（修复指引：重算或改声明）"
                          % (rel, rows_field, want, target, got))
    return issues



def _schema_of(root: str, rel: str, spec: Dict[str, Any]) -> str:
    """声明的 schema 路径：显式 `schema` 优先，其次 `schema_siblings` 里第一个在场的兄弟候选。"""
    sch = str(spec.get("schema") or "")
    if sch:
        return sch
    for tmpl in spec.get("schema_siblings") or []:
        cand = (Path(rel).parent / str(tmpl).replace("{stem}", Path(rel).stem)).as_posix()
        if (Path(root) / cand).is_file():
            return cand
    return ""



def _schema_issues(root: str, rel: str, obj: Any, sch_rel: str) -> List[str]:
    """按 schema 校验已解析对象（四格式共用：YAML/TOML 解析后与 JSON 同一数据模型）。"""
    from core import json_schema as js
    sch, err = _schema_doc(root, sch_rel)
    if err:
        return ["数据件 %s 的 schema 读不到：%s" % (rel, err)]
    try:
        errs = js.json_schema_check(obj, sch or {})
    except ValueError as exc:
        errs = ["schema 本身不是合法 JSON：%s" % exc]
    return ["数据件 %s 不符 schema %s：%s" % (rel, sch_rel, e) for e in errs[:5]]



def _fields_issues(rel: str, obj: Any, spec: Dict[str, Any]) -> List[str]:
    return ["数据件 %s 缺必填字段 %s（修复指引：补字段或从声明里删掉——声明即契约）" % (rel, f)
            for f in spec.get("required_fields") or [] if _dig(obj, f) is _MISSING]



def _data_yaml(root: str, rel: str, text: str,
               spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """YAML 数据件：复用仓库既有懒加载 YAML（软依赖），解析后与 JSON 同判据。"""
    from core import lazy_yaml
    ymod = lazy_yaml.module()                # 惰性入口：缺 PyYAML 时返回 None（不是即报）
    if ymod is None:
        # 契约判据**不许**在缺依赖时静默放行（那等于假绿）：报缺口并给安装指引。
        return ["数据件 %s 未判：PyYAML 不在场"
                "（修复指引：pip install pyyaml，或改成 format=text）"
                % rel], {"yaml_unavailable": 1}
    try:
        loader = lazy_yaml.safe_loader()
        obj = ymod.load(text, Loader=loader) if loader is not None else ymod.safe_load(text)
    except Exception as exc:                                  # noqa: BLE001 —— 解析器异常按坏件报
        return ["数据件 %s 不是合法 YAML：%s（修复指引：修好缩进/语法）"
                % (rel, exc)], {}
    issues: List[str] = []
    sch = _schema_of(root, rel, spec)
    if sch:
        issues += _schema_issues(root, rel, obj, sch)
    issues += _fields_issues(rel, obj, spec)
    return issues, {"fields": len(spec.get("required_fields") or [])}



def _data_toml(root: str, rel: str, text: str,
               spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """TOML 数据件：stdlib `tomllib`（3.11+）；解析后同 JSON 判据。"""
    import tomllib
    try:
        obj = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return ["数据件 %s 不是合法 TOML：%s（修复指引：修好语法或换 format）" % (rel, exc)], {}
    issues: List[str] = []
    sch = _schema_of(root, rel, spec)
    if sch:
        issues += _schema_issues(root, rel, obj, sch)
    issues += _fields_issues(rel, obj, spec)
    return issues, {"fields": len(spec.get("required_fields") or [])}



def _data_jsonl(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """JSONL：**逐行**严格 JSON（空行跳过）；必填字段对每一行判。"""
    issues: List[str] = []
    rows = 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        rows += 1
        try:
            obj = _strict_json(line)
        except ValueError as exc:
            issues.append("数据件 %s 第 %d 行不是合法 JSON：%s（修复指引：一行一条）"
                          % (rel, i, exc))
            continue
        for f in spec.get("required_fields") or []:
            if _dig(obj, f) is _MISSING:
                issues.append("数据件 %s 第 %d 行缺必填字段 %s（修复指引：补字段）"
                              % (rel, i, f))
    if spec.get("min_rows") and rows < int(spec["min_rows"]):
        issues.append("数据件 %s 行数 %d < min_rows %s（修复指引：补样例或下调声明）"
                      % (rel, rows, spec["min_rows"]))
    return issues, {"rows": rows}



def _data_graphml(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """GraphML：XML 良构 + 节点/边计数（图结构资产的可证那部分）。

    解析前的**拒收门槛**：含 DTD / 实体声明的图件直接拒——Billion-Laughs / XXE 的载体都在那两处，
    而本层处理的是仓内资产（非不可信输入），故 `# nosec` 的例外只需覆盖「标准库 XML 解析」本身，
    不覆盖实体展开（那条已在入口拒掉）。
    """
    if re.search(r"<!DOCTYPE|<!ENTITY", text):
        return ["数据件 %s 含 DTD/实体声明，拒绝解析（修复指引：去掉 DOCTYPE/ENTITY——导出工具重跑）"
                % rel], {}
    import xml.etree.ElementTree as ET  # nosec B405 —— 见函数自述：入口已拒 DTD/ENTITY
    try:
        root_el = ET.fromstring(text)        # nosec B314  # noqa: S314
    except ET.ParseError as exc:
        return ["数据件 %s 不是良构 XML：%s（修复指引：修好 XML）" % (rel, exc)], {}
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    nodes = len(root_el.findall(".//g:node", ns)) or len(root_el.findall(".//node"))
    edges = len(root_el.findall(".//g:edge", ns)) or len(root_el.findall(".//edge"))
    issues: List[str] = []
    if spec.get("min_nodes") and nodes < int(spec["min_nodes"]):
        issues.append("数据件 %s 节点数 %d < min_nodes %s（修复指引：补结构或下调声明）"
                      % (rel, nodes, spec["min_nodes"]))
    return issues, {"nodes": nodes, "edges": edges}



def _data_mmd(rel: str, text: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """Mermaid：首关键词须是合法图型（结构判据，不解析图内容）。"""
    first = ""
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("%%"):
            first = s.split()[0] if s.split() else ""
            break
    if not first:
        return ["数据件 %s 是空 Mermaid 图（修复指引：补图声明）" % rel], {}
    base = first.split("-")[0] if first.startswith(("xychart", "block")) else first
    if first not in _MMD_KINDS and base not in _MMD_KINDS:
        return ["数据件 %s 首关键词 %r 不是合法 Mermaid 图型"
                "（修复指引：用 graph/flowchart/sequenceDiagram 等）"
                % (rel, first)], {}
    return [], {"kind": first}




#: 数据面格式 → 判据函数（统一签名；原 if/elif 派发链改为查表，嵌套 ≤8 且新格式只加一行）
_DATA_FMT = {
    "json": lambda root, rel, text, spec: _data_json(root, rel, text, spec),
    "csv": lambda root, rel, text, spec: _data_csv(rel, text, spec),
    "markdown": lambda root, rel, text, spec: _data_markdown(rel, text, spec),
    "yaml": lambda root, rel, text, spec: _data_yaml(root, rel, text, spec),
    "toml": lambda root, rel, text, spec: _data_toml(root, rel, text, spec),
    "jsonl": lambda root, rel, text, spec: _data_jsonl(rel, text, spec),
    "graphml": lambda root, rel, text, spec: _data_graphml(rel, text, spec),
    "mmd": lambda root, rel, text, spec: _data_mmd(rel, text, spec),
}


def _check_data(root: str, spec: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    sid = str(spec.get("id") or spec.get("path") or spec.get("glob") or "?")
    rels = resolve(root, spec)
    if not rels:
        return (["数据契约 %s 未命中任何文件（修复指引：修正 path/glob —— 空气不是契约）" % sid],
                {"files": 0})
    fmt = str(spec.get("format") or "").lower()
    if fmt not in FORMATS:
        return (["数据契约 %s 的 format=%r 不在词表 %s（修复指引：改用词表内格式）"
                 % (sid, fmt, "/".join(FORMATS))], {"files": len(rels)})
    if spec.get("sha256") and len(rels) != 1:
        return (["数据契约 %s 声明了 sha256 却命中 %d 件（修复指引：sha256 只用于 path 单件）"
                 % (sid, len(rels))], {"files": len(rels)})
    issues: List[str] = []
    stats: Dict[str, Any] = {"files": len(rels), "format": fmt}
    for rel in rels:
        text, err = _read(root, rel)
        if err:
            issues.append(err)
            continue
        text = text or ""
        obj: Any = None
        if fmt == "json":
            try:
                obj = _strict_json(text)
            except ValueError:
                obj = None
        handler = _DATA_FMT.get(fmt)
        if handler is not None:
            sub, s = handler(root, rel, text, spec)
        else:
            sub, s = [], {"lines": len(text.splitlines())}
        issues += sub
        for _k in ("no_schema", "yaml_unavailable"):
            if s.get(_k):
                stats[_k] = int(stats.get(_k) or 0) + 1
                s = {k: v for k, v in s.items() if k != _k}
        stats.update(s)
        if spec.get("sha256"):
            got = digest_of(Path(root) / rel)
            if got != str(spec["sha256"]):
                issues.append("数据件 %s 摘要不符（记录 %s / 实测 %s）（修复指引：核对改动，"
                              "确认后用 nf asset contract --freeze 重冻）"
                              % (rel, str(spec["sha256"])[:12], got[:12]))
        if spec.get("link") and obj is not None:
            issues += _data_link(root, rel, spec, obj)
    return issues, stats
