import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import verifier_props as V  # noqa: E402


def _raises(x):
    raise ValueError("boom")


def _exhaustive(_):
    return ["a", "b"]


class Test(unittest.TestCase):
    def test_no_throw_detects(self):
        self.assertEqual(1, len(V.no_throw(_raises, [1])))

    def test_exhaustive(self):
        self.assertEqual([], V.exhaustive(_exhaustive, None, 2))
        self.assertEqual(1, len(V.exhaustive(lambda _: ["a"], None, 2)))

    def test_purity(self):
        def impure():
            import os  # noqa: F401
            return os.getcwd()
        self.assertTrue(V.purity(impure))
