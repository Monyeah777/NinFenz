#!/usr/bin/env python3
"""docs/ccos/research-methods-v0.md 契约：研究层文档必须「8 方法/7 切片/depth 映射与实现一致」。

为什么必须有：这层是「怎么钻一个问题」的计划器规范——方法库条数、切片数、depth 映射、确定性、
只出计划不出结论，任何一项漂移都会让计划不可复现。本轮补最后更新位、现状对照与复现口径，
并把方法库（每条含 steps≥2/output/falsifier）、切片 7 面、depth 映射、16 项判据、CLI 用法活绑定。

范围：只判本文与 research_methods.json/cognition_plan/判据事实自洽（不改方法库）。同族判据：
test_cognition_plan.py（16 例）/ test_cognition.py（行话与分档）/ test_doc_hygiene.py /
test_doc_examples.py。
契约：最后更新位 + 复核、8 方法 M1–M8 在文且数据 8 条、每条 steps≥2/output/falsifier、
切片 7（S1–S7）与 7 面名在文、depth 1→3/2→5/3→7、16 例判据、CLI 三旗标、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cognition_plan as cp  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "research-methods-v0.md"
DATA = ROOT / "protocol" / "research_methods.json"
TEST = ROOT / "desktop" / "tests" / "test_cognition_plan.py"
NF = ROOT / "scripts" / "nf.py"
METHOD_IDS = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8")
FACES = ("定义", "机制", "证据", "边界", "对比", "量级", "落地")
SECTIONS = ("## 相关文档", "## 解决什么", "## 方法库", "## 用法", "## 判据（可证）",
            "## 现状对照", "## 复现与引用口径", "## 边界（不承诺）")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"研究层文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("研究层文档为空")
    return text


def methods() -> list:
    return json.loads(DATA.read_text(encoding="utf-8"))["methods"]


def plan_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def research_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 研究层 v0"):
        issues.append("缺标题「# 研究层 v0（认知核：切片检索词 + 方法论路径）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    ms = methods()
    if len(ms) != 8:
        issues.append(f"方法库条数已变（{len(ms)}）")
    for mid in METHOD_IDS:
        if mid not in text:
            issues.append(f"正文缺方法：{mid}")
    for m in ms:
        if str(m.get("id")) not in METHOD_IDS:
            issues.append(f"方法 id 异常：{m.get('id')}")
        if len(m.get("steps") or []) < 2:
            issues.append(f"{m.get('id')} steps < 2")
        for key in ("output", "falsifier", "title", "when"):
            if not str(m.get(key) or "").strip():
                issues.append(f"{m.get('id')} 缺字段 {key}")
    slices = list(getattr(cp, "SLICES", []))
    if len(slices) != 7:
        issues.append(f"切片数已变（{len(slices)}）")
    for sid in ("S1", "S2", "S3", "S4", "S5", "S6", "S7"):
        if sid not in [s.get("id") for s in slices]:
            issues.append(f"切片缺 id：{sid}")
    for face in FACES:
        if face not in text:
            issues.append(f"正文缺切片面：{face}")
    depth = dict(getattr(cp, "_DEPTH_N", {}))
    if depth != {1: 3, 2: 5, 3: 7}:
        issues.append(f"depth 映射已变：{depth}")
    for mapping in ("1→3", "2→5", "3→7"):
        if mapping not in text:
            issues.append(f"正文缺 depth 映射：{mapping}")
    n_cases = plan_cases()
    if n_cases != 16:
        issues.append(f"test_cognition_plan 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text and str(n_cases) + " 例" not in text:
        issues.append(f"未写判据数（{n_cases}）")
    nf = NF.read_text(encoding="utf-8")
    for flag in ("--list-methods", "--plan", "--methods"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    if "en_needs_human" not in text:
        issues.append("缺「不编造英文检索词」口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("nf cognition --list-methods",
                'nf cognition --plan "水印抗转码" --depth 2',
                "python -m pytest desktop/tests/test_cognition_plan.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ResearchMethodsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_research_matches_contract(self):
        self.assertEqual([], research_issues(self.text), "研究层文档不满足契约")

    def test_method_data_live(self):
        ms = methods()
        self.assertEqual(8, len(ms))
        for m in ms:
            self.assertGreaterEqual(len(m["steps"]), 2)
            self.assertTrue(str(m["falsifier"]).strip())
        self.assertEqual(7, len(cp.SLICES))
        self.assertEqual({1: 3, 2: 5, 3: 7}, dict(cp._DEPTH_N))
        self.assertEqual(16, plan_cases())

    def test_contract_catches_mutations(self):
        """变异自证：缺方法 / 切片面缺失 / depth 映射回退 / 例数漂移 / 缺命令。"""
        no_m = self.text.replace("M8", "M9")
        self.assertTrue(any("M8" in i for i in research_issues(no_m)))
        no_face = self.text.replace("量级", "数量")
        self.assertTrue(any("量级" in i for i in research_issues(no_face)))
        old_depth = self.text.replace("2→5", "2→4")
        self.assertTrue(any("depth" in i for i in research_issues(old_depth)))
        old_n = self.text.replace("16 项", "12 项")
        self.assertTrue(any("例数" in i or "16" in i for i in research_issues(old_n)))
        no_cmd = self.text.replace("python -m pytest desktop/tests/test_cognition_plan.py",
                                   "跑判据")
        self.assertTrue(any("test_cognition_plan" in i for i in research_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_research.md")


if __name__ == "__main__":
    unittest.main()
