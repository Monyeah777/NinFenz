import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import eval_collapse as E  # noqa: E402


class Test(unittest.TestCase):
    def test_collapsed_mean_not_global(self):
        per = {"a": [1.0, 1.0, 1.0, 1.0], "b": [0.0]}
        self.assertEqual(0.5, E.collapsed_mean(per))

    def test_regression_guard(self):
        self.assertEqual(1, len(E.regression_guard(0.9, 0.5, 0.01, raw_global=0.95)))
        self.assertEqual([], E.regression_guard(0.9, 0.8, 0.01, raw_global=0.85))

    def test_empty(self):
        self.assertEqual(0.0, E.collapsed_mean({}))
