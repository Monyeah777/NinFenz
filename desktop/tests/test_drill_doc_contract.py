#!/usr/bin/env python3
"""docs/42_M1_P03 演练集契约：历史演练记录必须「快照状态 + 演练结果/机制现状 + 复现口径」。

为什么必须有：这份是「P03 第 1 份」执行演练集——它写的 8 例仍可复现，但**机制已扩到 8 条管线**、
**RULE_LAW 硬断言映射已从 4 条扩到 6 条**（新增 cross_pipeline_id / fabricated_asset_key → L2），
FIELD-001 回填仍挂账。不标这些，读者会把「4 条映射 / 只有 P03」当现状。本轮补快照横幅、
现状对照表、复现口径，并把「8 例可复现 / 夹具份数 / 映射条数 / FIELD-001 挂账」立成机检断言。

范围：只判本文与夹具/执行器事实自洽（不改演练内容）。同族判据：
test_execution_drill.py（常驻判据）/ test_c1c2_record_contract.py（同类快照模板）/
test_doc_reachability.py（ARCHIVE_DOCS，故 glob 定位）。
契约：标题 + 快照横幅、四节 + 现状对照 + 复现口径按序、P03 夹具 8 例、演练夹具 8 份、
RULE_LAW 6 条且含四条历史映射、执行器/判据在场、FIELD-001 仍挂账、
复现命令三条在、历史值 2026-09-08 保留。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import execution_drill as drill  # noqa: E402

HITS = sorted((ROOT / "docs").glob("42_M1_P03*演练集.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-drill.md"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "execution"
P03 = FIXTURES / "p03_drill_cases.json"
DRILL_MOD = ROOT / "desktop" / "src" / "core" / "execution_drill.py"
DRILL_TEST = ROOT / "desktop" / "tests" / "test_execution_drill.py"
SECTIONS = ("## 一、可复现执行", "## 二、演练案例清单", "## 三、五维自评",
            "## 四、边界与遗留", "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"演练集不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("演练集为空")
    return text


def p03_cases() -> list:
    return json.loads(P03.read_text(encoding="utf-8")).get("cases") or []


def drill_doc_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M1 · P03 西幻生存流 · 内部执行演练集"):
        issues.append("缺标题「# 42 M1 · P03 … 内部执行演练集」")
    for marker in ("历史演练记录", "机制已扩展", "仍挂账"):
        if marker not in text:
            issues.append(f"缺状态口径：{marker}")
    if "2026-09-08" not in text:
        issues.append("历史时点 2026-09-08 丢失（历史快照不应改写）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    cases = p03_cases()
    if len(cases) != 8:
        issues.append(f"P03 夹具例数已变（{len(cases)}）：本文清单需复核")
    if "8 例全过" not in text:
        issues.append("未写 P03 8 例全过（历史与现行一致）")
    fixtures = sorted(FIXTURES.glob("*_drill_cases.json"))
    if len(fixtures) != 8:
        issues.append(f"演练夹具份数已变（{len(fixtures)}）：现状对照需复核")
    if "8 份" not in text and "8 条管线" not in text:
        issues.append("未写练兵机制已扩到 8 条管线")
    law = dict(getattr(drill, "RULE_LAW", {}))
    if len(law) != 6:
        issues.append(f"RULE_LAW 条数已变（{len(law)}）：现状对照需复核")
    for rule, level in (("no_citation", "L1"), ("fabricated_id", "L2"),
                        ("browse_repeat", "L3"), ("semantic_misalignment", "L4")):
        if law.get(rule) != level:
            issues.append(f"RULE_LAW 映射漂移：{rule} 应为 {level}")
        if rule not in text:
            issues.append(f"正文缺历史映射：{rule}")
    if "cross_pipeline_id" not in text or "fabricated_asset_key" not in text:
        issues.append("现状对照缺新增映射 cross_pipeline_id / fabricated_asset_key")
    for path in (DRILL_MOD, DRILL_TEST):
        if not path.is_file():
            issues.append(f"载体缺件：{path.relative_to(ROOT).as_posix()}")
    if "test_state_header_acceptance_rule_law_mapping" not in text:
        issues.append("缺判级映射单测名")
    if "test_state_header_acceptance_rule_law_mapping" not in DRILL_TEST.read_text(
            encoding="utf-8"):
        issues.append("执行器判据文件缺 rule_law mapping 单测")
    for cmd in ("python -m core.execution_drill", "p03_drill_cases.json",
                "p04_drill_cases.json", "desktop/tests/test_execution_drill.py"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DrillDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_drill_doc_matches_contract(self):
        self.assertEqual([], drill_doc_issues(self.text), "演练集不满足契约")

    def test_fixture_and_mapping_are_live(self):
        self.assertEqual(8, len(p03_cases()))
        self.assertEqual(8, len(list(FIXTURES.glob("*_drill_cases.json"))))
        self.assertEqual(6, len(getattr(drill, "RULE_LAW", {})))

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 例数漂移 / 映射条数漂移 / 缺挂账 / 缺现状对照段 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史演练记录", "> **状态：现行", 1)
        self.assertTrue(any("历史演练记录" in i for i in drill_doc_issues(no_banner)))
        wrong_count = self.text.replace("8 例全过", "9 例全过")
        self.assertTrue(any("8 例全过" in i for i in drill_doc_issues(wrong_count)))
        no_new_rules = self.text.replace("cross_pipeline_id", "x").replace(
            "fabricated_asset_key", "y")
        self.assertTrue(any("cross_pipeline_id" in i or "新增映射" in i
                            for i in drill_doc_issues(no_new_rules)))
        no_hang = self.text.replace("仍挂账", "已销账")
        self.assertTrue(any("仍挂账" in i for i in drill_doc_issues(no_hang)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in drill_doc_issues(no_sec)))
        no_cmd = self.text.replace("p04_drill_cases.json", "其他夹具")
        self.assertTrue(any("p04" in i for i in drill_doc_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_drill.md")


if __name__ == "__main__":
    unittest.main()
