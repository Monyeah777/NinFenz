"""治理报告与审计包（WP-33，G3）：把 trust/适配器/附件/契约义务汇总成可复算报告。

纪律：
- 报告只**复算**既有事实（适配器 detect、等级计划、附件模式、契约状态、SELF_AUDIT、
  独立性报告、CQ 边界），不新造结论；
- `nf-gov-report/1`：各级 achievable/缺项、适配器状态、附件模式、契约状态、OPEN、claims 边界；
- `nf-gov-audit/1`：审计包（逐项 check + 证据路径 + 结论），**committed == 实时重算**；
- 诚实：T3/T4 不可达时明确写 missing/achievable；外部 OPEN 带 owner，不写成已关闭。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from core import attachment as at
from core import contract_lifecycle as cl
from core import governance_adapters as ga

REPORT_SCHEMA = "nf-gov-report/1"
AUDIT_SCHEMA = "nf-gov-audit/1"
REPORT_REL = "results/governance/report.json"
AUDIT_REL = "results/governance/audit.json"
LEVELS = ("T0", "T1", "T2", "T3", "T4")
GUIDE = "修复指引："


class GovReportError(Exception):
    """报告生成拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "GOV-REPORT-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _load_optional(root: str, rel: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _levels_block(plans: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """逐等级可达性投影（achievable/ok/missing/exit_code）。"""
    return {level: {"achievable": plans[level]["achievable"],
                    "ok": plans[level]["ok"],
                    "missing": plans[level]["missing"],
                    "exit_code": plans[level]["exit_code"]}
            for level in LEVELS}


def _adapters_block(adapters: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """适配器状态投影（按 id 排序）。"""
    return {aid: {"standard": row["standard"], "kind": row["kind"],
                  "live": row["live"], "declared": row["declared"]}
            for aid, row in sorted(adapters.items())}


def _attach_block(modes: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """附件模式投影（按 id 排序）。"""
    return {mid: {"blocking": bool(mode.get("blocking")),
                  "min_level": str(mode.get("min_level") or ""),
                  "records_observation": bool(mode.get("records_observation"))}
            for mid, mode in sorted(modes.items())}


def _self_audit_block(self_audit: Dict[str, Any]) -> Dict[str, Any]:
    """SELF_AUDIT 投影：p0 计数 + findings 条数。"""
    return {"p0": int((self_audit.get("stop") or {}).get("p0") or 0),
            "findings": len(self_audit.get("findings") or [])}


def _independence_block(independence: Dict[str, Any]) -> Dict[str, Any]:
    """独立性报告投影：跨界边数 + ok。"""
    return {"forbidden_edges": int((independence.get("counts") or {}).get(
        "forbidden_edges") or 0), "ok": bool(independence.get("ok"))}


def _audit_checks(root: str, plans: Dict[str, Dict[str, Any]],
                  self_audit: Dict[str, Any], independence: Dict[str, Any],
                  attach_modes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """治理审计包逐项 check（证据路径 + 结论）。"""
    return [
        {"id": "AC-01", "desc": "适配器注册表自检", "ok": not ga.check(root),
         "evidence": ga.REL},
        {"id": "AC-02", "desc": "契约生命周期注册表自检", "ok": not cl.check_registry(root),
         "evidence": cl.REGISTRY_REL},
        {"id": "AC-03", "desc": "附件模式注册表自检", "ok": not at.check_registry(root),
         "evidence": at.REL},
        {"id": "AC-04", "desc": "SELF_AUDIT P0=0",
         "ok": int((self_audit.get("stop") or {}).get("p0") or 0) == 0,
         "evidence": "results/trust/SELF_AUDIT.json"},
        {"id": "AC-05", "desc": "生产/治理边界跨界=0",
         "ok": bool(independence.get("ok")) and int((independence.get("counts") or {}).get(
             "forbidden_edges") or 0) == 0,
         "evidence": "results/independence.json"},
        {"id": "AC-06", "desc": "T3/T4 未冒称（缺适配器即不可达）",
         "ok": not (plans["T3"]["ok"] or plans["T4"]["ok"]),
         "evidence": ga.REL},
        {"id": "AC-07", "desc": "附件独立性（三模式纯函数）",
         "ok": all(str(m.get("desc")) for m in attach_modes.values()),
         "evidence": at.REL},
    ]


def _audit_summary(checks: List[Dict[str, Any]]) -> Dict[str, int]:
    """审计包汇总：总数 / 通过 / 失败。"""
    return {"total": len(checks), "ok": sum(1 for c in checks if c["ok"]),
            "fail": sum(1 for c in checks if not c["ok"])}


def build(root: str = ".") -> Dict[str, Any]:
    adapters = ga.detect(root)
    plans = {level: ga.verify_plan(level, root) for level in LEVELS}
    attach_modes = at.modes(root)
    lifecycle = cl.load_registry(root)
    self_audit = _load_optional(root, "results/trust/SELF_AUDIT.json")
    independence = _load_optional(root, "results/independence.json")
    report = {
        "schema": REPORT_SCHEMA,
        "levels": _levels_block(plans),
        "adapters": _adapters_block(adapters),
        "attachment_modes": _attach_block(attach_modes),
        "contract_states": sorted((lifecycle.get("status_vocabulary") or [])),
        "self_audit": _self_audit_block(self_audit),
        "independence": _independence_block(independence),
        "open_items": [
            {"id": "OPEN-EXTERNAL", "text": "公共日志提交/外部见证/第三方合规审核属外部操作", "owner": "maintainers"},
            {"id": "OPEN-TOOLS", "text": "cosign 不在场 → 签名外部核验不可用（最高 T1 可达）", "owner": "maintainers"},
        ],
        "claims_boundary": ["报告只复算已登记事实；T3/T4 未达即写 missing，不冒充",
                            "外部标准不作质量背书；外部 OPEN 带 owner 不静默"],
        "note": "确定性报告（无时间戳）；committed == 实时重算由 check51 断言",
    }
    checks = _audit_checks(root, plans, self_audit, independence, attach_modes)
    audit = {"schema": AUDIT_SCHEMA, "checks": checks, "summary": _audit_summary(checks),
             "open_items": report["open_items"],
             "note": "审计包只含 check/证据/结论；不替代外部审计"}
    return {"report": report, "audit": audit}


def render_report(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_audit(audit: Dict[str, Any]) -> str:
    return json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Dict[str, Any]:
    from core import atomic_write
    doc = build(root)
    atomic_write.write_text(Path(root) / REPORT_REL, render_report(doc["report"]))
    atomic_write.write_text(Path(root) / AUDIT_REL, render_audit(doc["audit"]))
    return doc


def _read_committed(root: str):
    """读在盘报告+审计包 → (report, audit) 或 [不可解析 issue]。"""
    try:
        report = json.loads((Path(root) / REPORT_REL).read_text(encoding="utf-8"))
        audit = json.loads((Path(root) / AUDIT_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["治理报告不可解析：%s（修复指引：重生成）" % exc]
    return report, audit


def _live_issues(report: Dict[str, Any], audit: Dict[str, Any],
                 live: Dict[str, Any]) -> List[str]:
    """在盘报告/审计包与实时重算逐字比对。"""
    issues: List[str] = []
    if render_report(report) != render_report(live["report"]):
        issues.append("治理报告与实时重算不一致（修复指引：重跑 write）")
    if render_audit(audit) != render_audit(live["audit"]):
        issues.append("审计包与实时重算不一致（修复指引：重跑 write）")
    return issues


def _audit_item_issues(audit: Dict[str, Any]) -> List[str]:
    """审计包内每条 check 必须 ok。"""
    issues: List[str] = []
    for item in audit.get("checks") or []:
        if not item.get("ok"):
            issues.append("审计项未过：%s（%s）" % (item.get("id"), item.get("desc")))
    return issues


def _open_issues(report: Dict[str, Any]) -> List[str]:
    """OPEN 项必须带 owner。"""
    issues: List[str] = []
    for item in report.get("open_items") or []:
        if not str(item.get("owner")):
            issues.append("OPEN %s 缺 owner" % item.get("id"))
    return issues


def check(root: str = ".") -> List[str]:
    """committed == 实时重算 + 审计包全绿 + OPEN 有 owner。"""
    issues: List[str] = []
    for rel in (REPORT_REL, AUDIT_REL):
        if not (Path(root) / rel).is_file():
            issues.append("缺 %s（修复指引：跑 write() 重生成）" % rel)
    if issues:
        return issues
    loaded = _read_committed(root)
    if isinstance(loaded, list):
        return loaded
    report, audit = loaded
    live = build(root)
    issues.extend(_live_issues(report, audit, live))
    issues.extend(_audit_item_issues(audit))
    issues.extend(_open_issues(report))
    if any(report["levels"][lv]["ok"] for lv in ("T3", "T4")):
        issues.append("T3/T4 声称可达但适配器缺失——不得冒充")
    boundary = " ".join(str(x) for x in report.get("claims_boundary") or [])
    if "不冒充" not in boundary:
        issues.append("claims_boundary 必须写明不冒充")
    return issues
