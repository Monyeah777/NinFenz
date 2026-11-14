#!/usr/bin/env python3
"""docs/44_M1 契约：8 集口径与夹具一致 + 测试参数化 8/8 + 保真面现状 + 复现口径。

为什么必须有：本文件是演练覆盖的**真源**，但曾出现「文字写测试参数化 8 集、实现只 7 套（缺 p07_en
lexicon 接线）」的口径漂移——读者会以为英文集已被常驻判据覆盖。本轮把实现补齐（_hits 接 lexicon
+ FIXTURES 加 p07_en），并让判据**活绑定**：夹具份数/每集例数/测试 FIXTURES 名单/规则集条数，
任何一处变化即打红。

范围：只判本文与夹具/测试/保真面事实自洽（不改演练集）。同族判据：
test_execution_drill.py（18 例参数化）/ test_drill_doc_contract.py（P03 记录）/
test_p06_drill_contract.py（P06 记录）/ test_doc_hygiene.py（指令档标识）。
契约：⛔ 标识 + last-updated、覆盖表 + 结构 + 验收 + 现状对照 + 复现口径、8 份夹具与每集例数
（8/8/8/12/8/8/9/8）、测试 FIXTURES 8 份含 p07_en 且 _hits 传 lexicon、RULE_LAW 6 条、
drill_fidelity 脚本与真源在场、历史值 PASS=72 保留、「8/8」口径在场。
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

DOC = ROOT / "docs" / "44_M1_执行演练扩展.md"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "execution"
TEST = ROOT / "desktop" / "tests" / "test_execution_drill.py"
FIDELITY = ROOT / "scripts" / "drill_fidelity.py"
FID_JSON = ROOT / "protocol" / "drill_fidelity.json"
SECTIONS = ("## 演练集覆盖", "## 每集结构", "## 验收", "## 现状对照", "## 复现与引用口径")
EXPECT_COUNTS = {
    "p01_drill_cases.json": 8, "p02_drill_cases.json": 8, "p03_drill_cases.json": 8,
    "p04_drill_cases.json": 12, "p05_drill_cases.json": 8, "p06_drill_cases.json": 8,
    "p07_en_drill_cases.json": 9, "p90_drill_cases.json": 8,
}


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"44 M1 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("44 M1 文档为空")
    return text


def fixture_counts() -> dict:
    return {p.name: len(json.loads(p.read_text(encoding="utf-8")).get("cases") or [])
            for p in sorted(FIXTURES.glob("*_drill_cases.json"))}


def _test_fixtures() -> list:
    text = TEST.read_text(encoding="utf-8")
    m = re.search(r"FIXTURES\s*=\s*\[FIX_DIR / n\s*\n\s*for n in \((.*?)\)\]", text, re.S)
    if not m:
        return []
    return [p.strip().strip('"') for p in m.group(1).split(",") if ".json" in p]


def m1_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 44 · 执行演练扩展"):
        issues.append("缺标题「# 44 · 执行演练扩展」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "覆盖真源仍现行" not in text:
        issues.append("缺「覆盖真源仍现行」状态声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    counts = fixture_counts()
    if counts != EXPECT_COUNTS:
        issues.append(f"夹具例数已变：{counts}")
    if "8 集" not in text:
        issues.append("未写 8 集覆盖")
    if "p04 = 12" not in text:
        issues.append("未写 P04 12 例（p04 = 12）")
    if "p07_en" not in text:
        issues.append("未写 p07_en（多语集）")
    fx = _test_fixtures()
    if len(fx) != 8 or "p07_en_drill_cases.json" not in fx:
        issues.append(f"test_execution_drill FIXTURES 未覆盖 8 套/缺 p07_en：{fx}")
    test_text = TEST.read_text(encoding="utf-8")
    if 'data.get("lexicon")' not in test_text:
        issues.append("_hits 未传 fixture lexicon（p07_en 会漏判）")
    if len(getattr(drill, "RULE_LAW", {})) != 6:
        issues.append("RULE_LAW 条数已变")
    if "6 条" not in text:
        issues.append("未写规则 6 条")
    for path in (FIDELITY, FID_JSON):
        if not path.is_file():
            issues.append(f"保真面缺件：{path.relative_to(ROOT).as_posix()}")
    if "drill_fidelity.py" not in text:
        issues.append("未引用保真量化脚本")
    if "check35" not in text:
        issues.append("未写保真面消费判据 check35")
    if "8/8" not in text:
        issues.append("缺「测试参数化 8/8」口径")
    if "PASS=72" not in text:
        issues.append("历史值 PASS=72 被改写")
    for cmd in ("python -m core.execution_drill", "test_execution_drill.py",
                "python scripts/drill_fidelity.py --json"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class M1DrillCoverageContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m1_matches_contract(self):
        self.assertEqual([], m1_issues(self.text), "44 M1 文档不满足契约")

    def test_fixtures_and_parameterization_live(self):
        self.assertEqual(EXPECT_COUNTS, fixture_counts())
        fx = _test_fixtures()
        self.assertEqual(8, len(fx))
        self.assertIn("p07_en_drill_cases.json", fx)
        self.assertIn('data.get("lexicon")', TEST.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 例数漂移 / 去 p07_en / 缺 8/8 / 缺现状对照 / 缺复现命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in m1_issues(no_marker)))
        wrong = self.text.replace("p04 = 12", "p04 = 8").replace("P04 6/6", "P04 4/4")
        self.assertTrue(any("p04 = 12" in i or "例数" in i for i in m1_issues(wrong)))
        no_en = self.text.replace("p07_en", "多语集")
        self.assertTrue(any("p07_en" in i for i in m1_issues(no_en)))
        no_claim = self.text.replace("8/8", "7/8")
        self.assertTrue(any("8/8" in i for i in m1_issues(no_claim)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in m1_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/drill_fidelity.py --json", "跑保真")
        self.assertTrue(any("drill_fidelity" in i for i in m1_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m1.md")


if __name__ == "__main__":
    unittest.main()
