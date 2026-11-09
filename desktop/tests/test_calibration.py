"""校准度量判据：把「口头置信是否可信」变成可算的可靠性表（只计数，不评分）。

依据（paper-screening 台账 #1/#2）：元认知 = 监控 × 控制，度量看**校准**而非「说得更肯定」。
本判据盯三件事：① 完美校准 → ECE 0；② 过度自信 → ECE 明确变大；③ 坏输入 fail-closed。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import calibration as cal  # noqa: E402


class CalibrationTest(unittest.TestCase):
    def test_perfectly_calibrated_has_zero_ece(self):
        """ECE 只看「箱内均值 vs 箱内命中率」：置信 0 全错、置信 1 全对 → 恰好 0。"""
        self.assertAlmostEqual(0.0, cal.ece([0.0, 1.0], [0.0, 1.0], n_bins=2), places=6)
        # 箱内均值与命中率相等就是校准（哪怕只有一半对）：ECE 仍应为 0
        self.assertAlmostEqual(0.0, cal.ece([0.5, 0.5], [0.0, 1.0], n_bins=2), places=6)
        # 置信 0.9 而实际一半错 → 明显偏离，ECE 必须 > 0
        self.assertGreater(cal.ece([0.9, 0.9], [0.0, 1.0], n_bins=2), 0.0)

    def test_overconfidence_increases_ece(self):
        conf = [0.9] * 10
        ok = [1.0] * 9 + [0.0]
        lean = cal.ece(conf, ok, n_bins=10)
        conf_bad = [0.9] * 10
        ok_bad = [0.0] * 10
        heavy = cal.ece(conf_bad, ok_bad, n_bins=10)
        self.assertGreater(heavy, lean)

    def test_bins_cover_all_samples_once(self):
        conf = [0.05, 0.15, 0.55, 0.95, 1.0]
        ok = [0, 1, 1, 0, 1]
        rows = cal.bins(conf, ok, n_bins=10)
        self.assertEqual(len(conf), sum(r["count"] for r in rows))
        self.assertEqual(10, len(rows))
        # 空箱不给假数字：mean_conf/accuracy 必须是 None
        self.assertTrue(all(r["mean_conf"] is None for r in rows if r["count"] == 0))

    def test_bad_input_fails_closed(self):
        with self.assertRaises(ValueError) as ctx:
            cal.bins([0.5], [1.0, 0.0])
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(ValueError):
            cal.bins([], [])
        with self.assertRaises(ValueError):
            cal.bins([1.5], [1.0])
        with self.assertRaises(ValueError):
            cal.bins([0.5], [2.0])
        with self.assertRaises(ValueError):
            cal.bins([0.5], [1.0], n_bins=0)

    def test_reliability_schema_and_note(self):
        doc = cal.reliability([0.2, 0.8], [0, 1], n_bins=2)
        self.assertEqual("nf-calibration/1", doc["schema"])
        self.assertEqual(2, doc["n"])
        self.assertIn("不是质量分", doc["note"])

    def test_trigger_policy_is_a_trigger_not_evidence(self):
        """口头置信 ≤ 阈值 → 触发复核；它只作触发器（返回里明确写「不算证据」）。"""
        res = cal.trigger_policy([0.2, 0.6, 0.9], 0.6)
        self.assertEqual("nf-calibration-trigger/1", res["schema"])
        self.assertEqual([0, 1], res["triggered"], "≤ 阈值的都要触发（含等号）")
        self.assertEqual([2], res["skipped"])
        self.assertEqual({"trigger": 2, "skip": 1}, res["counts"])
        self.assertIn("不算证据", res["note"])

    def test_trigger_policy_rejects_bad_threshold_and_empty(self):
        with self.assertRaises(ValueError) as ctx:
            cal.trigger_policy([0.5], 1.5)
        self.assertIn("修复指引", str(ctx.exception))
        with self.assertRaises(ValueError):
            cal.trigger_policy([], 0.5)


if __name__ == "__main__":
    unittest.main()
