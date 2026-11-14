#!/usr/bin/env python3
"""docs/approval.md 契约：内容绑定批准文档必须「字段/命令/冻链位置与实现一致 + 现状活绑定」。

为什么必须有：这是「批准」面的操作规范——它决定读者怎么理解「批准 ≠ 永久通行证」。文档写的
记录字段（原为 5 项散文）与现行实现（6 键 + schema）不一致；且它未说明自己是 **release 冻链条
第 2 环**（conformance → approve → receipts，真源 core/release_gate.DEFAULT_FREEZE_CHAIN）。
本轮补字段表、冻链位置、现状对照与复现口径，并把 CLI 旗标/记录结构/链顺序立成机检断言。

范围：只判本文与 approve 实现/记录事实自洽（不改机制）。同族判据：
test_audit.py（审计面）/ test_scale_receipts.py（回执）/ test_role_model.py（冻链）/
test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated + 复核位、字段表 6 键、
CLI 五旗标（--by/--note/--verify/--list/--json）、
记录存在且 6 键齐全/摘要非空、冻链三环顺序与 release_gate 一致、现状对照、复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import release_gate  # noqa: E402

DOC = ROOT / "docs" / "approval.md"
APPROVALS = ROOT / "protocol" / "approvals"
NF = ROOT / "scripts" / "nf.py"
SUBJECT = ROOT / "protocol" / "conformance_report.json"
SECTIONS = ("## 是什么", "## 怎么用", "## 边界", "## 在冻链条中的位置",
            "## 现状对照", "## 复现与引用口径")
FIELDS = ("schema", "subject", "subject_digest", "approved_by", "approved_at", "note")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"批准文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("批准文档为空")
    return text


def records() -> list:
    return sorted(APPROVALS.glob("*.json"))


def approval_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 内容绑定批准记录"):
        issues.append("缺标题「# 内容绑定批准记录（approve）」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核（2026-11-13）" not in text:
        issues.append("缺「复核（2026-11-13）」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for field in FIELDS:
        row = "| " + chr(96) + field + chr(96) + " |"
        if row not in text:
            issues.append(f"字段表缺键：{field}")
    nf = NF.read_text(encoding="utf-8")
    for flag in ("--by", "--note", "--verify", "--list", "--json"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
    recs = records()
    if len(recs) != 1:
        issues.append(f"批准记录数已变（{len(recs)}）：现状对照需复核")
    if "1 条" not in text:
        issues.append("未写现行记录数（1 条）")
    if recs:
        data = json.loads(recs[0].read_text(encoding="utf-8"))
        missing = [k for k in FIELDS if k not in data]
        if missing:
            issues.append(f"记录缺字段：{missing}")
        if not data.get("subject_digest"):
            issues.append("记录 subject_digest 为空（绑定失效）")
        if data.get("subject") != "protocol/conformance_report.json":
            issues.append(f"记录对象异常：{data.get('subject')}")
        if recs[0].name not in text:
            issues.append(f"未点名现行记录文件：{recs[0].name}")
    chain = list(release_gate.DEFAULT_FREEZE_CHAIN)
    if len(chain) != 3:
        issues.append(f"冻链条环数已变（{len(chain)}）")
    for step in chain:
        if step not in text:
            issues.append(f"冻链命令缺失：{step}")
    order = [text.find(step) for step in chain]
    if all(p >= 0 for p in order) and order != sorted(order):
        issues.append("冻链条顺序与实现不一致")
    if "DEFAULT_FREEZE_CHAIN" not in text:
        issues.append("未写冻链真源（core/release_gate.DEFAULT_FREEZE_CHAIN）")
    if "不判内容质量" not in text:
        issues.append("缺「只判绑定、不判质量」边界")
    for cmd in ("python scripts/nf.py approve --list --json",
                "python scripts/nf.py approve --verify",
                "python scripts/nf.py release --plan"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ApprovalDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_approval_matches_contract(self):
        self.assertEqual([], approval_issues(self.text), "批准文档不满足契约")

    def test_records_and_chain_live(self):
        self.assertEqual(1, len(records()))
        self.assertEqual(3, len(release_gate.DEFAULT_FREEZE_CHAIN))
        self.assertTrue(SUBJECT.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 去字段 / 链顺序颠倒 / 去记录点名 / 去边界 / 缺复现命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in approval_issues(no_date)))
        no_field = self.text.replace("| `approved_at` |", "| 时间 |")
        self.assertTrue(any("approved_at" in i for i in approval_issues(no_field)))
        swapped = self.text.replace(
            "1. `python scripts/nf.py conformance --write`",
            "1. `python scripts/nf.py receipts --scope protocol --write`"
        ).replace(
            "3. `python scripts/nf.py receipts --scope protocol --write`",
            "3. `python scripts/nf.py conformance --write`"
        )
        self.assertTrue(any("顺序" in i or "冻链" in i for i in approval_issues(swapped)))
        no_name = self.text.replace("protocol__conformance_report.json", "记录")
        self.assertTrue(any("记录文件" in i for i in approval_issues(no_name)))
        no_bound = self.text.replace("不判内容质量", "判内容质量")
        self.assertTrue(any("边界" in i for i in approval_issues(no_bound)))
        no_cmd = self.text.replace("python scripts/nf.py approve --verify", "跑校验")
        self.assertTrue(any("approve --verify" in i for i in approval_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_approval.md")


if __name__ == "__main__":
    unittest.main()
