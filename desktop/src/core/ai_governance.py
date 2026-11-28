"""AI 治理登记（`nf-ai-governance/1`）：影响评估 + 模型风险 + 监管映射，逐条可核。

为什么（NF-Final WP-0F，P0 盲区 BL-02）：没有影响评估/模型风险/监管映射的「AI 信任」是空心。
本模块把这三件事做成数据 + 判据：
- 范围/受影响方/不进范围（不把本仓写成 AI 平台）；
- 影响评估四项标准 + 人类监督/透明度/救济的**证据件必须真实在场**；
- 模型风险登记：概率/影响/缓解/证据/owner/状态；未 enforced 必须写 planned_gate（不冒充已控）；
- 监管映射：claim 只允许 `mechanism-alignment`/`not-claimed`（不声称合规）；每条必须有真实证据件。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-ai-governance/1"
REL = "protocol/ai_governance.json"
STATUSES = ("enforced", "partial", "planned", "UNOBSERVABLE")
CLAIMS = ("mechanism-alignment", "not-claimed")
GATES = ("G0", "G1", "G2", "G3", "G4", "G5")
RISK_LEVELS = ("low", "medium", "high")
GUIDE = "修复指引："
#: 监管映射必备框架（少一条 = 覆盖缺口）
EXPECTED_FRAMEWORKS = ("NIST AI RMF", "ISO/IEC 42001", "ISO/IEC 23894",
                       "ISO/IEC 5338", "EU AI Act", "SR 11-7")


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补 AI 治理登记）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _evidence_issues(root: str, refs: Any, where: str) -> List[str]:
    issues: List[str] = []
    if not isinstance(refs, list) or not refs:
        return ["%s 缺 evidence（%s 控制点必须绑定真实件）" % (where, GUIDE)]
    for rel in refs:
        if not (Path(root) / str(rel)).exists():
            issues.append("%s 的 evidence 不在场：%s" % (where, rel))
    return issues


def _scope_issues(scope: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for field in ("system_purpose", "affected_parties", "out_of_scope", "claims_boundary"):
        if not scope.get(field):
            out.append("scope 缺 %s" % field)
    if not isinstance(scope.get("affected_parties"), list) or len(scope["affected_parties"]) < 2:
        out.append("scope.affected_parties 至少登记两类受影响方")
    boundary = " ".join(str(x) for x in scope.get("claims_boundary") or [])
    if "不声称" not in boundary:
        out.append("scope.claims_boundary 必须显式写「不声称合规/认证」")
    return out


def _missing_fields(record: Dict[str, Any], fields) -> List[str]:
    return [f for f in fields if not str(record.get(f) or "").strip()]


def _criteria_issues(root: str, criteria: List[Any]) -> List[str]:
    out: List[str] = []
    ids = [str(c.get("id")) for c in criteria if isinstance(c, dict)]
    if len(ids) < 4 or len(ids) != len(set(ids)):
        out.append("impact_assessment.criteria 至少 4 项且 id 唯一（%s）" % GUIDE)
    for item in criteria:
        if not isinstance(item, dict):
            out.append("criteria 含非对象")
            continue
        for field in _missing_fields(item, ("id", "question", "answer")):
            out.append("criteria %s 缺 %s" % (item.get("id"), field))
        out += _evidence_issues(root, item.get("evidence"), "criteria " + str(item.get("id")))
    return out


def _impact_block_issues(root: str, impact: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("human_oversight", "transparency", "recourse"):
        block = impact.get(key) or {}
        if not str(block.get("mechanism") or "").strip():
            out.append("impact_assessment.%s 缺 mechanism" % key)
        out += _evidence_issues(root, block.get("evidence"), "impact_assessment." + key)
    return out


def _risk_row_issues(root: str, risk: Dict[str, Any], rid: str) -> List[str]:
    out: List[str] = []
    for field in _missing_fields(risk, ("risk", "category", "likelihood", "impact",
                                       "mitigation", "owner")):
        out.append("风险 %s 缺 %s" % (rid, field))
    for field in ("likelihood", "impact"):
        if str(risk.get(field)) not in RISK_LEVELS:
            out.append("风险 %s 的 %s 非法：%s" % (rid, field, risk.get(field)))
    status = str(risk.get("status"))
    if status not in STATUSES:
        out.append("风险 %s 的 status 非法：%s" % (rid, status))
    if status in ("partial", "planned") and str(risk.get("planned_gate")) not in GATES:
        out.append("风险 %s 标 %s 但缺 planned_gate" % (rid, status))
    out += _evidence_issues(root, risk.get("evidence"), "风险 " + rid)
    return out


def _risk_issues(root: str, risks: List[Any]) -> List[str]:
    out: List[str] = []
    rids = [str(r.get("id")) for r in risks if isinstance(r, dict)]
    if len(rids) < 4:
        out.append("model_risk_register 至少 4 条（%s 覆盖 GOVERN/MAP/MEASURE/MANAGE）" % GUIDE)
    if len(rids) != len(set(rids)):
        out.append("model_risk_register id 重复：%s" % rids)
    for risk in risks:
        if not isinstance(risk, dict):
            out.append("model_risk_register 含非对象")
            continue
        out += _risk_row_issues(root, risk, str(risk.get("id")))
    return out


def _framework_issues(mapping: List[Any]) -> List[str]:
    frameworks = " ".join(str(m.get("framework")) for m in mapping if isinstance(m, dict))
    out: List[str] = []
    for need in EXPECTED_FRAMEWORKS:
        if need not in frameworks:
            out.append("监管映射缺框架：%s（%s 补一行机制对照）" % (need, GUIDE))
    return out


def _mapping_issues(root: str, mapping: List[Any]) -> List[str]:
    out: List[str] = []
    for row in mapping:
        if not isinstance(row, dict):
            out.append("regulatory_mapping 含非对象")
            continue
        fid = str(row.get("framework"))
        if str(row.get("claim")) not in CLAIMS:
            out.append("映射 %s 的 claim 非法：%s（只允许 %s；不声称合规）"
                       % (fid, row.get("claim"), list(CLAIMS)))
        if not isinstance(row.get("clauses"), list) or not row.get("clauses"):
            out.append("映射 %s 缺 clauses" % fid)
        out += _evidence_issues(root, row.get("evidence"), "映射 " + fid)
    return out


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    issues += _scope_issues(doc.get("scope") or {})
    impact = doc.get("impact_assessment") or {}
    issues += _criteria_issues(root, impact.get("criteria") or [])
    issues += _impact_block_issues(root, impact)
    issues += _risk_issues(root, doc.get("model_risk_register") or [])
    mapping = doc.get("regulatory_mapping") or []
    issues += _framework_issues(mapping)
    issues += _mapping_issues(root, mapping)
    return issues


def risk_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    """风险面摘要（人读/机读共用）：按状态与等级计数。"""
    risks = [r for r in doc.get("model_risk_register") or [] if isinstance(r, dict)]
    by_status: Dict[str, int] = {}
    high = 0
    for risk in risks:
        by_status[str(risk.get("status"))] = by_status.get(str(risk.get("status")), 0) + 1
        if str(risk.get("impact")) == "high" and str(risk.get("status")) != "enforced":
            high += 1
    return {"risks": len(risks), "by_status": by_status,
            "high_open": high, "frameworks": len(doc.get("regulatory_mapping") or [])}
