import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import value_replay as V  # noqa: E402


class Test(unittest.TestCase):
    def test_replay(self):
        self.assertTrue(V.replay(10.0, 10.4, 0.5))
        self.assertFalse(V.replay(10.0, 11.0, 0.5))

    def test_check(self):
        self.assertEqual([], V.check([{"id": "c1", "actual": 1, "expected": 1, "tolerance": 0}]))
        self.assertEqual(1, len(V.check([{"id": "c1", "actual": 2, "expected": 1, "tolerance": 0}])))
