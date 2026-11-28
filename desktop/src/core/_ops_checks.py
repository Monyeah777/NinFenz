"""core.ops 私有子模块：运行面/供应商面的形状判据（供 core.ops.validate_* 复用）。

门面 core.ops 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core import ops as _ops


# ---------------------------------------------------------------- ops 面
def _severity_entry_issues(sev: Dict[str, Any]) -> List[str]:
    """S0–S3 每条分级的 definition/response/disclosure 判据。"""
    out: List[str] = []
    for key in _ops.SEVERITIES:
        entry = sev.get(key) or {}
        for field in ("definition", "response", "disclosure"):
            if not str(entry.get(field) or "").strip():
                out.append("%s 缺 %s（%s 分级必须可执行）" % (key, field, _ops.GUIDE))
    return out


def _runbook_head_issues(steps: List[Any], ids: List[str]) -> List[str]:
    """runbook 步数与 id 完整性判据。"""
    out: List[str] = []
    if not steps:
        out.append("incident_runbook 缺 steps（%s 至少 5 步）" % _ops.GUIDE)
    if len(ids) != len(set(ids)):
        out.append("incident_runbook step id 重复：%s" % ids)
    if tuple(ids) != _ops.EXPECTED_RUNBOOK:
        out.append("incident_runbook 步骤必须恰为 %s（实际 %s；%s 补齐缺失步骤）"
                   % (list(_ops.EXPECTED_RUNBOOK), ids, _ops.GUIDE))
    return out


def _runbook_step_issues(step: Any, root: str) -> List[str]:
    """单个 runbook 步判据（必填字段 / 证据在场）。"""
    if not isinstance(step, dict):
        return ["runbook step 含非对象"]
    out: List[str] = []
    for field in ("id", "name", "action", "evidence"):
        if not str(step.get(field) or "").strip():
            out.append("runbook %s 缺 %s" % (step.get("id"), field))
    rel = str(step.get("evidence") or "")
    if rel and not _ops._exists(root, rel):
        out.append("runbook %s 的 evidence 不在场：%s" % (step.get("id"), rel))
    return out


def _runbook_steps_issues(steps: List[Any], root: str) -> List[str]:
    """逐 runbook 步判据。"""
    out: List[str] = []
    for step in steps:
        out.extend(_runbook_step_issues(step, root))
    return out


def _ops_runbook_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """incident_runbook 判据（head + 逐 step）。"""
    runbook = doc.get("incident_runbook") or {}
    steps = runbook.get("steps") or []
    ids = [str(s.get("id")) for s in steps if isinstance(s, dict)]
    out = _runbook_head_issues(steps, ids)
    out.extend(_runbook_steps_issues(steps, root))
    return out


def _disclosure_text_issues(disc: Dict[str, Any], root: str) -> List[str]:
    """披露通道与策略引用判据。"""
    out: List[str] = []
    if not str(disc.get("channel") or "").strip():
        out.append("disclosure 缺 channel（私密通道）")
    ref = str(disc.get("policy_ref") or "")
    if not ref or not _ops._exists(root, ref):
        out.append("disclosure.policy_ref 不在场：%s（%s 指向 SECURITY.md）" % (ref, _ops.GUIDE))
    return out


def _disclosure_days_issues(ack: Any, disclose: Any) -> List[str]:
    """披露时限口径判据（ack 1..30 / disclose ≥ ack 且 ≤365）。"""
    out: List[str] = []
    if not (isinstance(ack, int) and not isinstance(ack, bool) and 0 < ack <= 30):
        out.append("disclosure.ack_within_days 必须是 1..30 的整数（逻辑口径）")
    if not (isinstance(disclose, int) and not isinstance(disclose, bool)
            and isinstance(ack, int) and ack <= disclose <= 365):
        out.append("disclosure.disclose_within_days 必须 ≥ ack 且 ≤365（逻辑口径）")
    return out


def _disclosure_note_issues(disc: Dict[str, Any]) -> List[str]:
    """披露逻辑说明判据。"""
    if not str(disc.get("logic_note") or "").strip():
        return ["disclosure 缺 logic_note（天数是流程口径，不是修复 SLA）"]
    return []


def _ops_disclosure_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """disclosure 判据（通道/引用 → 时限 → 说明，判序同原实现）。"""
    disc = doc.get("disclosure") or {}
    out = _disclosure_text_issues(disc, root)
    out.extend(_disclosure_days_issues(disc.get("ack_within_days"),
                                       disc.get("disclose_within_days")))
    out.extend(_disclosure_note_issues(disc))
    return out


def _slo_head_issues(slo: List[Any], sno: List[str]) -> List[str]:
    """SLO 非空与 id 唯一性判据。"""
    out: List[str] = []
    if not slo:
        out.append("缺 slo（本地优先工具至少有正确/可复现/离线目标）")
    if len(sno) != len(set(sno)):
        out.append("slo id 重复：%s" % sno)
    return out


def _slo_item_issues(item: Any, root: str) -> List[str]:
    """单条 SLO 判据（必填字段 / 证据在场）。"""
    if not isinstance(item, dict):
        return ["slo 含非对象"]
    out: List[str] = []
    for field in ("id", "name", "objective", "measurement", "evidence"):
        if not str(item.get(field) or "").strip():
            out.append("slo %s 缺 %s" % (item.get("id"), field))
    rel = str(item.get("evidence") or "")
    if rel and not _ops._exists(root, rel):
        out.append("slo %s 的 evidence 不在场：%s" % (item.get("id"), rel))
    return out


def _ops_slo_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """slo 判据（head + 逐条）。"""
    slo = doc.get("slo") or []
    sno = [str(s.get("id")) for s in slo if isinstance(s, dict)]
    out = _slo_head_issues(slo, sno)
    for item in slo:
        out.extend(_slo_item_issues(item, root))
    return out


def _bcp_asset_issues(asset: Any) -> List[str]:
    """单个 BCP 资产判据（六字段齐全）。"""
    if not isinstance(asset, dict):
        return ["bcp.assets 含非对象"]
    out: List[str] = []
    for field in ("id", "name", "backup", "rto", "rpo", "restore"):
        if not str(asset.get(field) or "").strip():
            out.append("bcp 资产 %s 缺 %s" % (asset.get("id"), field))
    return out


def _bcp_scenario_issues(scen: Any) -> List[str]:
    """单个 BCP 场景判据（五字段 / drill 词表 / steps 非空）。"""
    if not isinstance(scen, dict):
        return ["bcp.scenarios 含非对象"]
    out: List[str] = []
    for field in ("id", "trigger", "impact", "expected", "drill"):
        if not str(scen.get(field) or "").strip():
            out.append("bcp 场景 %s 缺 %s" % (scen.get("id"), field))
    if scen.get("drill") not in ("recovery", "tabletop"):
        out.append("bcp 场景 %s 的 drill 非法：%s" % (scen.get("id"), scen.get("drill")))
    if not isinstance(scen.get("steps"), list) or not scen.get("steps"):
        out.append("bcp 场景 %s 缺 steps" % scen.get("id"))
    return out


def _ops_bcp_issues(doc: Dict[str, Any]) -> List[str]:
    """bcp 判据（head / 逐资产 / 逐场景）。"""
    bcp = doc.get("bcp") or {}
    assets = bcp.get("assets") or []
    scenarios = bcp.get("scenarios") or []
    out: List[str] = []
    if not assets:
        out.append("bcp 缺 assets（备份/RTO/RPO 要有对象）")
    if not scenarios:
        out.append("bcp 缺 scenarios（至少覆盖磁盘/密钥/外部依赖）")
    for asset in assets:
        out.extend(_bcp_asset_issues(asset))
    for scen in scenarios:
        out.extend(_bcp_scenario_issues(scen))
    return out


def _drill_issues(drill: Any) -> List[str]:
    """单条演练判据（id/runner / covers 非空）。"""
    if not isinstance(drill, dict):
        return ["drills 含非对象"]
    out: List[str] = []
    if not str(drill.get("id")) or not str(drill.get("runner")):
        out.append("drill 缺 id/runner：%s" % drill.get("id"))
    if not isinstance(drill.get("covers"), list) or not drill.get("covers"):
        out.append("drill %s 缺 covers" % drill.get("id"))
    return out


def _drills_head_issues(drills: List[Any], kinds: set) -> List[str]:
    """演练类型覆盖判据。"""
    if kinds != set(_ops.DR_KINDS):
        return ["drills 必须覆盖 %s（实际 %s）" % (list(_ops.DR_KINDS), sorted(kinds))]
    return []


def _ops_bcp_drills_issues(doc: Dict[str, Any]) -> List[str]:
    """bcp + drills 判据（head / 逐条）。"""
    out = _ops_bcp_issues(doc)
    drills = doc.get("drills") or []
    kinds = {str(d.get("kind")) for d in drills if isinstance(d, dict)}
    out.extend(_drills_head_issues(drills, kinds))
    for drill in drills:
        out.extend(_drill_issues(drill))
    return out


def _ops_issues(doc: Dict[str, Any], root: str) -> List[str]:
    """ops 面全部判据（severity → runbook → disclosure → slo → bcp/drills）。"""
    issues: List[str] = []
    issues.extend(_severity_entry_issues(doc.get("severity_vocabulary")))
    issues.extend(_ops_runbook_issues(doc, root))
    issues.extend(_ops_disclosure_issues(doc, root))
    issues.extend(_ops_slo_issues(doc, root))
    issues.extend(_ops_bcp_drills_issues(doc))
    return issues


# ---------------------------------------------------------------- vendors 面
def _vendor_head_issues(doc: Dict[str, Any]) -> List[str]:
    """vendor 词表 / 清单非空 / id 唯一性判据。"""
    out: List[str] = []
    if not isinstance(doc.get("kind_vocabulary"), list) or not doc.get("kind_vocabulary"):
        out.append("缺 kind_vocabulary")
    if (not isinstance(doc.get("criticality_vocabulary"), list)
            or not doc.get("criticality_vocabulary")):
        out.append("缺 criticality_vocabulary")
    vendors = doc.get("vendors") or []
    ids = [str(v.get("id")) for v in vendors if isinstance(v, dict)]
    if not vendors:
        out.append("vendors 为空（至少登记托管/依赖/TSA/公共日志/模型 provider）")
    if len(ids) != len(set(ids)):
        out.append("vendor id 重复：%s" % ids)
    return out


def _vendor_fields_issues(ven: Dict[str, Any], vid: str) -> List[str]:
    """vendor 五字段齐全判据。"""
    out: List[str] = []
    for field in ("id", "name", "kind", "criticality", "status"):
        if not str(ven.get(field) or "").strip():
            out.append("vendor %s 缺 %s" % (vid, field))
    return out


def _vendor_vocab_issues(ven: Dict[str, Any], vid: str, kinds: Any,
                         crits: Any, statuses: Any) -> List[str]:
    """vendor kind/criticality/status 词表判据。"""
    out: List[str] = []
    if kinds and ven.get("kind") not in kinds:
        out.append("vendor %s 的 kind 非法：%s" % (vid, ven.get("kind")))
    if crits and ven.get("criticality") not in crits:
        out.append("vendor %s 的 criticality 非法：%s" % (vid, ven.get("criticality")))
    if statuses and ven.get("status") not in statuses:
        out.append("vendor %s 的 status 非法：%s" % (vid, ven.get("status")))
    return out


def _vendor_terms_issues(ven: Dict[str, Any], vid: str, root: str) -> List[str]:
    """vendor data_terms / used_by 判据。"""
    out: List[str] = []
    terms = ven.get("data_terms") or {}
    if terms.get("stores_user_data") is not False:
        out.append("vendor %s 不得声明处理用户数据（本仓本地优先；%s）"
                   % (vid, _ops.GUIDE))
    if not str(terms.get("note") or "").strip():
        out.append("vendor %s 的 data_terms 缺 note" % vid)
    used = ven.get("used_by") or []
    if not used:
        out.append("vendor %s 缺 used_by（能力要落到真实消费点）" % vid)
    for rel in used:
        if not _ops._exists(root, str(rel)):
            out.append("vendor %s 的 used_by 不在场：%s" % (vid, rel))
    return out


def _vendor_attest_issues(ven: Dict[str, Any], vid: str, root: str) -> List[str]:
    """vendor attestation 判据（逐件在场 / 高关键度必须有）。"""
    out: List[str] = []
    att = ven.get("attestation") or []
    for rel in att:
        if not _ops._exists(root, str(rel)):
            out.append("vendor %s 的 attestation 不在场：%s" % (vid, rel))
    if ven.get("criticality") in ("critical", "high") and not att:
        out.append("vendor %s 是 %s，必须有 attestation（SBOM/来源/锚证据）"
                   % (vid, ven.get("criticality")))
    return out


def _vendor_exit_issues(ven: Dict[str, Any], vid: str) -> List[str]:
    """vendor exit_plan 判据（fallback / ≥2 步 / owner）。"""
    out: List[str] = []
    plan = ven.get("exit_plan") or {}
    if not str(plan.get("fallback") or "").strip():
        out.append("vendor %s 的 exit_plan 缺 fallback" % vid)
    steps = plan.get("steps") or []
    if not isinstance(steps, list) or len(steps) < 2:
        out.append("vendor %s 的 exit_plan 至少 2 步" % vid)
    if not str(plan.get("owner") or "").strip():
        out.append("vendor %s 的 exit_plan 缺 owner" % vid)
    return out


def _vendor_issues(ven: Any, root: str, kinds: Any, crits: Any,
                   statuses: Any) -> List[str]:
    """单 vendor 判据（字段/词表/数据条款/证据/退出计划）。"""
    if not isinstance(ven, dict):
        return ["vendors 含非对象"]
    vid = str(ven.get("id"))
    out = _vendor_fields_issues(ven, vid)
    out.extend(_vendor_vocab_issues(ven, vid, kinds, crits, statuses))
    out.extend(_vendor_terms_issues(ven, vid, root))
    out.extend(_vendor_attest_issues(ven, vid, root))
    out.extend(_vendor_exit_issues(ven, vid))
    return out


def _vendor_body_issues(doc: Dict[str, Any], root: str) -> tuple[List[str], List[str]]:
    """逐 vendor 判据 → (ids, issues)。"""
    kinds = doc.get("kind_vocabulary")
    crits = doc.get("criticality_vocabulary")
    statuses = doc.get("status_vocabulary")
    vendors = doc.get("vendors") or []
    ids = [str(v.get("id")) for v in vendors if isinstance(v, dict)]
    out: List[str] = []
    for ven in vendors:
        out.extend(_vendor_issues(ven, root, kinds, crits, statuses))
    return ids, out


def _replacement_drill_issues(drill: Dict[str, Any], ids: List[str]) -> List[str]:
    """单条替换演练判据（covers 非空且只覆盖已登记 vendor）。"""
    out: List[str] = []
    covers = drill.get("covers") or []
    if not covers:
        out.append("replacement drill %s 缺 covers" % drill.get("id"))
    for vid in covers:
        if vid not in ids:
            out.append("replacement drill %s 覆盖了未登记 vendor：%s"
                       % (drill.get("id"), vid))
    return out


def _replacement_drills_issues(doc: Dict[str, Any], ids: List[str]) -> List[str]:
    """replacement_drills 判据（非空 + 逐条）。"""
    drills = doc.get("replacement_drills") or []
    out: List[str] = []
    if not drills:
        out.append("缺 replacement_drills（退出/替换演练要登记）")
    for drill in drills:
        out.extend(_replacement_drill_issues(drill, ids))
    return out


def _vendor_issues_all(doc: Dict[str, Any], root: str) -> List[str]:
    """vendors 面全部判据（head → 逐 vendor → 替换演练）。"""
    issues = _vendor_head_issues(doc)
    ids, body = _vendor_body_issues(doc, root)
    issues.extend(body)
    issues.extend(_replacement_drills_issues(doc, ids))
    return issues
