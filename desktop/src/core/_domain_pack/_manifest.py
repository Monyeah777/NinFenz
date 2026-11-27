"""domain_pack · _manifest（自 domain_pack.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import conformance_scan as csc
from core import json_doc

from ._alloc import (
    allocate,
)
from ._catalog import (
    authenticity,
    bindings_full,
    concept_index,
)
from ._const import (
    AUTHENTICITY_THRESHOLD,
    BINDING_REL,
    DENSITY_THRESHOLD,
    MANIFEST_REL,
    REACHABLE_RATIO_THRESHOLD,
    REGISTRY_REL,
    SPEC_DIR,
    STANDARDS_REL,
)
from ._io import (
    _read_json,
    _write_text_retry,
    standards_catalog,
)
from ._json_faces import (
    output_index,
)

# ---------------------------------------------------------------- 名录（公开结果面）

def _tier_faces(idx: Dict[str, Any], tiers: Tuple[str, ...]) -> List[Dict[str, Any]]:
    return [e for e in idx["outputs"] if e.get("tier") in tiers]


def _std_ids(values: Any) -> set:
    return set(filter(None, values))


def _other_packs(doc: Dict[str, Any], entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [p for p in doc["packs"] if p.get("code") != entry["code"]]


def _pack_min(packs: List[Dict[str, Any]], key: str, coerce: Any) -> Any:
    return min((coerce(p.get(key) or 0) for p in packs), default=coerce(0))


def _std_set(rows: List[Dict[str, Any]], key: str) -> set:
    return {r[key] for r in rows if r[key]}


def _support_rows(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [r for r in p["bindings"] if r.get("support_standard")]


def _binding_attr(cat: Dict[str, Any], sid: str, why: str, key: str) -> Dict[str, Any]:
    std = cat.get(sid) or {}
    ev = std.get("evidence") or {}
    return {
        key: sid,
        key + "_rationale": why,
        key + "_layer": std.get("layer", ""),
        key + "_body": std.get("body", ""),
        key + "_url": std.get("url", ""),
        key + "_reachable": bool(ev.get("reachable")),
        key + "_probe_date": str(ev.get("probe_date") or ""),
    }


def manifest_entry(root: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    alloc = allocate(root, spec)
    idx = json_doc.loads(output_index(spec), dict, what="output index")
    mv = _tier_faces(idx, ("T2", "T3", "T4"))
    t4 = _tier_faces(idx, ("T4",))
    ratio = round(len(mv) / max(1, len(idx["outputs"])), 4)
    spec_blob = json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")
    cat = standards_catalog(root)
    ci = concept_index(spec, cat)
    auth = authenticity(spec, cat)
    n_sub = max(1, len(spec["subdivisions"]))
    bound_std = _std_ids(list(ci["primary"].values()) + list(ci["support"].values()))
    prim_std = _std_ids(ci["primary"].values())
    sup_std = _std_ids(ci["support"].values())
    return {
        "code": spec["code"],
        "section": spec["section"],
        "name": spec["name"],
        "package": spec["pack_name"],
        "category": spec["category"],
        "pipeline": alloc["pipeline"],
        "module_ids": alloc["module_ids"],
        "modules": len(alloc["module_ids"]),
        "subdivisions": len(spec["subdivisions"]),
        "assets": 3,
        "output_faces": len(idx["outputs"]),
        "machine_verifiable_faces": len(mv),
        "functional_faces": len(t4),
        "machine_verifiable_ratio": ratio,
        "metric_family": spec["metric_family"],
        "content_tier": spec.get("content_tier", "authored"),
        "standards_bound": len(bound_std),
        "standards_bound_primary": len(prim_std),
        "standards_bound_support": len(sup_std),
        "standards_binding_coverage": round(len(prim_std) / n_sub, 4),
        "support_binding_coverage": round(len(sup_std) / n_sub, 4),
        "standards_dep_edges": len(ci["dep_edges"]),
        "standards_reachable_ratio": auth["reachable_ratio"],
        "data_authenticity": auth["score"],
        "concept_nodes": ci["nodes"],
        "concept_edges": ci["edges"],
        "concept_density": ci["density"],
        "spec_digest": hashlib.sha256(spec_blob).hexdigest(),
    }




def update_manifest(root: str, spec: Dict[str, Any], write: bool = False) -> Dict[str, Any]:
    """维护 `protocol/domain_packs.json`（公开名录：域码 → 包/管线/模块/产出面/机验率）。"""
    path = Path(root) / MANIFEST_REL
    doc: Dict[str, Any] = json_doc.load(path, dict, what=MANIFEST_REL) if path.is_file() else {
        "schema": "nf-domain-packs/1",
        "note": "AI 品类域包名录（公开结果面）。每包：域码 / 独占类别 / 管线 / 模块 / "
                "资产数 / 产出面与机验率 / 规格摘要。机检：check32 domain_packs 子扫描"
                "（名录 ↔ 盘上实况一致 + 可机验占比 ≥95%）。规格源在内部档案，"
                "故名录只登记摘要（spec_digest）不携带内容。",
        "machine_verifiable_threshold": 0.95,
        "packs": [],
    }
    entry = manifest_entry(root, spec)
    packs = _other_packs(doc, entry)
    packs.append(entry)
    doc["packs"] = sorted(packs, key=lambda p: p["code"])
    doc["count"] = len(doc["packs"])
    doc["subdivisions_total"] = sum(int(p.get("subdivisions") or 0) for p in doc["packs"])
    doc["standards_catalog"] = STANDARDS_REL
    doc["concept_density_threshold"] = DENSITY_THRESHOLD
    doc["concept_density_min"] = _pack_min(doc["packs"], "concept_density", float)
    doc["binding_coverage_min"] = _pack_min(
        doc["packs"], "standards_binding_coverage", float)
    doc["support_binding_coverage_min"] = _pack_min(
        doc["packs"], "support_binding_coverage", float)
    doc["data_authenticity_threshold"] = AUTHENTICITY_THRESHOLD
    doc["data_authenticity_min"] = _pack_min(doc["packs"], "data_authenticity", float)
    doc["reachable_ratio_threshold"] = REACHABLE_RATIO_THRESHOLD
    doc["standards_dep_edges_min"] = _pack_min(doc["packs"], "standards_dep_edges", int)
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_retry(path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        _write_binding_table(root, spec)
    return doc




def _write_binding_table(root: str, spec: Dict[str, Any]) -> None:
    """维护 `protocol/standards_binding.json`：逐包逐细分的标准绑定 + 理由（公开结果面）。"""
    path = Path(root) / BINDING_REL
    doc = _read_json(path) or {
        "schema": "nf-standards-binding/1",
        "note": "域包 × 细分 → 可扩展标准目录条目的绑定表（公开结果面）。判据"
                "（check32 domain_packs）：① 每条细分都有 standard_ref；② 引用 id 必须在 "
                "protocol/standards_catalog.json 在册；③ 每包绑定覆盖率 100%；"
                "④ 概念密度（边/节点，含主锚/辅锚标准节点、绑定边与标准依赖边）≥ 门槛；"
                "⑤ **双锚**：每细分另有 support_standard（产出承载标准，与主锚异层优先）；"
                "⑥ 数据真实性：引用标准的本机实测记录（reachable/probe_date）逐条落 row。",
        "catalog": STANDARDS_REL,
        "packs": [],
    }
    cat = standards_catalog(root)
    rows = []
    _bd = bindings_full(spec, cat)
    for s in spec["subdivisions"]:
        rec = {"subdivision": s["id"], "name": s["name"]}
        for role, key in (("primary", "standard"), ("support", "support_standard")):
            sid, why = _bd[s["id"]][role]
            rec.update(_binding_attr(cat, sid, why, key))
        rows.append(rec)
    auth = authenticity(spec, cat)
    entry = {"code": spec["code"], "package": spec["pack_name"],
             "category": spec["category"], "subdivisions": len(rows),
             "distinct_standards": len(_std_set(rows, "standard")),
             "distinct_standards_with_support": len(
                 _std_set(rows, "standard") | _std_set(rows, "support_standard")),
             "data_authenticity": auth["score"],
             "reachable_ratio": auth["reachable_ratio"],
             "probe_evidence_ratio": auth["probe_evidence_ratio"],
             "bindings": rows}
    packs = _other_packs(doc, entry)
    packs.append(entry)
    doc["packs"] = sorted(packs, key=lambda p: p["code"])
    doc["count"] = len(doc["packs"])
    doc["bindings_total"] = sum(len(p["bindings"]) for p in doc["packs"])
    doc["support_bindings_total"] = sum(len(_support_rows(p)) for p in doc["packs"])
    doc["data_authenticity_min"] = _pack_min(doc["packs"], "data_authenticity", float)
    doc["data_authenticity_threshold"] = AUTHENTICITY_THRESHOLD
    _write_text_retry(path, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")




def manifest_verify(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """名录机检：名录 ↔ 盘上实况一致 + 可机验占比 ≥ 门槛（check32 子扫描）。"""
    issues: List[str] = []
    path = Path(root) / MANIFEST_REL
    if not path.is_file():
        return [], {"packs": 0, "note": "无域包名录（域包工程未启用）"}
    doc = json_doc.load(path, dict, what=MANIFEST_REL)
    thr = float(doc.get("machine_verifiable_threshold") or 0.95)
    cat = standards_catalog(root)
    dens_min = float(doc.get("concept_density_threshold") or 1.0)
    auth_min = float(doc.get("data_authenticity_threshold") or AUTHENTICITY_THRESHOLD)
    reach_min = float(doc.get("reachable_ratio_threshold") or REACHABLE_RATIO_THRESHOLD)
    stats = {"packs": 0, "faces": 0, "functional": 0}
    reg = _read_json(Path(root) / REGISTRY_REL) or {}
    by_id = {p.get("id"): p for p in reg.get("protocols") or []}
    _bind = _read_json(Path(root) / BINDING_REL) or {}
    bind_by = {b.get("code"): b for b in _bind.get("packs") or []}
    for p in doc.get("packs") or []:
        pkg = str(p.get("package") or "")
        bp = bind_by.get(p.get("code")) or {}
        stats["packs"] += 1
        stats["faces"] += int(p.get("output_faces") or 0)
        stats["functional"] += int(p.get("functional_faces") or 0)
        regp = by_id.get(pkg)
        if not regp:
            issues.append("%s：registry protocols[] 无该包（名录 ↔ 登记不一致）" % pkg)
        else:
            if str(regp.get("pipeline")) != str(p.get("pipeline")):
                issues.append("%s：管线不一致（名录 %s / registry %s）"
                              % (pkg, p.get("pipeline"), regp.get("pipeline")))
            if [str(x) for x in regp.get("module_ids") or []] != \
                    [str(x) for x in p.get("module_ids") or []]:
                issues.append("%s：模块 id 不一致（名录 ↔ registry）" % pkg)
        proto = Path(root) / "community" / pkg / "protocol.yaml"
        if not proto.is_file():
            issues.append("%s：包目录或 protocol.yaml 缺失" % pkg); continue
        text = csc.read_text_cached(proto)
        for tok in (str(p.get("pipeline")), str(p.get("category"))):
            if tok not in text:
                issues.append("%s：protocol.yaml 缺名录声明 %s" % (pkg, tok))
        idx_path = Path(root) / "community" / pkg / "outputs" / "INDEX.json"
        if not idx_path.is_file():
            issues.append("%s：缺 outputs/INDEX.json" % pkg); continue
        idx_doc = json_doc.loads(csc.read_text_cached(idx_path), dict, what=str(idx_path))
        faces = (idx_doc.get("outputs") or [])
        ratio = round(sum(1 for e in faces if e.get("tier") in ("T2", "T3", "T4"))
                      / max(1, len(faces)), 4)
        if ratio < thr:
            issues.append("%s：可机验产出占比 %.4f < 门槛 %.2f（产出面必须 ≥95%% 可机验）"
                          % (pkg, ratio, thr))
        if not any(e.get("tier") == "T4" for e in faces):
            issues.append("%s：无 T4 可复算面（域包必须有一个可重算产出）" % pkg)
        if int(p.get("output_faces") or 0) != len(faces):
            issues.append("%s：名录产出面数 %s ≠ INDEX 实况 %d"
                          % (pkg, p.get("output_faces"), len(faces)))
        # 可扩展标准绑定面（2026-09-23 对齐）：覆盖率 100% + 引用在册 + 概念密度不回落
        spec_path = Path(root) / SPEC_DIR / ("%s.json" % p.get("code", ""))
        if spec_path.is_file():
            payload = _read_json(Path(root) / "community" / pkg / "outputs"
                                 / "DOMAIN_SPEC.json") or {}
            subs = payload.get("subdivisions") or []
            bad_ref = [s["id"] for s in subs if str(s.get("standard_ref") or "") not in cat]
            if bad_ref:
                issues.append("%s：细分未绑可扩展标准或引用不在册：%s" % (pkg, bad_ref[:4]))
            if subs and len(bad_ref) > 0:
                pass
            if float(p.get("standards_binding_coverage") or 0) < 1.0:
                issues.append("%s：标准绑定覆盖率 %.2f < 1.0（每条细分须绑一个目录内标准）"
                              % (pkg, float(p.get("standards_binding_coverage") or 0)))
            if float(p.get("concept_density") or 0) < dens_min:
                issues.append("%s：概念密度 %.3f < 门槛 %.3f（边/节点；含标准节点与绑定边）"
                              % (pkg, float(p.get("concept_density") or 0), dens_min))
            if int(p.get("standards_bound") or 0) < 3:
                issues.append("%s：绑定标准数 %s < 3（单包至少要贴 3 条不同标准）"
                              % (pkg, p.get("standards_bound")))
            # 双锚 + 数据真实性（2026-09-24 对齐）：主锚/辅锚齐备、引用有本机实测证据
            if float(p.get("support_binding_coverage") or 0) < 1.0:
                issues.append("%s：辅锚覆盖率 %.2f < 1.0（每条细分须另绑一条产出承载标准）"
                              % (pkg, float(p.get("support_binding_coverage") or 0)))
            if int(p.get("standards_dep_edges") or 0) < 1:
                issues.append("%s：概念图无标准依赖边（绑定标准的 depends_on 未入图）" % pkg)
            auth = float(p.get("data_authenticity") or 0)
            if auth < auth_min:
                issues.append("%s：数据真实性分 %.4f < 门槛 %.2f（在册 × 实测可达 × 证据齐备）"
                              % (pkg, auth, auth_min))
            rr = float(p.get("standards_reachable_ratio") or 0)
            if rr < reach_min:
                issues.append("%s：绑定标准本机实测可达率 %.4f < 门槛 %.2f"
                              % (pkg, rr, reach_min))
            bad_binding = [r for r in (bp.get("bindings") or [])
                           if str(r.get("standard") or "") not in cat
                           or str(r.get("support_standard") or "") not in cat
                           or not str(r.get("standard_probe_date") or "")
                           or not str(r.get("support_standard_probe_date") or "")]
            if bad_binding:
                issues.append("%s：绑定表缺在册证明或实测记录：%s"
                              % (pkg, [r.get("subdivision") for r in bad_binding[:4]]))
    return issues, stats




def _scan_impl(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """真算（未命中缓存时走这里）。"""
    return manifest_verify(root)
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
