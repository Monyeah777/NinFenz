#!/usr/bin/env python3
"""docs/42_M1_P06 契约：快照状态 + 覆盖真源接续 + 判据覆盖面如实 + 复现口径。

为什么必须有：本文是「P06 第 2 份」演练记录，写「测试参数化覆盖 P03+P06 两套」——但 44 drill 波
已把演练集扩到 **8 集**，覆盖真源是 docs/44_M1_执行演练扩展.md；而 test_execution_drill 现
参数化 **8 套**（p01–p06 + p07_en + p90；2026-11-13 起含 p07_en，_hits 接 fixture lexicon，
此前「7 套 + p07_en 例外」的旧口径已消除）。本轮补快照横幅、现状对照、复现口径，并把覆盖
事实立成机检断言。

范围：只判本文与夹具/测试/44 真源自洽（不改历史数值）。同族判据：
test_execution_drill.py / test_drill_doc_contract.py（P03 同类）/
test_doc_reachability.py（ARCHIVE_DOCS，故 glob 定位）。
契约：标题 + 快照横幅、五段按序、P06 夹具 8 例、演练夹具 8 份、
test_execution_drill 的 FIXTURES 实为 8 套且正文写「8 套」（含 p07_en）、
RULE_LAW 6 条、44 覆盖真源在场、FIELD-001 挂账、复现命令在。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import execution_drill as drill  # noqa: E402

HITS = sorted((ROOT / "docs").glob("42_M1_P06*演练集.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-p06.md"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "execution"
P06 = FIXTURES / "p06_drill_cases.json"
P07 = FIXTURES / "p07_en_drill_cases.json"
TEST_FILE = ROOT / "desktop" / "tests" / "test_execution_drill.py"
COVER_DOC = ROOT / "docs" / "44_M1_执行演练扩展.md"
SECTIONS = ("## 一、可复现执行", "## 二、案例清单", "## 三、口径与纪律",
            "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"P06 演练集不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("P06 演练集为空")
    return text


def _fixture_count() -> int:
    text = TEST_FILE.read_text(encoding="utf-8")
    m = re.search(r"FIXTURES\s*=\s*\[FIX_DIR / n\s*\n\s*for n in \((.*?)\)\]", text, re.S)
    if not m:
        return -1
    return len([p for p in m.group(1).split(",") if ".json" in p])


def p06_cases() -> list:
    return json.loads(P06.read_text(encoding="utf-8")).get("cases") or []


def p06_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M1 · P06 技术文档题材装配流 · 内部执行演练集"):
        issues.append("缺标题「# 42 M1 · P06 … 内部执行演练集」")
    for marker in ("历史演练记录", "已被 44 drill 扩展接续", "仍挂账"):
        if marker not in text:
            issues.append(f"缺状态口径：{marker}")
    if "2026-09-08" not in text:
        issues.append("历史时点 2026-09-08 丢失")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if len(p06_cases()) != 8:
        issues.append(f"P06 夹具例数已变（{len(p06_cases())}）")
    if "8 例全过" not in text:
        issues.append("未写 P06 8 例全过")
    fixtures = sorted(FIXTURES.glob("*_drill_cases.json"))
    if len(fixtures) != 8:
        issues.append(f"演练夹具份数已变（{len(fixtures)}）")
    if "8 集" not in text and "8 条管线" not in text:
        issues.append("未写演练集已扩到 8 集")
    covered = _fixture_count()
    if covered != 8:
        issues.append(f"test_execution_drill 夹具清单已变（{covered}）：现状对照需复核")
    if "8 套" not in text:
        issues.append("未写 test_execution_drill 实际参数化 8 套")
    if "已纳入" not in text and "含 p07_en" not in text:
        issues.append("未写 p07_en 已纳入该单测")
    if not P07.is_file():
        issues.append("缺 p07_en 夹具")
    if len(getattr(drill, "RULE_LAW", {})) != 6:
        issues.append("RULE_LAW 条数已变")
    if "6 条" not in text:
        issues.append("未写 RULE_LAW 6 条")
    if not COVER_DOC.is_file():
        issues.append("缺覆盖真源：docs/44_M1_执行演练扩展.md")
    else:
        cover = COVER_DOC.read_text(encoding="utf-8")
        if "7 条可执行主线" not in cover or "p07_en" not in cover:
            issues.append("44 覆盖真源缺主线清单/多语集")
    if "docs/44_M1_执行演练扩展.md" not in text:
        issues.append("正文未指向 44 覆盖真源")
    for cmd in ("python -m core.execution_drill", "p06_drill_cases.json",
                "test_execution_drill.py"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class P06DrillContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_p06_doc_matches_contract(self):
        self.assertEqual([], p06_issues(self.text), "P06 演练集不满足契约")

    def test_coverage_facts_are_live(self):
        self.assertEqual(8, len(p06_cases()))
        self.assertEqual(8, len(list(FIXTURES.glob("*_drill_cases.json"))))
        self.assertEqual(8, _fixture_count())
        self.assertTrue(P07.is_file())

    def test_contract_catches_mutations(self):
        """变异自证：去快照 / 例数漂移 / 套数回退 / 缺真源 / 缺现状对照 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史演练记录", "> **状态：现行", 1)
        self.assertTrue(any("历史演练记录" in i for i in p06_issues(no_banner)))
        wrong = self.text.replace("8 例全过", "9 例全过")
        self.assertTrue(any("8 例全过" in i for i in p06_issues(wrong)))
        overclaim = self.text.replace("8 套", "7 套")
        self.assertTrue(any("8 套" in i for i in p06_issues(overclaim)))
        no_src = self.text.replace("docs/44_M1_执行演练扩展.md", "覆盖文档")
        self.assertTrue(any("44" in i for i in p06_issues(no_src)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in p06_issues(no_sec)))
        no_cmd = self.text.replace("p06_drill_cases.json", "夹具")
        self.assertTrue(any("p06_drill_cases.json" in i for i in p06_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_p06.md")


if __name__ == "__main__":
    unittest.main()
