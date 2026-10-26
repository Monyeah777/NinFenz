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


class BackendDifferentialTest(unittest.TestCase):
    """P-A3：朴素与半朴素**两条后端必须同结果**（随机语料 + 紧燃料对照）。"""

    def _random_doc(self, seed):
        import random
        rnd = random.Random(seed)
        consts = ["c0", "c1", "c2"]
        preds = ["p0", "p1"]
        facts = [{"pred": rnd.choice(preds), "args": [rnd.choice(consts), rnd.choice(consts)]}
                 for _ in range(rnd.randint(2, 6))]
        rules = []
        for _ in range(rnd.randint(1, 3)):
            h = rnd.choice(preds)
            b1 = {"pred": rnd.choice(preds), "args": ["?X", "?Y"]}
            rules.append({"head": {"pred": h, "args": ["?X", "?Y"]}, "body": [b1]})
        rules.append({"head": {"pred": "p0", "args": ["?X", "?Z"]},
                      "body": [{"pred": "p0", "args": ["?X", "?Y"]},
                               {"pred": "p0", "args": ["?Y", "?Z"]}]})
        return {"schema": "nf-nfal-rules/1", "facts": facts, "rules": rules}

    def test_backends_agree_on_random_corpus(self):
        bad = []
        nontrivial = 0
        for seed in range(40):
            doc = self._random_doc(seed)
            a = nr.evaluate(doc)
            b = nr.evaluate_seminaive(doc)
            base = {"%s(%s)" % (f["pred"], ",".join(str(x) for x in f["args"]))
                    for f in doc["facts"]}
            if set(a["facts"]) - base:
                nontrivial += 1
            if a["status"] != b["status"] or a["facts"] != b["facts"]:
                bad.append((seed, a["status"], b["status"],
                            set(a["facts"]) ^ set(b["facts"])))
        self.assertEqual([], bad, "两后端分歧：%s" % bad[:3])
        self.assertGreater(nontrivial, 10, "语料太浅（几乎无新增事实）——差分判据近乎空转")

    def test_backends_agree_on_cycles_and_guards(self):
        doc = _doc(edges=(("a", "b"), ("b", "a")), guard=True)
        a, b = nr.evaluate(doc), nr.evaluate_seminaive(doc)
        self.assertEqual(a["facts"], b["facts"])
        self.assertEqual("OK", b["status"])

    def test_dag_backend_agrees_and_reports_graph(self):
        """P-A4：第三后端（显式推导图）与另两后端事实集必须逐条相同，并给出图统计。"""
        for doc in (self._random_doc(7), _doc(), _doc(edges=(("a", "b"), ("b", "a"))),
                    _doc(edges=(("a", "a"), ("a", "b")), guard=True)):
            a, b, c = nr.evaluate(doc), nr.evaluate_seminaive(doc), nr.evaluate_dag(doc)
            self.assertEqual(a["facts"], c["facts"], doc)
            self.assertEqual(b["facts"], c["facts"], doc)
            self.assertEqual("OK", c["status"], doc)
            self.assertGreaterEqual(c["graph"]["depth"], 1)
            self.assertGreaterEqual(c["graph"]["edges"], 1)

    def test_dag_backend_is_deterministic(self):
        self.assertEqual(nr.evaluate_dag(_doc()), nr.evaluate_dag(_doc()))

    def test_seminaive_uses_no_more_fuel(self):
        doc = _doc()
        a, b = nr.evaluate(doc), nr.evaluate_seminaive(doc)
        self.assertLessEqual(b["fuel_used"], a["fuel_used"],
                             "半朴素不该比朴素更费（它是优化，不是另一套语义）")


if __name__ == "__main__":
    unittest.main()
