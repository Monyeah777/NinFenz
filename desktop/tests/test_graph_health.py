"""graph_health 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import graph_health as H  # noqa: E402


class Test(unittest.TestCase):
    def test_unreachable_detected(self):
        r = H.analyze(["A", "B", "C"], [("A", "B")], ["A"])
        self.assertEqual(["C"], r["unreachable"])

    def test_over_outdegree(self):
        r = H.analyze(["A", "B", "C", "D"], [("A", "B"), ("A", "C"), ("A", "D")], ["A"], max_out=2)
        self.assertEqual(["A"], r["over_out"])

    def test_articulation(self):
        r = H.analyze(["A", "B", "C"], [("A", "B"), ("B", "C")], ["A"])
        self.assertIn("B", r["articulation"])
