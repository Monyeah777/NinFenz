#!/usr/bin/env python3
"""docs/45_M3 契约：已确认事实 + registry 现状活绑定 + 开放项如实 + 复现口径。

为什么必须有：这是「proposed → 已确认」的载荷提案档——它写「declared 30/30」，但事件登记面已扩到
443 条（declared 438）；同时开放项（sections/changes 结构粒度、模块 io_types 收窄）**仍未完成**。
不标现状，读者会以为登记面只有 30 条，或误以为 untyped 已收窄。本轮补状态横幅、现状对照、
复现口径，并把 5 事件 declared 事实、registry 规模、M90 untyped 现状立成机检断言。

范围：只判本文与 registry/模块契约事实自洽（不改提案）。同族判据：
test_events*.py（事件背书）/ test_module_types*.py（io_types）/
test_doc_hygiene.py（指令档标识）/ test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated、现状 + 提案表（5 事件）+ 落库纪律 + 现状对照 + 复现口径、
5 事件在 registry 为 declared 且字段与提案一致、registry 事件/declared 规模与实读一致、
M90 DocState/doc_delta 仍 untyped 的现状如实标注、历史 30/30 快照保留、复现命令在。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "45_M3_techdoc载荷提案.md"
REG = ROOT / "protocol" / "event_registry.json"
M90 = ROOT / "04_模块库" / "技术文档类" / "M90_结构装配.md"
NF = ROOT / "scripts" / "nf.py"
SECTIONS = ("## 现状（已收口）", "## 提案", "## 落库纪律", "## 现状对照", "## 复现与引用口径")
EVENTS = {
    "doc_structure_ready": {"doc_id", "title", "version", "sections"},
    "doc_delta_committed": {"doc_id", "prev_ver", "new_ver", "changes"},
    "intent_received": {"intent_id", "mode", "text"},
    "term_synced": {"delta", "status", "count"},
    "term_conflict_detected": {"term", "definitions", "status"},
}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"载荷提案不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("载荷提案为空")
    return text


def registry() -> dict:
    return json.loads(REG.read_text(encoding="utf-8")).get("events") or {}


def proposal_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 45 A1 · techdoc 链载荷补充"):
        issues.append("缺标题「# 45 A1 · techdoc 链载荷补充」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "提案已确认并落库" not in text:
        issues.append("缺「提案已确认并落库」状态声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    ev = registry()
    for name, fields in EVENTS.items():
        entry = ev.get(name) or {}
        if entry.get("payload_status") != "declared":
            issues.append(f"registry 事件未 declared：{name}")
        got = set((entry.get("fields") or {}).keys())
        if got != fields:
            issues.append(f"事件字段与提案不一致：{name} {sorted(got)}")
        if name not in text:
            issues.append(f"正文缺事件：{name}")
    declared = sum(1 for e in ev.values() if e.get("payload_status") == "declared")
    if len(ev) != 443:
        issues.append(f"registry 事件数已变（{len(ev)}）：现状对照需复核")
    if declared != 438:
        issues.append(f"declared 数已变（{declared}）：现状对照需复核")
    if "443" not in text or "438" not in text:
        issues.append("未写现行事件/declared 规模（443/438）")
    if "30/30" not in text:
        issues.append("历史「declared 30/30」快照被改写")
    m90 = M90.read_text(encoding="utf-8")
    for token in ("DocState: untyped", "doc_delta: untyped"):
        if token not in m90:
            issues.append(f"M90 契约已变（不再 untyped）：{token}")
    if "untyped" not in text:
        issues.append("未如实标注 io_types 仍 untyped")
    if "仍待办" not in text:
        issues.append("缺开放项「仍待办」如实标注")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("events", "module"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    for cmd in ("python scripts/nf.py events", "python scripts/nf.py module types --json"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class PayloadProposalContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_proposal_matches_contract(self):
        self.assertEqual([], proposal_issues(self.text), "载荷提案不满足契约")

    def test_registry_facts_live(self):
        ev = registry()
        for name in EVENTS:
            self.assertEqual("declared", (ev.get(name) or {}).get("payload_status"))
        self.assertEqual(443, len(ev))
        declared = sum(1 for e in ev.values() if e.get("payload_status") == "declared")
        self.assertEqual(438, declared)

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 事件缺失 / 规模回退 / 假称已收窄 / 缺现状对照 / 缺复现命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in proposal_issues(no_marker)))
        no_ev = self.text.replace("term_synced", "某事件")
        self.assertTrue(any("term_synced" in i for i in proposal_issues(no_ev)))
        old_scale = self.text.replace("443", "30").replace("438", "30")
        self.assertTrue(any("443" in i or "438" in i for i in proposal_issues(old_scale)))
        narrowed = self.text.replace("untyped", "typed")
        self.assertTrue(any("untyped" in i for i in proposal_issues(narrowed)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in proposal_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py events", "看事件")
        self.assertTrue(any("events" in i for i in proposal_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_proposal.md")


if __name__ == "__main__":
    unittest.main()
