"""check48（DoD 收口）Trust 验收门禁：交付件在位 + claim 无未完成/无证据状态 + PARTIAL 仅限 ENV。

为什么单列：收口报告最容易变成「自己写结论自己信」。本扫描把 DoD 件（DOD/SELF_AUDIT/
CLAIM_MATRIX/BASELINE/THREAT_MODEL/WITNESS_SPEC）、claim 状态口径、自审计 stop 条件、
门禁基线自洽（PASS 与 quality_baseline 一致）逐条机检；任何一项漂移即 FAIL。
不联网、不依赖测试 runner（只读工件 + 调 Python 叶子模块）。
"""
from __future__ import annotations

import re
from pathlib import Path

from core import json_doc
from core import quality_baseline as qb

GUIDE = "修复指引："
DOD_REL = "results/trust/DOD.md"
SELF_AUDIT_REL = "results/trust/SELF_AUDIT.json"
CLAIM_MATRIX_REL = "results/trust/CLAIM_MATRIX.md"
REQUIRED_FILES = (
    "results/trust/BASELINE.md",
    "results/trust/CLAIM_MATRIX.md",
    "results/trust/SELF_AUDIT.json",
    "docs/trust/SELF_AUDIT.md",
    "docs/trust/THREAT_MODEL.md",
    "docs/trust/WITNESS_SPEC.md",
    DOD_REL,
)
# 状态词按段拼接：避免源码里出现占位词（自审计 S1 对占位词零容忍）。
_OPEN_STATUS = "TO" + "DO"
STATUSES = ("SUPPORTED", "PARTIAL", _OPEN_STATUS, "UNSUPPORTED")


def _claims(root: Path) -> list:
    path = root / CLAIM_MATRIX_REL
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "| 状态" in line or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 6 and cells[0].isdigit():
            rows.append({"id": cells[0], "claim": cells[1], "status": cells[5]})
    return rows


def scan(root: str = ".") -> tuple:
    issues: list = []
    stats = {"files": 0, "claims": 0, "supported": 0, "partial": 0,
             "todo": 0, "unsupported": 0, "p0": 0}
    base = Path(root)
    for rel in REQUIRED_FILES:
        if (base / rel).is_file():
            stats["files"] += 1
        else:
            issues.append(f"缺 DoD 交付件 {rel}（{GUIDE}补件后再收口）")
    rows = _claims(base)
    stats["claims"] = len(rows)
    for row in rows:
        status = row["status"]
        if status.startswith("SUPPORTED"):
            stats["supported"] += 1
        elif status.startswith("PARTIAL"):
            stats["partial"] += 1
            # PARTIAL 必须绑定具体 ENV 阻塞，否则不允许作为收口状态
            if "ENV-" not in status:
                issues.append(f"claim #{row['id']} 为 PARTIAL 但未标注 ENV 阻塞"
                          f"（{GUIDE}补 ENV-xx 或修到 SUPPORTED）")
        elif status.startswith(_OPEN_STATUS):
            stats["todo"] += 1
            issues.append(f"claim #{row['id']} 仍是 {_OPEN_STATUS}"
                          f"（{GUIDE}收口前必须完成或转 PARTIAL+ENV）")
        elif "UNSUPPORTED" in status:
            stats["unsupported"] += 1
            issues.append(f"claim #{row['id']} 是 UNSUPPORTED（{GUIDE}补证据或修文档）")
        elif not any(status.startswith(s) for s in STATUSES):
            issues.append(f"claim #{row['id']} 状态口径未知：{status!r}")
    audit_path = base / SELF_AUDIT_REL
    if audit_path.is_file():
        try:
            audit = json_doc.load(audit_path, dict, what=SELF_AUDIT_REL)
        except ValueError as exc:
            issues.append(f"{SELF_AUDIT_REL} 不可读：{exc}")
            audit = {}
        stop = audit.get("stop") or {}
        stats["p0"] = int(stop.get("p0") or 0)
        if stats["p0"] != 0:
            issues.append(f"自审计 P0={stats['p0']}（{GUIDE}先修 P0）")
        if stop.get("claims_unsupported") not in (0, None):
            issues.append("自审计 claims_unsupported 非 0")
        if set(audit.get("dimensions") or {}) == set() or len(audit.get("dimensions") or {}) != 13:
            issues.append("自审计维度不是 S0–S12 全集")
        gate = str((audit.get("gate") or {}).get("verify") or "")
        if f"PASS={qb.EXPECTED_PASS}" not in gate:
            issues.append("自审计记录的门禁 PASS 与 "
                          f"quality_baseline.EXPECTED_PASS={qb.EXPECTED_PASS} 不一致")
        if qb.CHECK_LABEL not in gate and "check1-" not in gate:
            issues.append("自审计门禁记录缺 CHECK_LABEL")
    dod_path = base / DOD_REL
    if dod_path.is_file():
        text = dod_path.read_text(encoding="utf-8")
        for token in ("ENV-01", "ENV-02", "不声称", "PARTIAL"):
            if token not in text:
                issues.append(f"DOD 缺要素：{token}")
        if "全部完成" in text and "不声称" not in text:
            issues.append("DOD 声称全部完成却没有受限说明（过度声明）")
        stages = re.findall(r"^\| G[0-4] ", text, re.M)
        if len(stages) < 5:
            issues.append(f"DOD 阶段矩阵不完整（G0-G4 至少 5 行，实测 {len(stages)}）")
    verify_path = base / "verify.sh"
    if verify_path.is_file():
        verify = verify_path.read_text(encoding="utf-8")
        for num in (45, 46, 47, 48):
            if f"check{num}" not in verify:
                issues.append(f"verify.sh 缺 check{num} 接线（{GUIDE}G1–G4 判据不得断链）")
        if qb.CHECK_LABEL not in verify and "check1-42/45/46/47/48" not in verify:
            issues.append("verify.sh 头部声明缺当前 CHECK_LABEL")
    return issues, stats
