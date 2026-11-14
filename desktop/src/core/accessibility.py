"""可访问性（`nf-a11y/1`）：WCAG 2.2 适用子集 + PAIR/HAX 人因 + 可用性测试模板。

为什么（NF-Final WP-0E，P1 盲区 BL-08）：CLI/TUI 无图形界面不等于「天然可访问」——颜色语义、
窄宽度截断、错误不可解释、AI 输出无人类监督都是真实缺陷。本模块把适用项做成数据 + 判据：
- 每条 WCAG 项要么有控制点+**在场证据**（enforced），要么 partial（如实缺口），要么
  not-applicable（**必须写理由**）；planned 必须写 planned_gate；
- 人因原则（PAIR/HAX）逐条绑定控制点与证据；
- 可用性测试状态诚实（template-only：外部实测属外部操作，不冒充已做）；
- 违规预算 = 0（声明面出现颜色-only/无键盘路径等即红）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-a11y/1"
REL = "protocol/accessibility.json"
STATUSES = ("enforced", "partial", "not-applicable", "planned")
LEVELS = ("A", "AA", "AAA")
FRAMEWORKS = ("PAIR", "HAX")
GATES = ("G0", "G1", "G2", "G3", "G4", "G5")
GUIDE = "修复指引："


def load(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise ValueError("缺 %s（%s 补可访问性登记）" % (REL, GUIDE))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(REL + " 不是合法 JSON：" + str(exc)) from exc
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        raise ValueError(REL + " schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）")
    return doc


def _exists(root: str, rel: str) -> bool:
    return (Path(root) / str(rel)).exists()


def _evidence_issues(root: str, refs: Any, where: str,
                     require_test: bool = False) -> List[str]:
    issues: List[str] = []
    if not isinstance(refs, list) or not refs:
        return ["%s 缺 evidence（%s 控制点必须绑定真实件）" % (where, GUIDE)]
    for rel in refs:
        if not _exists(root, str(rel)):
            issues.append("%s 的 evidence 不在场：%s" % (where, rel))
    if require_test and not any(str(x).startswith(("desktop/tests/", "scripts/", "verify.sh"))
                                for x in refs):
        issues.append("%s 标 enforced 但缺测试/门禁证据" % where)
    return issues


def validate(doc: Dict[str, Any], root: str = ".") -> List[str]:
    issues: List[str] = []
    std = doc.get("standard") or {}
    for key in ("wcag", "iso_9241_11", "human_ai"):
        if not str(std.get(key) or "").strip():
            issues.append("standard 缺 %s" % key)
    for rel in doc.get("declared_surfaces") or []:
        if not _exists(root, str(rel)):
            issues.append("declared_surfaces 不在场：%s" % rel)
    rows = doc.get("wcag") or []
    ids = [str(r.get("id")) for r in rows if isinstance(r, dict)]
    if len(rows) < 6:
        issues.append("wcag 至少 6 条适用项（%s）" % GUIDE)
    if len(ids) != len(set(ids)):
        issues.append("wcag id 重复：%s" % ids)
    for row in rows:
        if not isinstance(row, dict):
            issues.append("wcag 含非对象")
            continue
        wid = str(row.get("id"))
        if str(row.get("level")) not in LEVELS:
            issues.append("%s 的 level 非法：%s" % (wid, row.get("level")))
        status = str(row.get("status"))
        if status not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (wid, status))
        if not str(row.get("control") or "").strip():
            issues.append("%s 缺 control（控制点）" % wid)
        issues += _evidence_issues(root, row.get("evidence"), wid,
                                   require_test=(status == "enforced"))
        if status == "not-applicable" and not str(row.get("reason") or "").strip():
            issues.append("%s 标 not-applicable 但缺 reason" % wid)
        if status == "planned" and str(row.get("planned_gate")) not in GATES:
            issues.append("%s 标 planned 但缺 planned_gate" % wid)
    hf = doc.get("human_factors") or []
    hf_ids = [str(h.get("id")) for h in hf if isinstance(h, dict)]
    if len(hf) < 4:
        issues.append("human_factors 至少 4 条（PAIR/HAX；%s）" % GUIDE)
    if len(hf_ids) != len(set(hf_ids)):
        issues.append("human_factors id 重复：%s" % hf_ids)
    for row in hf:
        if not isinstance(row, dict):
            issues.append("human_factors 含非对象")
            continue
        hid = str(row.get("id"))
        if str(row.get("framework")) not in FRAMEWORKS:
            issues.append("%s 的 framework 非法：%s" % (hid, row.get("framework")))
        if not str(row.get("principle") or "").strip():
            issues.append("%s 缺 principle" % hid)
        issues += _evidence_issues(root, row.get("evidence"), hid)
    tests = doc.get("usability_tests") or []
    if not tests:
        issues.append("缺 usability_tests（至少模板级）")
    for test in tests:
        if not isinstance(test, dict):
            issues.append("usability_tests 含非对象")
            continue
        if str(test.get("status")) not in ("template-only", "done-external"):
            issues.append("可用性测试 %s 的 status 非法：%s"
                          % (test.get("id"), test.get("status")))
        if str(test.get("status")) == "template-only" and not str(test.get("note") or "").strip():
            issues.append("可用性测试 %s 标 template-only 但缺 note（如实写未做）" % test.get("id"))
    if doc.get("violation_budget") != 0:
        issues.append("violation_budget 必须为 0（声明面不允许已知违规存量）")
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "不声称" not in boundary:
        issues.append("claims_boundary 必须显式写「不声称 WCAG 合规/认证」")
    return issues


def terminal_facts(root: str = ".") -> Dict[str, Any]:
    """CLI/TUI 可访问性事实（只读 grep/AST 级别；供人读报告与测试断言）。"""
    term = Path(root) / "desktop" / "src" / "core" / "terminal.py"
    text = term.read_text(encoding="utf-8") if term.is_file() else ""
    tui_dir = Path(root) / "tui"
    tui_files = sorted(p.name for p in tui_dir.glob("*.py")) if tui_dir.is_dir() else []
    return {
        "no_color": "NO_COLOR" in text,
        "color_mode": "着色" in text or "color" in text,
        "width_limit": "width" in text.lower() or "限长" in text,
        "self_check": "def self_check(" in text,
        "tui_files": tui_files,
        "declared": {"term": term.is_file(), "tui": bool(tui_files)},
    }
