"""output_forms 私有子模块 _registry：形态清单读取/自检与形态识别（扩展名 + 内容嗅探）。

门面 core.output_forms 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from core import json_doc

from ._const import INDEX_REL, REGISTRY_REL, STATUSES, TIERS, _EXT_FORM, _FORM_MAX_TIER



def _rel(root: str, rel: str) -> Path:
    return Path(root) / rel.replace("/", os.sep)



def _read_text_cached(path: Path) -> str:
    from core import conformance_scan as _csc
    return _csc.read_text_cached(path)



def _read_bytes_cached(path: Path) -> bytes:
    from core import conformance_scan as _csc
    return _csc.read_bytes_cached(path)



def _read_json(path: Path) -> Tuple[Any, str]:
    try:
        return json_doc.loads(_read_text_cached(path), None, what=str(path)), ""
    except OSError as exc:
        return None, "不可读：%s" % exc
    except ValueError as exc:
        return None, "JSON 解析失败：%s" % exc



# ---------------------------------------------------------------- 形态清单

def load_registry(root: str = ".") -> Dict[str, Any]:
    data, _ = _read_json(_rel(root, REGISTRY_REL))
    return data if isinstance(data, dict) else {}



def _category_issues(cats) -> List[str]:
    """categories 条目必须带 id/name。"""
    issues: List[str] = []
    for c in cats:
        if not isinstance(c, dict) or not c.get("id") or not c.get("name"):
            issues.append("categories 条目缺 id/name：%r" % (c,))
    return issues


def _form_identity_issues(f: Dict[str, Any], seen: set, cat_ids: set) -> List[str]:
    """形态身份面：id 唯一 + 类别/档位/状态在册。"""
    issues: List[str] = []
    fid = f.get("id")
    if fid in seen:
        issues.append("形态 id 重复：%s" % fid)
    seen.add(fid)
    if f.get("category") not in cat_ids:
        issues.append("%s 类别未在册：%r" % (fid, f.get("category")))
    if f.get("tier") not in TIERS:
        issues.append("%s 档位非法：%r（预期 %s）" % (fid, f.get("tier"), "/".join(TIERS)))
    if f.get("status") not in STATUSES:
        issues.append("%s 状态非法：%r" % (fid, f.get("status")))
    return issues


def _form_evidence_issues(f: Dict[str, Any], fid: Any) -> Tuple[List[str], int]:
    """形态证据面：spec.uri 必填（unfit 可空）+ 可达性实证必需 → (issues, 不可达数)。"""
    issues: List[str] = []
    unreachable = 0
    spec = f.get("spec") or {}
    if f.get("status") != "unfit" and not spec.get("uri"):
        issues.append("%s 缺规范入口 spec.uri（不适面才可空）" % fid)
    ev = f.get("evidence") or {}
    if "reachable" not in ev:
        issues.append("%s 缺可达性实证 evidence.reachable（不伪造：查不到也要记 false）" % fid)
    elif ev.get("reachable") is False:
        unreachable += 1
    return issues, unreachable


def _form_row_issues(f: Any, seen: set, cat_ids: set) -> Tuple[List[str], int]:
    """单条形态：非对象/缺 id 直接报；否则走身份面 + 证据面。"""
    if not isinstance(f, dict):
        return ["forms 条目非对象：%r" % (f,)], 0
    fid = f.get("id")
    if not fid:
        return ["forms 条目缺 id：%r" % (f,)], 0
    issues = _form_identity_issues(f, seen, cat_ids)
    ev_issues, unreachable = _form_evidence_issues(f, fid)
    issues.extend(ev_issues)
    return issues, unreachable


def _form_counts(forms) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    """类别/档位/状态三维计数（非对象条目跳过）。"""
    per_cat: Dict[str, int] = {}
    per_tier: Dict[str, int] = {}
    per_status: Dict[str, int] = {}
    for f in forms:
        if not isinstance(f, dict):
            continue
        per_cat[str(f.get("category"))] = per_cat.get(str(f.get("category")), 0) + 1
        per_tier[str(f.get("tier"))] = per_tier.get(str(f.get("tier")), 0) + 1
        per_status[str(f.get("status"))] = per_status.get(str(f.get("status")), 0) + 1
    return per_cat, per_tier, per_status


def registry_verify(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """形态清单自检：结构合法 + 类别/档位在册 + id 唯一 + 可达性实证齐备。"""
    issues: List[str] = []
    reg = load_registry(root)
    if not reg:
        return ["%s 缺失或不可解析（形态清单是真源）" % REGISTRY_REL], {}
    if reg.get("schema") != "nf-output-forms/1":
        issues.append("schema 应为 nf-output-forms/1，实为 %r" % reg.get("schema"))
    cats = reg.get("categories") or []
    cat_ids = {c.get("id") for c in cats if isinstance(c, dict)}
    if not cat_ids:
        issues.append("categories 为空（形态必须有类别归属）")
    issues.extend(_category_issues(cats))
    forms = reg.get("forms") or []
    seen: set = set()
    unreachable = 0
    for f in forms:
        row_issues, bad = _form_row_issues(f, seen, cat_ids)
        issues.extend(row_issues)
        unreachable += bad
    per_cat, per_tier, per_status = _form_counts(forms)
    stats = {"forms": len(forms), "categories": len(cat_ids),
             "by_category": per_cat, "by_tier": per_tier, "by_status": per_status,
             "unreachable": unreachable}
    return issues, stats



# ---------------------------------------------------------------- 形态识别

def _json_schema_form(base_form: str, sch: str) -> str:
    """$schema 主机名含 json-schema.org（含子域）→ json-schema；否则沿用扩展名形态。"""
    # 2026-11-09（CodeQL py/incomplete-url-substring-sanitization）：原来用
    # `"json-schema.org" in sch` 会被 `https://evil/json-schema.org` 之类字符串骗过；
    # 判**主机名**（含子域），不判子串。
    host = urlsplit(sch).hostname or ""
    if host == "json-schema.org" or host.endswith(".json-schema.org"):
        return "json-schema"
    return base_form


def _json_form_head(data: Dict[str, Any], kind: str) -> str | None:
    """首轮识别：nf-domain-spec 与 nf-combo/1 组合卡。"""
    if kind.startswith("nf-domain-spec"):
        return "domain-spec"
    if str(data.get("schema") or "").startswith("nf-combo/1"):
        return "combo-cert"
    return None


def _json_form_kind(kind: str) -> str | None:
    """kind 前缀识别：domain-report / system-card。"""
    if kind.startswith("nf-domain-report"):
        return "domain-report"
    if kind.startswith("nf-system-card"):
        return "system-card"
    return None


def _json_form_vega(sch: str) -> str | None:
    """$schema 字符串识别：vega-lite 必须先于 vega。"""
    if "vega-lite" in sch:
        return "vega-lite"
    if "vega" in sch:
        return "vega"
    return None


def _json_form_tail(kind: str) -> str | None:
    """kind 前缀识别：performance / quant-metrics / concept-closure。"""
    if kind.startswith("nf-performance"):
        return "performance-report"
    if kind.startswith("nf-quant-metrics"):
        return "quant-metrics"
    if kind.startswith("nf-concept-closure"):
        return "concept-closure"
    return None


def _json_form(data: Dict[str, Any], base_form: str) -> str:
    """JSON 形态嗅探（单一派发点）：先按 $schema 主机名定 json-schema，再按 kind/键名逐级覆盖。"""
    sch = str(data.get("$schema") or "").strip()
    form = _json_schema_form(base_form, sch)
    kind = str(data.get("kind") or "")
    for step in (_json_form_head(data, kind), _json_form_kind(kind),
                 _json_form_vega(sch), _json_form_tail(kind)):
        if step is not None:
            return step
    return form


def detect(root: str, rel: str) -> Tuple[str, str]:
    """按扩展名 + 内容嗅探判形态，返回 (form_id, tier)。不猜：认不出即 text/T0。"""
    path = _rel(root, rel)
    ext = path.suffix.lower()
    form = _EXT_FORM.get(ext, "text")
    if ext == ".json":
        data, _ = _read_json(path)
        if isinstance(data, dict):
            form = _json_form(data, form)
    return form, _FORM_MAX_TIER.get(form, "T1")



# ---------------------------------------------------------------- 包级产出清单

def _pack_dirs(root: str) -> List[str]:
    """有 `community/<包>/outputs/INDEX.json` 的包目录名（有序）。

    效率（实测 2026-09-29）：原实现是 `Path.iterdir()` + 逐条 `d.is_dir()` +
    `INDEX.json.is_file()`——**每次 20 ms**（106 个包 ⇒ 200+ 次 stat），而 `index_verify` 与
    `meter` 每个内容状态各调一次 ⇒ 一次新状态白花 **40 ms**（占 `index_verify` 的一半）。
    改走共享枚举器（`community/*/outputs/INDEX.json`；目录清单已在常驻层）后 **~1 ms**。
    面**逐件一致**由 `test_output_forms.PackEnumerationTest` 用旧口径原样重算比对守着。
    """
    from core import conformance_scan as _csc
    return sorted({rel.split("/")[1]
                   for rel in _csc.iter_files(root, "community/*/" + INDEX_REL)})
