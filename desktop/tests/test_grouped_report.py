"""分组报告判据：先分组再汇总；单样本组不能谈方差；只报总体要被判据拦下。

依据（筛选台账 #13 Model Cards / 评测设计包 `ev.effect_and_variance`）：
只报一个总体均值会掩盖子群差异。本判据盯：分组均值/标准差正确、单样本组被点名、
缺失分组被点名、文本表与结构化结果同源。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import grouped_report as gr  # noqa: E402


class GroupedReportTest(unittest.TestCase):
    def setUp(self):
        self.rows = [{"cond": "free", "score": 1.0}, {"cond": "free", "score": 3.0},
                     {"cond": "menu", "score": 5.0}, {"cond": "menu", "score": 7.0}]

    def test_group_means_and_sd(self):
        doc = gr.summarize(self.rows, "cond", "score")
        self.assertEqual("nf-grouped-report/1", doc["schema"])
        self.assertAlmostEqual(2.0, doc["groups"]["free"]["mean"])
        self.assertAlmostEqual(6.0, doc["groups"]["menu"]["mean"])
        self.assertAlmostEqual(1.414214, doc["groups"]["free"]["sd"], places=5)
        self.assertEqual(4, doc["overall"]["n"])
        self.assertIn("只作对照", doc["note"])

    def test_clean_report_has_no_issues(self):
        self.assertEqual([], gr.verify(gr.summarize(self.rows, "cond", "score")))

    def test_single_sample_group_is_flagged(self):
        doc = gr.summarize(self.rows + [{"cond": "hybrid", "score": 9.0}], "cond", "score")
        issues = gr.verify(doc)
        self.assertTrue(any("n<2" in i for i in issues), issues)
        self.assertIsNone(doc["groups"]["hybrid"]["sd"], "n=1 时 sd 必须是 None，不能报 0")

    def test_missing_groups_is_flagged(self):
        doc = gr.summarize(self.rows, "cond", "score")
        doc["groups"] = {}
        self.assertTrue(any("没有分组" in i for i in gr.verify(doc)))
        doc["groups"] = {"only": {"n": 5, "mean": 1.0, "sd": 0.1}}
        self.assertTrue(any("至少两个分组" in i for i in gr.verify(doc)))

    def test_bad_input_fails_closed(self):
        with self.assertRaises(ValueError) as ctx:
            gr.summarize([], "cond", "score")
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(ValueError):
            gr.summarize([{"cond": "a"}], "cond", "score")
        with self.assertRaises(ValueError):
            gr.summarize([{"cond": "a", "score": "x"}], "cond", "score")

    def test_table_matches_structured_values(self):
        doc = gr.summarize(self.rows, "cond", "score")
        table = gr.render_table(doc)
        for name in ("free", "menu"):
            self.assertIn(name, table)
            self.assertIn(str(doc["groups"][name]["mean"]), table)
        self.assertIn("总体，仅对照", table)


if __name__ == "__main__":
    unittest.main()