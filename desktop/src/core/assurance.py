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


def validate_claims(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    goals = doc.get("goals") or []
    gids = [str(g.get("id")) for g in goals if isinstance(g, dict)]
    if gids != list(GOALS):
        issues.append("goals 必须恰为 %s（实际 %s；%s 补/改）" % (list(GOALS), gids, GUIDE))
    args = doc.get("arguments") or []
    aids = [str(a.get("id")) for a in args if isinstance(a, dict)]
    if aids != list(ARGUMENTS):
        issues.append("arguments 必须恰为 %s（实际 %s）" % (list(ARGUMENTS), aids))
    if len(aids) != len(set(aids)):
        issues.append("argument id 重复：%s" % aids)
    arg_map = {str(a.get("id")): a for a in args if isinstance(a, dict)}
    for goal in goals:
        if not isinstance(goal, dict):
            issues.append("goals 含非对象")
            continue
        gid = str(goal.get("id"))
        if not str(goal.get("claim") or "").strip():
            issues.append("%s 缺 claim" % gid)
        if str(goal.get("status")) not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (gid, goal.get("status")))
        for aid in goal.get("arguments") or []:
            if aid not in arg_map:
                issues.append("%s 引用了不存在的论证：%s" % (gid, aid))
        for gap in goal.get("open") or []:
            if not any(str(g.get("id")) == gap for g in doc.get("gaps") or []):
                issues.append("%s 的 open 缺口未在 gaps 登记：%s" % (gid, gap))
    gaps = {str(g.get("id")): g for g in doc.get("gaps") or [] if isinstance(g, dict)}
    for gap_id, gap in gaps.items():
        if not str(gap.get("text") or "").strip():
            issues.append("缺口 %s 缺 text" % gap_id)
        if not str(gap.get("owner") or "").strip():
            issues.append("缺口 %s 缺 owner（%s 未关闭项必须有 owner）" % (gap_id, GUIDE))
        if str(gap.get("status")) not in ("open", "accepted-risk", "closed"):
            issues.append("缺口 %s 的 status 非法：%s" % (gap_id, gap.get("status")))
    for aid, arg in arg_map.items():
        if str(arg.get("status")) not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (aid, arg.get("status")))
        evidence = arg.get("evidence") or []
        if not isinstance(evidence, list) or not evidence:
            issues.append("%s 缺 evidence（%s 论证必须有真实证据）" % (aid, GUIDE))
        for rel in evidence:
            if not _exists(root, str(rel)):
                issues.append("%s 的 evidence 不在场：%s" % (aid, rel))
        if str(arg.get("status")) == "supported":
            if len(evidence) < 2:
                issues.append("%s 标 supported 但证据少于 2 件" % aid)
            if not any(str(x).startswith(TEST_EVIDENCE) for x in evidence):
                issues.append("%s 标 supported 但缺测试/门禁证据（%s 测试通过不能替代论证）"
                              % (aid, GUIDE))
        else:
            open_ref = str(arg.get("open") or "")
            if not open_ref:
                issues.append("%s 标 %s 但缺 open（缺口 id）" % (aid, arg.get("status")))
            elif open_ref not in gaps:
                issues.append("%s 的 open 缺口未在 gaps 登记：%s" % (aid, open_ref))
        if not str(arg.get("assumption") or "").strip():
            issues.append("%s 缺 assumption（论证须写成立假设）" % aid)
        if not str(arg.get("rebuttal") or "").strip():
            issues.append("%s 缺 rebuttal（论证须可被反驳）" % aid)
    for group in ("assumptions", "rebuttals"):
        ids = [str(x.get("id")) for x in doc.get(group) or [] if isinstance(x, dict)]
        if len(ids) != len(set(ids)):
            issues.append("%s id 重复：%s" % (group, ids))
    for asm in doc.get("assumptions") or []:
        if not str(asm.get("owner") or "").strip():
            issues.append("假设 %s 缺 owner" % asm.get("id"))
    return issues


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
        if not isinstance(risk, dict):
            issues.append("risks 含非对象")
            continue
        rid = str(risk.get("id"))
        for field in ("title", "owner", "trigger", "mitigation", "review"):
            if not str(risk.get(field) or "").strip():
                issues.append("风险 %s 缺 %s" % (rid, field))
        for field in ("probability", "impact"):
            if str(risk.get(field)) not in SCALE:
                issues.append("风险 %s 的 %s 非法：%s" % (rid, field, risk.get(field)))
        if str(risk.get("status")) not in RAID_STATUSES:
            issues.append("风险 %s 的 status 非法：%s" % (rid, risk.get("status")))
    for group, prefix, fields in (
            ("assumptions", "AS", ("title", "owner", "trigger", "mitigation", "review")),
            ("issues", "I", ("title", "owner", "status")),
            ("dependencies", "D", ("title", "owner", "trigger", "mitigation", "review"))):
        items = doc.get(group) or []
        if not items:
            issues.append("缺 %s（%s RAID 四类都要登记）" % (group, GUIDE))
        for item in items:
            if not isinstance(item, dict):
                issues.append("%s 含非对象" % group)
                continue
            iid = str(item.get("id"))
            if not iid.startswith(prefix):
                issues.append("%s 的 id 前缀应 %s：%s" % (group, prefix, iid))
            for field in fields:
                if not str(item.get(field) or "").strip():
                    issues.append("%s %s 缺 %s" % (group, iid, field))
    stakeholders = doc.get("stakeholders") or []
    if len(stakeholders) < 3:
        issues.append("stakeholders 至少 3 类（%s）" % GUIDE)
    change = doc.get("change_control") or {}
    for field in ("process", "record", "evidence"):
        if not str(change.get(field) or "").strip():
            issues.append("change_control 缺 %s" % field)
    if not _exists(root, str(change.get("evidence") or "")):
        issues.append("change_control.evidence 不在场：%s" % change.get("evidence"))
    return issues


def link_issues(claims: Dict[str, Any], raid: Dict[str, Any]) -> List[str]:
    """缺口 ↔ RAID issues 一一绑定（双向；缺口不能只在保证案例里出现）。"""
    issues: List[str] = []
    gap_ids = {str(g.get("id")) for g in claims.get("gaps") or [] if isinstance(g, dict)}
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
    gap_ids = {str(g.get("id")) for g in claims.get("gaps") or [] if isinstance(g, dict)}
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
