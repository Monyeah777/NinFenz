#!/usr/bin/env python3
"""docs/42_M1_协议可执行性自测规范 契约：口径不变 + 规则集 6 条 + 覆盖/单测现状 + 复现口径。

为什么必须有：这是「协议可执行性自测」的规范档（指令类），写着 4 条规则 / 单测 3 例 / 1 集夹具。
但 44 drill 扩展后：规则 **6 条**（+cross_pipeline_id、fabricated_asset_key）、单测 **18 例**、
演练集 **8 集**。规范口径（内部演练≠外部转正、GWT 三段式、诚实标注、防过拟合）不变，但规则表
与验收实况必须更新，否则按本文实现捕获器会漏两类失范。本轮补状态横幅、规则表两行、现状对照、
复现口径，并把规则集/夹具/单测事实立成机检断言。

范围：只判本文与 execution_drill/44 真源自洽（不改规范口径）。同族判据：
test_execution_drill.py / test_drill_doc_contract.py / test_p06_drill_contract.py /
test_doc_hygiene.py（指令档标识与 last-updated）。
契约：⛔ 标识 + last-updated、六节 + 现状对照 + 复现口径、规则表 6 条与 RULE_LAW 一致、
P03 夹具 8 例（guard 4）、单测 18 例、夹具 8 集、44 覆盖真源在场、FIELD-001 挂账、
历史快照值（PASS 39 / 3 例）保留。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import execution_drill as drill  # noqa: E402

DOC = ROOT / "docs" / "42_M1_协议可执行性自测规范.md"
P03 = ROOT / "desktop" / "tests" / "fixtures" / "execution" / "p03_drill_cases.json"
FIXTURES = ROOT / "desktop" / "tests" / "fixtures" / "execution"
DRILL_TEST = ROOT / "desktop" / "tests" / "test_execution_drill.py"
COVER_DOC = ROOT / "docs" / "44_M1_执行演练扩展.md"
SECTIONS = ("## 一、目的与定位", "## 二、演练格式", "## 三、样本诚实标注纪律",
            "## 四、回归触发点", "## 五、变异自检规程", "## 六、当前验收实况",
            "## 现状对照", "## 复现与引用口径")
RULES = ("fabricated_id", "browse_repeat", "no_citation", "semantic_misalignment",
         "cross_pipeline_id", "fabricated_asset_key")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"规范档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("规范档为空")
    return text


def p03_guard_count() -> int:
    cases = json.loads(P03.read_text(encoding="utf-8")).get("cases") or []
    return sum(1 for c in cases if c.get("guard"))


def _test_count() -> int:
    return DRILL_TEST.read_text(encoding="utf-8").count("def test")


def spec_issues(text: str) -> list:
    issues = []
    if "⛔ 操作指令" not in text:
        issues.append("指令档缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "v1 规范" not in text or "复核扩写" not in text:
        issues.append("缺「v1 规范 → 复核扩写」状态口径")
    if "内部演练 ≠ 外部转正" not in text:
        issues.append("规范口径「内部演练 ≠ 外部转正」丢失")
    law = dict(getattr(drill, "RULE_LAW", {}))
    if len(law) != 6:
        issues.append(f"RULE_LAW 条数已变（{len(law)}）")
    for rule in RULES:
        if rule not in text:
            issues.append(f"规则表缺规则：{rule}")
        if rule not in law:
            issues.append(f"RULE_LAW 缺规则：{rule}")
    if "6 条" not in text:
        issues.append("未写现行规则 6 条")
    cases = json.loads(P03.read_text(encoding="utf-8")).get("cases") or []
    if len(cases) != 8 or p03_guard_count() != 4:
        issues.append(f"P03 夹具形态已变（{len(cases)} 例 / guard {p03_guard_count()}）")
    if "8 例" not in text or "guard 4/4" not in text:
        issues.append("未写 P03 8 例 / guard 4/4 现状")
    n_cases = _test_count()
    if n_cases != 18:
        issues.append(f"test_execution_drill 例数已变（{n_cases}）：现状对照需复核")
    if "18 例" not in text:
        issues.append("未写单测现行 18 例")
    n_fixtures = len(list(FIXTURES.glob("*_drill_cases.json")))
    if n_fixtures != 8:
        issues.append(f"演练夹具份数已变（{n_fixtures}）")
    if "8 集" not in text:
        issues.append("未写演练集现行 8 集")
    if not COVER_DOC.is_file():
        issues.append("缺覆盖真源：docs/44_M1_执行演练扩展.md")
    else:
        cover = COVER_DOC.read_text(encoding="utf-8")
        if "cross_pipeline_id" not in cover or "fabricated_asset_key" not in cover:
            issues.append("44 覆盖真源缺新增规则")
    if "docs/44_M1_执行演练扩展.md" not in text:
        issues.append("正文未指向 44 覆盖真源")
    if "仍挂账" not in text:
        issues.append("缺 FIELD-001 仍挂账标注")
    if "PASS=39" not in text:
        issues.append("历史快照值 PASS=39 被改写")
    for cmd in ("python -m core.execution_drill", "test_execution_drill.py"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class SelfTestSpecContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_spec_matches_contract(self):
        self.assertEqual([], spec_issues(self.text), "自测规范不满足契约")

    def test_rules_and_cases_live(self):
        self.assertEqual(6, len(getattr(drill, "RULE_LAW", {})))
        self.assertEqual(8, len(json.loads(P03.read_text(encoding="utf-8"))["cases"]))
        self.assertEqual(4, p03_guard_count())
        self.assertEqual(18, _test_count())
        self.assertEqual(8, len(list(FIXTURES.glob("*_drill_cases.json"))))

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 规则回退 / 例数漂移 / 缺挂账 / 缺覆盖真源 / 缺现状对照。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in spec_issues(no_marker)))
        no_rule = self.text.replace("cross_pipeline_id", "x").replace(
            "fabricated_asset_key", "y")
        self.assertTrue(any("cross_pipeline_id" in i or "规则表" in i
                            for i in spec_issues(no_rule)))
        wrong = self.text.replace("18 例", "3 例")
        self.assertTrue(any("18 例" in i for i in spec_issues(wrong)))
        no_hang = self.text.replace("仍挂账", "已销账")
        self.assertTrue(any("仍挂账" in i for i in spec_issues(no_hang)))
        no_cover = self.text.replace("docs/44_M1_执行演练扩展.md", "覆盖文档")
        self.assertTrue(any("44" in i for i in spec_issues(no_cover)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in spec_issues(no_sec)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_spec.md")


if __name__ == "__main__":
    unittest.main()
