"""保证案例（GSN/CAE）+ RAID（`nf-assurance-claims/1` + `nf-raid/1`）：把「凭什么可信」做成可核图。

为什么（NF-Final WP-0G，P2 盲区 BL-12）：QA 报告是证据，不是论证。保证案例把
Goal(C) → Argument(A) → Evidence 串起来，并显式写假设/反驳/缺口；RAID 把风险/假设/问题/依赖
与 owner/触发/缓解/复审绑定。本模块的纪律：
- 每条 Argument 必须有**真实证据**；`supported` 至少 2 件且含测试/门禁证据；`partial`/`open`
  /`accepted-risk` 必须写缺口 id，缺口再进 gaps（有 owner/status）；
- 「测试通过」不能替代论证——所以 evidence 必须指向代码/契约/测试/门禁，且论证本身要有
  assumption/rebuttal（可被反驳）；
- RAID：风险 R-01…R-08 与假设/问题/依赖逐条 owner/触发/缓解/复审；问题必须 link 到 gaps，
  两边一一对应（缺口不能只在保证案例里出现而不进 RAID，反之亦然）；
- 不声称合规/认证（伦理面另见 docs/ETHICS.md）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

CLAIMS_SCHEMA = "nf-assurance-claims/1"
RAID_SCHEMA = "nf-raid/1"
CLAIMS_REL = "results/assurance/CLAIMS.json"
RAID_REL = "protocol/raid.json"
GUIDE = "修复指引："
STATUSES = ("supported", "partial", "open", "accepted-risk")
RAID_STATUSES = ("open", "partial", "mitigated", "active", "accepted-risk")
GOALS = ("C0", "C1", "C2", "C3")
ARGUMENTS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8")
RISK_IDS = ("R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-08")
SCALE = ("low", "medium", "high")
TEST_EVIDENCE = ("desktop/tests/", "scripts/", "verify.sh")


def _load(root: str, rel: str, schema: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError("缺 %s（%s 补文件）" % (rel, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(rel + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != schema:
        raise ValueError(rel + " schema 不匹配（" + GUIDE + "需要 " + schema + "）")
    return doc


def load_claims(root: str = ".") -> Dict[str, Any]:
    return _load(root, CLAIMS_REL, CLAIMS_SCHEMA)


def load_raid(root: str = ".") -> Dict[str, Any]:
    return _load(root, RAID_REL, RAID_SCHEMA)


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).exists()


def _goals_head_issues(doc: Dict[str, Any]) -> List[str]:
    """goals 清单与 id 完整性判据。"""
    goals = doc.get("goals") or []
    gids = [str(g.get("id")) for g in goals if isinstance(g, dict)]
    if gids != list(GOALS):
        return ["goals 必须恰为 %s（实际 %s；%s 补/改）" % (list(GOALS), gids, GUIDE)]
    return []


def _arguments_head_issues(doc: Dict[str, Any]) -> List[str]:
    """arguments 清单与 id 唯一性判据。"""
    args = doc.get("arguments") or []
    aids = [str(a.get("id")) for a in args if isinstance(a, dict)]
    out: List[str] = []
    if aids != list(ARGUMENTS):
        out.append("arguments 必须恰为 %s（实际 %s）" % (list(ARGUMENTS), aids))
    if len(aids) != len(set(aids)):
        out.append("argument id 重复：%s" % aids)
    return out


def _claim_graph(doc: Dict[str, Any]) -> Tuple[List[Any], Dict[str, Any], Dict[str, Any]]:
    """goals / argument id→对象 / 缺口 id→对象 三视图。"""
    goals = doc.get("goals") or []
    args = doc.get("arguments") or []
    arg_map = {str(a.get("id")): a for a in args if isinstance(a, dict)}
    gaps = {str(g.get("id")): g for g in doc.get("gaps") or [] if isinstance(g, dict)}
    return goals, arg_map, gaps


def _goal_gap_issues(gid: str, goal: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    """目标 open 缺口必须在 gaps 登记。"""
    out: List[str] = []
    for gap in goal.get("open") or []:
        if not any(str(g.get("id")) == gap for g in doc.get("gaps") or []):
            out.append("%s 的 open 缺口未在 gaps 登记：%s" % (gid, gap))
    return out


def _goal_issues(goal: Any, arg_map: Dict[str, Any], doc: Dict[str, Any]) -> List[str]:
    """单目标判据（claim/status/引用论证/open 缺口登记）。"""
    if not isinstance(goal, dict):
        return ["goals 含非对象"]
    gid = str(goal.get("id"))
    out: List[str] = []
    if not str(goal.get("claim") or "").strip():
        out.append("%s 缺 claim" % gid)
    if str(goal.get("status")) not in STATUSES:
        out.append("%s 的 status 非法：%s" % (gid, goal.get("status")))
    for aid in goal.get("arguments") or []:
        if aid not in arg_map:
            out.append("%s 引用了不存在的论证：%s" % (gid, aid))
    out.extend(_goal_gap_issues(gid, goal, doc))
    return out


def _gap_issues(gap_id: str, gap: Dict[str, Any]) -> List[str]:
    """单缺口判据（text / owner / status 词表）。"""
    out: List[str] = []
    if not str(gap.get("text") or "").strip():
        out.append("缺口 %s 缺 text" % gap_id)
    if not str(gap.get("owner") or "").strip():
        out.append("缺口 %s 缺 owner（%s 未关闭项必须有 owner）" % (gap_id, GUIDE))
    if str(gap.get("status")) not in ("open", "accepted-risk", "closed"):
        out.append("缺口 %s 的 status 非法：%s" % (gap_id, gap.get("status")))
    return out


def _arg_evidence_issues(aid: str, evidence: Any, root: str) -> List[str]:
    """论证证据判据（列表非空 / 逐件在场）。"""
    out: List[str] = []
    if not isinstance(evidence, list) or not evidence:
        out.append("%s 缺 evidence（%s 论证必须有真实证据）" % (aid, GUIDE))
    for rel in evidence:
        if not _exists(root, str(rel)):
            out.append("%s 的 evidence 不在场：%s" % (aid, rel))
    return out


def _arg_support_issues(aid: str, arg: Dict[str, Any], evidence: list,
                        gaps: Dict[str, Any]) -> List[str]:
    """supported / 非 supported 的支撑与缺口登记判据。"""
    if str(arg.get("status")) == "supported":
        out: List[str] = []
        if len(evidence) < 2:
            out.append("%s 标 supported 但证据少于 2 件" % aid)
        if not any(str(x).startswith(TEST_EVIDENCE) for x in evidence):
            out.append("%s 标 supported 但缺测试/门禁证据（%s 测试通过不能替代论证）"
                       % (aid, GUIDE))
        return out
    open_ref = str(arg.get("open") or "")
    if not open_ref:
        return ["%s 标 %s 但缺 open（缺口 id）" % (aid, arg.get("status"))]
    if open_ref not in gaps:
        return ["%s 的 open 缺口未在 gaps 登记：%s" % (aid, open_ref)]
    return []


def _arg_text_issues(aid: str, arg: Dict[str, Any]) -> List[str]:
    """论证假设/反驳文本判据。"""
    out: List[str] = []
    if not str(arg.get("assumption") or "").strip():
        out.append("%s 缺 assumption（论证须写成立假设）" % aid)
    if not str(arg.get("rebuttal") or "").strip():
        out.append("%s 缺 rebuttal（论证须可被反驳）" % aid)
    return out


def _arg_issues(aid: str, arg: Dict[str, Any], root: str,
                gaps: Dict[str, Any]) -> List[str]:
    """单论证判据（status / 证据 / 支撑 / 假设 / 反驳）。"""
    out: List[str] = []
    if str(arg.get("status")) not in STATUSES:
        out.append("%s 的 status 非法：%s" % (aid, arg.get("status")))
    evidence = arg.get("evidence") or []
    out.extend(_arg_evidence_issues(aid, evidence, root))
    out.extend(_arg_support_issues(aid, arg, evidence, gaps))
    out.extend(_arg_text_issues(aid, arg))
    return out


def _dup_id_issues(doc: Dict[str, Any]) -> List[str]:
    """assumptions / rebuttals 的 id 唯一性判据。"""
    out: List[str] = []
    for group in ("assumptions", "rebuttals"):
        ids = [str(x.get("id")) for x in doc.get(group) or [] if isinstance(x, dict)]
        if len(ids) != len(set(ids)):
            out.append("%s id 重复：%s" % (group, ids))
    return out


def _assumption_owner_issues(doc: Dict[str, Any]) -> List[str]:
    """假设 owner 判据。"""
    out: List[str] = []
    for asm in doc.get("assumptions") or []:
        if not str(asm.get("owner") or "").strip():
            out.append("假设 %s 缺 owner" % asm.get("id"))
    return out


def validate_claims(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    issues.extend(_goals_head_issues(doc))
    issues.extend(_arguments_head_issues(doc))
    goals, arg_map, gaps = _claim_graph(doc)
    for goal in goals:
        issues.extend(_goal_issues(goal, arg_map, doc))
    for gap_id, gap in gaps.items():
        issues.extend(_gap_issues(gap_id, gap))
    for aid, arg in arg_map.items():
        issues.extend(_arg_issues(aid, arg, root, gaps))
    issues.extend(_dup_id_issues(doc))
    issues.extend(_assumption_owner_issues(doc))
    return issues


def _risk_issues(risk: Any) -> List[str]:
    """单条风险形状 → 问题清单。"""
    if not isinstance(risk, dict):
        return ["risks 含非对象"]
    rid = str(risk.get("id"))
    out: List[str] = []
    for field in ("title", "owner", "trigger", "mitigation", "review"):
        if not str(risk.get(field) or "").strip():
            out.append("风险 %s 缺 %s" % (rid, field))
    for field in ("probability", "impact"):
        if str(risk.get(field)) not in SCALE:
            out.append("风险 %s 的 %s 非法：%s" % (rid, field, risk.get(field)))
    if str(risk.get("status")) not in RAID_STATUSES:
        out.append("风险 %s 的 status 非法：%s" % (rid, risk.get("status")))
    return out


def _group_issues(group: str, prefix: str, fields: Tuple[str, ...],
                  doc: Dict[str, Any]) -> List[str]:
    """RAID 单个登记类（assumptions/issues/dependencies）→ 问题清单。"""
    items = doc.get(group) or []
    out: List[str] = []
    if not items:
        out.append("缺 %s（%s RAID 四类都要登记）" % (group, GUIDE))
    for item in items:
        if not isinstance(item, dict):
            out.append("%s 含非对象" % group)
            continue
        iid = str(item.get("id"))
        if not iid.startswith(prefix):
            out.append("%s 的 id 前缀应 %s：%s" % (group, prefix, iid))
        for field in fields:
            if not str(item.get(field) or "").strip():
                out.append("%s %s 缺 %s" % (group, iid, field))
    return out


def _raid_tail_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """stakeholders + change_control 判据。"""
    out: List[str] = []
    stakeholders = doc.get("stakeholders") or []
    if len(stakeholders) < 3:
        out.append("stakeholders 至少 3 类（%s）" % GUIDE)
    change = doc.get("change_control") or {}
    for field in ("process", "record", "evidence"):
        if not str(change.get(field) or "").strip():
            out.append("change_control 缺 %s" % field)
    if not _exists(root, str(change.get("evidence") or "")):
        out.append("change_control.evidence 不在场：%s" % change.get("evidence"))
    return out


def validate_raid(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    matrix = doc.get("risk_matrix") or {}
    if tuple(matrix.get("scale") or []) != SCALE:
        issues.append("risk_matrix.scale 必须为 %s" % (list(SCALE),))
    risks = doc.get("risks") or []
    rids = [str(r.get("id")) for r in risks if isinstance(r, dict)]
    if rids != list(RISK_IDS):
        issues.append("risks 必须恰为 %s（实际 %s）" % (list(RISK_IDS), rids))
    for risk in risks:
        issues.extend(_risk_issues(risk))
    for group, prefix, fields in (
            ("assumptions", "AS", ("title", "owner", "trigger", "mitigation", "review")),
            ("issues", "I", ("title", "owner", "status")),
            ("dependencies", "D", ("title", "owner", "trigger", "mitigation", "review"))):
        issues.extend(_group_issues(group, prefix, fields, doc))
    issues.extend(_raid_tail_issues(doc, root))
    return issues


def _gap_ids(claims: Dict[str, Any]) -> set:
    """保证案例登记的缺口 id 集合。"""
    return {str(g.get("id")) for g in claims.get("gaps") or [] if isinstance(g, dict)}


def link_issues(claims: Dict[str, Any], raid: Dict[str, Any]) -> List[str]:
    """缺口 ↔ RAID issues 一一绑定（双向；缺口不能只在保证案例里出现）。"""
    issues: List[str] = []
    gap_ids = _gap_ids(claims)
    linked = {}
    for item in raid.get("issues") or []:
        gap = str((item or {}).get("link_gap") or "")
        if gap:
            linked[gap] = str(item.get("id"))
    for gap in sorted(gap_ids):
        if gap not in linked:
            issues.append("缺口 %s 未在 RAID issues 里 link（%s 缺口必须进 RAID）" % (gap, GUIDE))
    for gap in sorted(set(linked) - gap_ids):
        issues.append("RAID issue %s link 了未登记的缺口：%s" % (linked[gap], gap))
    return issues


def audit(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """保证案例 + RAID 审计（含交叉绑定）→ (issues, facts)。"""
    try:
        claims = load_claims(root)
        raid = load_raid(root)
    except ValueError as exc:
        return [str(exc)], {}
    issues = validate_claims(claims, root) + validate_raid(raid, root)
    issues += link_issues(claims, raid)
    gap_ids = _gap_ids(claims)
    facts = {
        "goals": len(claims.get("goals") or []),
        "arguments": len(claims.get("arguments") or []),
        "gaps": len(gap_ids),
        "risks": len(raid.get("risks") or []),
        "issues": len(raid.get("issues") or []),
        "dependencies": len(raid.get("dependencies") or []),
        "stakeholders": len(raid.get("stakeholders") or []),
    }
    return issues, facts
