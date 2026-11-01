"""report_meta 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import report_meta as R  # noqa: E402


class Test(unittest.TestCase):
    def test_digest_is_order_insensitive(self):
        self.assertEqual(R.input_digest({"a": 1, "b": 2}), R.input_digest({"b": 2, "a": 1}))

    def test_valid_meta(self):
        self.assertEqual([], R.validate(R.make_meta("check1-40", {"x": 1}, 10)))

    def test_zero_denominator_confident_rejected(self):
        self.assertTrue(R.validate(R.make_meta("m", {}, 0, "confident")))

    def test_tentative_requires_reason(self):
        self.assertTrue(R.validate(R.make_meta("m", {}, 3, "tentative")))
        self.assertEqual([], R.validate(R.make_meta("m", {}, 3, "tentative", "样本仅 3")))
