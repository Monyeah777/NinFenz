"""injection_ledger 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import injection_ledger as L  # noqa: E402


class Test(unittest.TestCase):
    def test_unjudged_is_first_class(self):
        d = {}
        L.record_injection(d, "t1", "M00")
        L.record_injection(d, "t1", "M80")
        L.record_outcome(d, "t1", True)
        L.judge_effect(d, "t1", "M00", L.USED)
        r = L.report(d)
        self.assertEqual(1, r["used"])
        self.assertEqual(1, r["unjudged"])
        self.assertEqual("t1", r["pairs"][0]["turn"])

    def test_bad_effect_rejected(self):
        with self.assertRaises(ValueError):
            L.judge_effect({}, "t", "x", "maybe")
