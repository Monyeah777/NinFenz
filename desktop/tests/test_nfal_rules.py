# -*- coding: utf-8 -*-
"""core.nfal_rules 回归：定点推导 / guard / fuel 溢出 fail-closed / 确定性。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import nfal_rules as nr  # noqa: E402


def _doc(fuel=None, edges=(("a", "b"), ("b", "c")), guard=False):
    doc = {"schema": "nf-nfal-rules/1",
           "facts": [{"pred": "edge", "args": [x, y]} for x, y in edges],
           "rules": [
               {"head": {"pred": "reach", "args": ["?X", "?Y"]},
                "body": [{"pred": "edge", "args": ["?X", "?Y"]}]},
               {"head": {"pred": "reach", "args": ["?X", "?Z"]},
                "body": [{"pred": "reach", "args": ["?X", "?Y"]},
                         {"pred": "edge", "args": ["?Y", "?Z"]}]}]}
    if guard:
        doc["rules"][0]["body"].append({"guard": ["?X", "!=", "?Y"]})
        doc["rules"][1]["body"].append({"guard": ["?X", "!=", "?Z"]})
    if fuel is not None:
        doc["fuel"] = fuel
    return doc


class EvalTest(unittest.TestCase):
    def test_transitive_closure(self):
        got = nr.evaluate(_doc())
        self.assertEqual("OK", got["status"])
        for want in ("reach(a,b)", "reach(b,c)", "reach(a,c)"):
            self.assertIn(want, got["facts"], got["facts"])

    def test_cycle_terminates(self):
        got = nr.evaluate(_doc(edges=(("a", "b"), ("b", "a"))))
        self.assertEqual("OK", got["status"])
        self.assertIn("reach(b,a)", got["facts"])

    def test_guard_filters_self_loops(self):
        got = nr.evaluate(_doc(edges=(("a", "a"), ("a", "b")), guard=True))
        self.assertEqual("OK", got["status"])
        self.assertIn("reach(a,b)", got["facts"])
        self.assertNotIn("reach(a,a)", got["facts"], "guard 未拦住自环")

    def test_deterministic(self):
        self.assertEqual(nr.evaluate(_doc()), nr.evaluate(_doc()))

    def test_fuel_exhaustion_is_reported_not_silent(self):
        got = nr.evaluate(_doc(fuel=1))
        self.assertEqual("FUEL_EXHAUSTED", got["status"])
        self.assertGreater(got["fuel_used"], 1, "超限必须记到用量")
        self.assertTrue(got["facts"], "已达部分应保留（不静默清空）")

    def test_invalid_doc(self):
        self.assertTrue(nr.validate({"schema": "x"}))
        self.assertEqual("INVALID", nr.evaluate({"schema": "x"})["status"])

    def test_variable_convention(self):
        self.assertTrue(nr.is_var("?X"))
        self.assertFalse(nr.is_var("X"))


if __name__ == "__main__":
    unittest.main()
