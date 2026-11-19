#!/usr/bin/env python3
"""研究能力模块单测：PBE/字符串/增量/约束/类型/lineage/effi/属性/协作。"""
import sys
import unittest
from pathlib import Path

if str(Path(__file__).resolve().parent.parent / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.research import (
    collab,
    constraints,
    incremental,
    lineage,
    pbe,
    property_check,
    provenance,
    solver_policy,
    strings,
    typed_template,
)


class PbeTest(unittest.TestCase):
    def test_learn_bullets(self):
        result = pbe.learn([pbe.Example("- a\n- b", "a；b"),
                            pbe.Example("- c", "c")])
        self.assertTrue(result.exact)
        self.assertEqual(result.program.ops, ("bullets_to_semicolon",))

    def test_reject_non_exact_recipe(self):
        result = pbe.learn([pbe.Example("a", "b")])
        with self.assertRaises(ValueError):
            pbe.to_recipe(result)
        with self.assertRaises(ValueError):
            pbe.learn([])


class StringTest(unittest.TestCase):
    def test_between(self):
        out = strings.learn([strings.ExtractExample("Hello [world]", "world"),
                             strings.ExtractExample("x [abc] y", "abc")])
        self.assertEqual(out["status"], "ok")
        self.assertIn("between", out["program"])

    def test_regex_and_no_solution(self):
        out = strings.learn([strings.ExtractExample("I have 17", "17")])
        self.assertIn("regex", out["program"])
        self.assertEqual(strings.learn([strings.ExtractExample("abc", "zzz")])["status"],
                         "no_solution")


class IncrementalTest(unittest.TestCase):
    def test_reuse_and_backdate(self):
        db = incremental.Database()
        db.set_input("source", "a  b")
        parse = lambda d: " ".join(d.input("source").split())  # noqa: E731
        db.query("parse", parse)
        db.query("parse", parse)
        self.assertEqual(db.executions, ["parse"])
        db.set_input("source", "a  b ")
        db.query("parse", parse)
        self.assertEqual(db.backdated, 1)

    def test_change_invalidates(self):
        db = incremental.Database()
        db.set_input("x", "1")
        db.query("q", lambda d: d.input("x"))
        db.set_input("x", "2")
        db.query("q", lambda d: d.input("x"))
        self.assertEqual(db.executions, ["q", "q"])


class ConstraintTest(unittest.TestCase):
    def test_sat(self):
        out = constraints.assign(["s1", "s2"],
                                 [constraints.Slot("a"), constraints.Slot("b")],
                                 {("s1", "a"): 1.0, ("s2", "b"): 1.0})
        self.assertEqual(out["status"], "sat")
        self.assertEqual(out["assignment"]["s1"], "a")

    def test_unsat_and_empty(self):
        out = constraints.assign(["s1"], [constraints.Slot("a"), constraints.Slot("b")])
        self.assertEqual(out["status"], "unsat")
        self.assertIn("a", out["core"])
        self.assertEqual(constraints.assign([], [])["status"], "error")


class TypedTemplateTest(unittest.TestCase):
    def test_missing_and_max(self):
        row = typed_template.RowType(
            {"x": typed_template.SlotType("x", max_len=2)}, open=True)
        self.assertEqual(typed_template.check_record({}, row).diagnostics[0]["code"],
                         "MISSING")
        self.assertEqual(typed_template.check_record({"x": "abc"}, row).diagnostics[0]["code"],
                         "MAX_LEN")

    def test_closed_rejects_extra(self):
        row = typed_template.RowType({"x": typed_template.SlotType("x")}, open=False)
        self.assertEqual(typed_template.check_record({"x": "v", "y": "v"}, row)
                         .diagnostics[0]["code"], "EXTRA")


class LineageTest(unittest.TestCase):
    def test_backward(self):
        g = lineage.ProvGraph()
        for ident in ("src", "out"):
            g.entity(ident)
        g.activity("act")
        g.used("act", "src")
        g.generated("out", "act")
        out = g.lineage("out")
        self.assertIn("src", out["nodes"])
        self.assertEqual(g.lineage("missing")["status"], "error")


class SolverPolicyTest(unittest.TestCase):
    def test_symbolic_skips_llm(self):
        called = []
        out = solver_policy.solve([1], lambda _e: [solver_policy.Candidate("ok", 1.0)],
                                  lambda _e: (called.append(1) or ([], 99)))
        self.assertEqual(out.source, "symbolic")
        self.assertFalse(called)
        self.assertEqual(out.tokens, 0)

    def test_fallback_uses_llm(self):
        out = solver_policy.solve([1], lambda _e: [solver_policy.Candidate("bad", 0.1)],
                                  lambda _e: ([solver_policy.Candidate("good", 1.0)], 12))
        self.assertEqual(out.source, "ensemble")
        self.assertEqual(out.best.value, "good")
        self.assertEqual(out.tokens, 12)


class PropertyTest(unittest.TestCase):
    def test_checks(self):
        self.assertEqual(property_check.check_max_len(3)["status"], "passed")
        self.assertEqual(property_check.check_required()["status"], "passed")
        self.assertEqual(property_check.check_closed_row()["status"], "passed")



class ProvenanceTest(unittest.TestCase):
    def test_sign_verify_and_tamper(self):
        doc = provenance.build("body", "x.md", recipe={"id": "r1"})
        signed = provenance.sign(doc, "key")
        self.assertTrue(provenance.verify(signed, "body", "key")["verified"])
        self.assertFalse(provenance.verify(signed, "tampered", "key")["verified"])

    def test_unsigned_is_not_authenticated(self):
        doc = provenance.build("body", "x.md")
        out = provenance.verify(doc, "body")
        self.assertTrue(out["verified"])
        self.assertFalse(out["authenticated"])

class CollabTest(unittest.TestCase):
    def test_confirmation_and_visibility(self):
        s = collab.Session(["agent", "human"])
        req = s.step("agent", "export", "x")
        self.assertEqual(req["status"], "needs_confirmation")
        self.assertEqual(s.confirm("human", req["id"])["status"], "ok")
        s.step("agent", "note", "secret", private=True)
        self.assertEqual(len(s.visible_to("human")), 3)
        self.assertEqual(len(s.visible_to("agent")), 4)

    def test_entropy_and_autonomy(self):
        s = collab.Session(["agent", "human"])
        s.step("agent", "edit")
        s.step("human", "edit")
        self.assertAlmostEqual(s.initiative_entropy(), 1.0)
        s.intervene("human", "stop")
        self.assertEqual(s.controlled_autonomy()["interventions"], 1)


if __name__ == "__main__":
    unittest.main()
