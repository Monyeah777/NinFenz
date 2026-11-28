"""运维/事件/BCP/供应商登记（`nf-ops/1` + `nf-vendors/1`）：把「出事了怎么办」做成可复算判据。

为什么（NF-Final WP-0D，P0 盲区 BL-03/BL-04）：IR/BCP/供应商这些面最容易变成「文档写了就算
有」。本模块把三件事做成数据 + 可执行演练：
- **登记校验**：严重度/runbook/SLO/BCP/披露口径逐条查在场与结构；vendor 的 used_by/attestation
  必须指向真实件，critical/high 必须有 attestation，退出计划必须有 fallback+步骤+owner；
- **桌面演练（tabletop）**：给定严重度，输出 runbook 每步的 required/skipped 与披露义务，
  证明分级到流程的映射是确定性的（不是"看情况"）；
- **恢复演练（recovery）**：真的做一次「备份 → 篡改 → 检测到 → 从备份恢复 → 再验通过」闭环
  （用 claim bundle 的 Merkle 校验做被保护对象；不写仓、不联网）；
- **披露演练（disclosure）**：通道/口径来自 `SECURITY.md`（唯一权威），本模块只做逻辑校验
  （私密通道 + 确认/披露窗口有序），不承诺修复 SLA；
- **供应商退出就绪（vendor exit）**：静态就绪检查（路径/attestation/退出计划）；真实网络替换
  属外部操作，标 UNOBSERVABLE，不冒充已演练。

报告落 `results/ops/drills.json`，`check_committed` 断言在盘 == 实时重算。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OPS_SCHEMA = "nf-ops/1"
VENDORS_SCHEMA = "nf-vendors/1"
REPORT_SCHEMA = "nf-ops-drills/1"
OPS_REL = "protocol/ops.json"
VENDORS_REL = "protocol/vendors.json"
REPORT_REL = "results/ops/drills.json"
SEVERITIES = ("S0", "S1", "S2", "S3")
DR_KINDS = ("tabletop", "recovery", "disclosure", "vendor-exit")
#: 桌面演练：某严重度可跳过的步骤（其余全部 required）——分级到流程的确定性映射。
TABLE_TOP_SKIP = {"S0": (), "S1": (), "S2": ("IR-03",), "S3": ("IR-03", "IR-06")}
#: runbook 必备步骤（删任一步 = 流程缺口，判据必须红）
EXPECTED_RUNBOOK = ("IR-01", "IR-02", "IR-03", "IR-04", "IR-05", "IR-06", "IR-07")
GUIDE = "修复指引："


def _load(root: str, rel: str, schema: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError("缺 %s（%s 补登记件）" % (rel, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(rel + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != schema:
        raise ValueError(rel + " schema 不匹配（" + GUIDE + "需要 " + schema + "）")
    return doc


def load_ops(root: str = ".") -> Dict[str, Any]:
    return _load(root, OPS_REL, OPS_SCHEMA)


def load_vendors(root: str = ".") -> Dict[str, Any]:
    return _load(root, VENDORS_REL, VENDORS_SCHEMA)


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / rel).exists()


from ._ops_checks import _ops_issues, _vendor_issues_all


def validate_ops(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    sev = doc.get("severity_vocabulary")
    if not isinstance(sev, dict) or list(sev.keys()) != list(SEVERITIES):
        return ["severity_vocabulary 必须恰为 S0/S1/S2/S3（%s 补齐）" % GUIDE]
    return _ops_issues(doc, root)


def validate_vendors(doc: Dict[str, Any], root: str = ".") -> List[str]:
    return _vendor_issues_all(doc, root)


def tabletop(doc: Dict[str, Any], severity: str) -> Dict[str, Any]:
    """桌面演练：给定严重度 → runbook 每步 required/skipped + 披露义务（确定性映射）。"""
    if severity not in SEVERITIES:
        raise ValueError("未知严重度：%r（%s 取 S0-S3）" % (severity, GUIDE))
    steps = ((doc.get("incident_runbook") or {}).get("steps") or [])
    skip = set(TABLE_TOP_SKIP[severity])
    rows = []
    for step in steps:
        sid = str(step.get("id"))
        rows.append({"id": sid, "status": "skipped" if sid in skip else "required"})
    return {"id": "DR-01", "kind": "tabletop", "severity": severity, "steps": rows,
            "disclosure_required": severity in ("S0", "S1"), "status": "pass"}


def disclosure_drill(doc: Dict[str, Any], severity: str) -> Dict[str, Any]:
    """披露演练：私密通道 + 确认/披露窗口有序（逻辑口径；通道权威 = SECURITY.md）。"""
    if severity not in SEVERITIES:
        raise ValueError("未知严重度：%r" % severity)
    disc = doc.get("disclosure") or {}
    ok = (bool(str(disc.get("channel") or "").strip())
          and isinstance(disc.get("ack_within_days"), int)
          and isinstance(disc.get("disclose_within_days"), int)
          and 0 < disc["ack_within_days"] <= disc["disclose_within_days"])
    return {"id": "DR-03", "kind": "disclosure", "severity": severity,
            "private_channel": bool(str(disc.get("channel") or "").strip()),
            "ack_days": disc.get("ack_within_days"),
            "disclose_days": disc.get("disclose_within_days"),
            "status": "pass" if ok else "fail"}


def recovery_drill() -> Dict[str, Any]:
    """恢复演练：备份 → 篡改 → 检出 → 从备份恢复 → 再验通过（Merkle 证据闭环）。"""
    from core.trust import bundle as tb
    claims = [
        {"id": "C-001", "type": "evidence", "subject_digest": "b" * 64,
         "payload_digest": "c" * 64},
        {"id": "C-002", "type": "evidence", "subject_digest": "d" * 64,
         "payload_digest": "e" * 64},
    ]
    backup = tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", claims)
    steps = [{"name": "备份", "status": "pass" if tb.verify_bundle(backup)["ok"] else "fail"}]
    tampered = copy.deepcopy(backup)
    tampered["claims"][0]["payload_digest"] = "f" * 64
    steps.append({"name": "篡改被检出",
                  "status": "pass" if not tb.verify_bundle(tampered)["ok"] else "fail"})
    restored = copy.deepcopy(backup)
    steps.append({"name": "从备份恢复后可验",
                  "status": "pass" if tb.verify_bundle(restored)["ok"] else "fail"})
    return {"id": "DR-02", "kind": "recovery", "steps": steps,
            "status": "pass" if all(s["status"] == "pass" for s in steps) else "fail"}


def vendor_readiness(vendors: Dict[str, Any], root: str = ".") -> Dict[str, Any]:
    """供应商退出就绪（静态）：逐 vendor 查 used_by/attestation/exit_plan 可执行。"""
    issues = validate_vendors(vendors, root)
    rows = []
    for ven in vendors.get("vendors") or []:
        vid = str(ven.get("id"))
        own = [i for i in issues if vid in i]
        rows.append({"id": vid, "status": "fail" if own else "pass", "issues": own})
    drill = {"id": "DR-04", "kind": "vendor-exit", "vendors": rows,
             "replacement_drills": len(vendors.get("replacement_drills") or []),
             "status": "pass" if not issues else "fail"}
    return drill


def render(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _drills(ops: Dict[str, Any], vendors: Dict[str, Any], root: str) -> List[Dict[str, Any]]:
    """四类演练：桌面（逐严重度）/ 恢复 / 披露（S0·S1）/ 供应商退出。"""
    drills = [tabletop(ops, sev) for sev in SEVERITIES]
    drills.append(recovery_drill())
    drills += [disclosure_drill(ops, sev) for sev in ("S0", "S1")]
    drills.append(vendor_readiness(vendors, root))
    return drills


def _counts(ops: Dict[str, Any], vendors: Dict[str, Any],
            drills: List[Dict[str, Any]]) -> Dict[str, int]:
    """报告计数（严重度/runbook 步/演练数/供应商/SLO）。"""
    return {"severities": len(SEVERITIES), "runbook_steps": len(
        (ops.get("incident_runbook") or {}).get("steps") or []),
        "drills": len(drills),
        "vendors": len(vendors.get("vendors") or []),
        "slo": len(ops.get("slo") or [])}


def build_report(root: str = ".") -> Dict[str, Any]:
    findings: List[str] = []
    try:
        ops = load_ops(root)
    except ValueError as exc:
        return {"schema": REPORT_SCHEMA, "ok": False, "findings": [str(exc)],
                "drills": [], "counts": {}}
    try:
        vendors = load_vendors(root)
    except ValueError as exc:
        return {"schema": REPORT_SCHEMA, "ok": False, "findings": [str(exc)],
                "drills": [], "counts": {}}
    findings += validate_ops(ops, root) + validate_vendors(vendors, root)
    drills = _drills(ops, vendors, root)
    for drill in drills:
        if drill.get("status") != "pass":
            findings.append("演练未过：%s（%s 修登记或演练实现）" % (drill.get("id"), GUIDE))
    counts = _counts(ops, vendors, drills)
    return {"schema": REPORT_SCHEMA, "ok": not findings, "findings": findings,
            "drills": drills, "counts": counts}


def write(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    from core import atomic_write
    doc = build_report(root)
    dest = Path(root) / REPORT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(dest, render(doc))
    return doc["findings"], doc


def check_committed(root: str = ".") -> List[str]:
    """在盘报告与实时重算逐字节比对（手改/少跑 --run 都红）。"""
    path = Path(root) / REPORT_REL
    if not path.is_file():
        return ["缺演练报告 %s（%s 跑 python scripts/ops_drill.py --run）" % (REPORT_REL, GUIDE)]
    try:
        have = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ["读不出 %s：%s" % (REPORT_REL, exc)]
    want = render(build_report(root))
    if want != have:
        return ["演练报告与实时重算不一致（%s 跑 python scripts/ops_drill.py --run）" % GUIDE]
    return []
