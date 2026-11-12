#!/usr/bin/env python3
"""docs/ccos/paper-adoption-v0.md 契约：论文台账文档必须「34 篇/四档计数/落点存在与实现一致」。

为什么必须有：这份台账是「读了哪些论文、移植了什么」的可核对象——它的价值全在「可核」：count 34、
counts 22/7/1/4、adopted 每条 targets/evidence 非空且文件真存在。文档若与台账漂移，读者会按错的
数字判断「吸收了多少」；adopted 若指向不存在文件，则是「看起来有落点」。本轮补最后更新位、现状对照、
复现口径，并把计数、entries 字段、落点/证据文件存在、脚本选项、5 例判据全部活绑定。

范围：只判本文与 protocol/paper_ledger.json/脚本/判据事实自洽（不改台账）。同族判据：
test_paper_ledger.py（5 例）/ test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、34/22/7/1/4 与台账逐项相等、entries 34、adopted 均有 targets+evidence
且文件在场、脚本三选项、5 例判据、现状对照 + 复现三命令。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "paper-adoption-v0.md"
LEDGER = ROOT / "protocol" / "paper_ledger.json"
SCRIPT = ROOT / "scripts" / "paper_ledger.py"
TEST = ROOT / "desktop" / "tests" / "test_paper_ledger.py"
SECTIONS = ("## 它是什么", "## 四档处置的含义", "## 怎么用", "## 判据（可证）",
            "## 现状对照", "## 复现与引用口径", "## 边界")
DISPOSITIONS = ("adopted", "deferred", "rejected", "not-applicable")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"论文台账文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("论文台账文档为空")
    return text


def ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def paper_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def paper_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 论文筛选台账 v0"):
        issues.append("缺标题「# 论文筛选台账 v0（34 篇 · 处置可核）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    doc = ledger()
    entries = doc.get("entries") or []
    if doc.get("count") != 34 or len(entries) != 34:
        issues.append(f"总数已变（count={doc.get('count')}, entries={len(entries)}）")
    counts = doc.get("counts") or {}
    want = {"adopted": 22, "deferred": 7, "rejected": 1, "not-applicable": 4}
    if {k: counts.get(k) for k in DISPOSITIONS} != want:
        issues.append(f"四档计数已变：{counts}")
    for label in ("34 篇", "adopted 22", "deferred 7", "rejected 1",
                  "not-applicable 4"):
        if label not in text:
            issues.append(f"正文缺计数口径：{label}")
    bad = []
    for e in entries:
        if e.get("disposition") == "adopted":
            if not (e.get("targets") and e.get("evidence")):
                bad.append(f"{e.get('id')} 缺 targets/evidence")
                continue
            for rel in list(e.get("targets") or []) + list(e.get("evidence") or []):
                if not (ROOT / str(rel)).exists():
                    bad.append(f"{e.get('id')} 落点不存在：{rel}")
    if bad:
        issues.append("adopted 落点/证据面不成立：" + "；".join(bad[:3]))
    for disp in DISPOSITIONS:
        if disp not in text:
            issues.append(f"正文缺处置档：{disp}")
    sp = SCRIPT.read_text(encoding="utf-8")
    for opt in ("--stats", "--check", "--write"):
        if opt not in sp:
            issues.append(f"脚本缺选项：{opt}")
        if opt not in text:
            issues.append(f"正文缺脚本选项：{opt}")
    n_cases = paper_cases()
    if n_cases != 5:
        issues.append(f"test_paper_ledger 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text and str(n_cases) + " 项" not in text:
        issues.append(f"未写判据数（{n_cases}）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/paper_ledger.py --check",
                "python scripts/paper_ledger.py --stats",
                "python -m pytest desktop/tests/test_paper_ledger.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class PaperAdoptionDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_paper_doc_matches_contract(self):
        self.assertEqual([], paper_issues(self.text), "论文台账文档不满足契约")

    def test_ledger_live(self):
        doc = ledger()
        self.assertEqual(34, doc["count"])
        self.assertEqual(34, len(doc["entries"]))
        self.assertEqual({"adopted": 22, "deferred": 7, "rejected": 1,
                          "not-applicable": 4},
                         {k: doc["counts"][k] for k in DISPOSITIONS})
        self.assertEqual(5, paper_cases())

    def test_contract_catches_mutations(self):
        """变异自证：计数回退 / 缺处置档 / 缺脚本选项 / 例数漂移 / 缺命令。"""
        old = self.text.replace("adopted 22", "adopted 20")
        self.assertTrue(any("adopted" in i or "计数" in i for i in paper_issues(old)))
        no_disp = self.text.replace("not-applicable", "na")
        self.assertTrue(any("not-applicable" in i for i in paper_issues(no_disp)))
        no_opt = self.text.replace("--stats", "--sum")
        self.assertTrue(any("--stats" in i for i in paper_issues(no_opt)))
        old_n = self.text.replace("5 例", "3 例").replace("5 项", "3 项")
        self.assertTrue(any("5" in i or "例数" in i for i in paper_issues(old_n)))
        no_cmd = self.text.replace("python scripts/paper_ledger.py --stats", "看计数")
        self.assertTrue(any("--stats" in i for i in paper_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_paper.md")


if __name__ == "__main__":
    unittest.main()
