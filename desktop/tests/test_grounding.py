"""锚点回验（core.grounding）单测：归一/转述容忍/未锚定不丢件。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import grounding as G  # noqa: E402


class NormalizeTest(unittest.TestCase):
    def test_punctuation_and_space_removed(self):
        self.assertEqual(G.normalize("人工智能，体 架构！！"), G.normalize("人工智能体架构"))

    def test_tokens_are_words_and_cjk_chars(self):
        self.assertEqual(G.tokens("M00 数据基座"), ["m00", "数", "据", "基", "座"])


class OverlapTest(unittest.TestCase):
    def test_identical_is_one(self):
        self.assertEqual(1.0, G.overlap("模块契约必须可解析", "模块契约必须可解析"))

    def test_paraphrase_tolerated(self):
        # 标点/语序差异 + 增删虚词：归一后整串包含 → 1.0
        self.assertEqual(1.0, G.overlap("模块契约必须可解析", "模块契约，必须可解析。"))

    def test_token_ratio_for_reordered_paraphrase(self):
        score = G.overlap("模块 契约 可解析", "可解析的模块契约")
        self.assertGreaterEqual(score, 0.8)

    def test_unrelated_is_low(self):
        self.assertLess(G.overlap("模块契约可解析", "天气与季节推进"), 0.8)


class VerifyAnchorsTest(unittest.TestCase):
    def test_all_anchored(self):
        ok, un = G.verify_anchors(
            ["M00 数据基座提供状态槽", "M80 输出呈现生成正文"],
            ["M00 数据基座提供状态槽（见 01 §2）", "M80 输出呈现负责生成正文"])
        self.assertTrue(ok)
        self.assertEqual(un, [])

    def test_unanchored_is_reported_not_dropped(self):
        ok, un = G.verify_anchors(["凭空多出的事实点"], ["完全无关的来源正文"])
        self.assertFalse(ok)
        self.assertEqual(len(un), 1)
        self.assertIn("fact", un[0])
        self.assertIn("best", un[0])
        self.assertIn("reason", un[0])

    def test_blank_facts_are_ignored(self):
        self.assertEqual((True, []), G.verify_anchors(["", "   "], ["来源"]))


if __name__ == "__main__":
    unittest.main()
