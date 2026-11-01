import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import policy_snapshot as P  # noqa: E402


class Test(unittest.TestCase):
    def test_snapshot_is_order_insensitive(self):
        s1 = P.snapshot({"a": 1, "b": 2})
        s2 = P.snapshot({"b": 2, "a": 1})
        self.assertEqual(s1["digest"], s2["digest"])

    def test_matches(self):
        s = P.snapshot({"a": 1})
        self.assertTrue(P.matches(s, {"a": 1}))
        self.assertFalse(P.matches(s, {"a": 2}))
