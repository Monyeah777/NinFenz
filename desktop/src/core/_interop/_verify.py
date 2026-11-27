"""interop_export 私有子模块 _verify：总验与摘要：全形态自洽校验 + 计数摘要。

门面 core.interop_export 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import os

from ._base import CONTRACT_REL, EVENTS_REL, EXTERNAL_EVENTS_REL, RECEIPTS_REL, _read_json
from ._checks import _arr, _check_a2a, _check_asyncapi, _check_c2pa, _check_cid, _check_cyclonedx, _check_decision, _check_determinism, _check_intoto, _check_openapi, _check_prov, _check_sbom, _check_slsa, _check_vc, _obj
from ._docs_a import asyncapi_doc, intoto_statement, openapi_doc, sbom_doc, slsa_provenance
from ._docs_b import a2a_agent_card, c2pa_manifest, cid_index, cyclonedx_doc, decision_surface, prov_document, vc_document



def verify(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """门禁：覆盖完整 + 形状合法 + 确定性（派生面不许漂移）。"""
    issues: List[str] = []
    contract = _read_json(root, CONTRACT_REL)
    reg = _read_json(root, EVENTS_REL)
    ext = _read_json(root, EXTERNAL_EVENTS_REL)
    rec = _read_json(root, RECEIPTS_REL)
    # fail-closed：真源缺失 = 派生面无从校验（不是"空导出面"，是"没有可导出的东西"）
    for rel in (CONTRACT_REL, EVENTS_REL, RECEIPTS_REL):
        if not os.path.isfile(os.path.join(root, rel)):
            issues.append("缺派生真源 %s（修复指引：先落声明件——导出面只做纯派生，"
                          "不自造真源）" % rel)
    oa, aa, st = openapi_doc(root), asyncapi_doc(root), intoto_statement(root)
    sb, sl, card = sbom_doc(root), slsa_provenance(root), a2a_agent_card(root)
    pv, cdx, vc = prov_document(root), cyclonedx_doc(root), vc_document(root)
    c2, ci, ds = c2pa_manifest(root), cid_index(root), decision_surface(root)
    _check_openapi(oa, contract, issues)
    _check_asyncapi(aa, reg, ext, issues)
    _check_intoto(st, rec, issues)
    _check_sbom(sb, issues)
    _check_determinism(root, issues)
    _check_slsa(sl, rec, root, issues)
    _check_a2a(card, contract, issues)
    _check_prov(pv, root, issues)
    _check_cyclonedx(cdx, root, issues)
    _check_vc(vc, issues)
    _check_c2pa(c2, issues)
    _check_cid(ci, rec, issues)
    _check_decision(ds, root, issues)
    stats = {"openapi_paths": len(_obj(oa.get("paths"))),
             "asyncapi_channels": len(_obj(aa.get("channels"))),
             "intoto_subjects": len(_arr(st.get("subject"))),
             "sbom_packages": len(_arr(sb.get("packages"))),
             "slsa_subjects": len(_arr(sl.get("subject"))),
             "a2a_skills": len(_arr(card.get("skills"))),
             "prov_nodes": len(_arr(pv.get("@graph"))),
             "prov_counts": _obj(pv.get("x-nf-counts")),
             "cyclonedx_components": len(_arr(cdx.get("components"))),
             "vc_type": (vc.get("type") or [""])[0],
             "c2pa_assertions": len(_arr(c2.get("assertions"))),
             "cid_entries": len(_arr(ci.get("entries"))),
             "decision_adapters": len(_arr(ds.get("adapters"))),
             "decision_candidates": len(_arr(ds.get("candidates"))),
             "decision_audits": len(_arr(ds.get("publicDecisionIndex"))),
             "issues": len(issues)}
    return issues, stats



def summary(stats: Dict[str, Any]) -> str:
    return ("OpenAPI 路径 %(openapi_paths)d / AsyncAPI 通道 %(asyncapi_channels)d / "
            "in-toto subject %(intoto_subjects)d / SBOM 包 %(sbom_packages)d / "
            "SLSA subject %(slsa_subjects)d / A2A skills %(a2a_skills)d / "
            "PROV 节点 %(prov_nodes)d / 决策面 适配器 %(decision_adapters)d"
            "（裁决索引 %(decision_audits)d）" % stats)
