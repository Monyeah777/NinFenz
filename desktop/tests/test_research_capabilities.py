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
    contract_codegen,
    contracts,
    experiment_health,
    feature_gate,
    incremental,
    lineage,
    pbe,
    property_check,
    provenance,
    smt_constraints,
    solver_policy,
    strings,
    tier_gate,
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



class SmtConstraintTest(unittest.TestCase):
    def test_sat_or_backtracking(self):
        out = smt_constraints.assign_sections(
            ["s1", "s2"], [constraints.Slot("a"), constraints.Slot("b")],
            {("s1", "a"): 1.0, ("s2", "b"): 1.0})
        self.assertEqual(out["status"], "sat")
        self.assertEqual(out["assignment"], {"s1": "a", "s2": "b"})

    def test_unsat(self):
        out = smt_constraints.assign_sections(
            ["s1"], [constraints.Slot("a"), constraints.Slot("b")])
        self.assertEqual(out["status"], "unsat")
        self.assertTrue(out["core"] or out.get("engine") == "backtracking")

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


class FeatureGateTest(unittest.TestCase):
    def test_deterministic_rollout_and_variant(self):
        flags = [feature_gate.Flag(
            "f", rollout_percentage=100,
            variants=(feature_gate.Variant("a", 50), feature_gate.Variant("b", 50)))]
        gate = feature_gate.FeatureGate(flags, salt="s")
        first = gate.evaluate("f", "user-1")
        second = gate.evaluate("f", "user-1")
        self.assertEqual(first["bucket"], second["bucket"])
        self.assertEqual(first["variant"], second["variant"])
        self.assertIn(first["variant"], {"a", "b"})
        self.assertEqual(len(gate.exposures_for("f")), 2)

    def test_rollout_boundaries_and_unknown(self):
        off = feature_gate.FeatureGate([feature_gate.Flag("off", rollout_percentage=0)])
        self.assertFalse(off.evaluate("off", "u")["enabled"])
        self.assertEqual(off.evaluate("missing", "u")["reason"], "unknown_flag")
        with self.assertRaises(ValueError):
            feature_gate.FeatureGate([feature_gate.Flag(
                "bad", variants=(feature_gate.Variant("a", 101),))])

    def test_duplicate_or_empty_key_rejected(self):
        with self.assertRaises(ValueError):
            feature_gate.FeatureGate([feature_gate.Flag("x"), feature_gate.Flag("x")])
        with self.assertRaises(ValueError):
            feature_gate.FeatureGate([feature_gate.Flag("")])


class ExperimentHealthTest(unittest.TestCase):
    def test_healthy(self):
        snap = experiment_health.Snapshot(
            "e", ("a", "b"), {"a": 100, "b": 100}, metric_events=200)
        out = experiment_health.health(snap)
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["can_conclude"])

    def test_no_metric_or_empty_arm_blocks(self):
        snap = experiment_health.Snapshot(
            "e", ("a", "b"), {"a": 100, "b": 0}, metric_events=0)
        out = experiment_health.health(snap)
        self.assertEqual(out["status"], "blocked")
        codes = {f["code"] for f in out["findings"]}
        self.assertIn("empty_arm", codes)
        self.assertIn("no_metric_events", codes)

    def test_imbalance_is_warning_not_blocker(self):
        snap = experiment_health.Snapshot(
            "e", ("a", "b"), {"a": 100, "b": 400}, metric_events=500)
        out = experiment_health.health(snap)
        self.assertEqual(out["status"], "ok")
        self.assertIn("imbalanced_arms", {f["code"] for f in out["findings"]})

    def test_changed_bucketing_blocks(self):
        snap = experiment_health.Snapshot(
            "e", ("a", "b"), {"a": 100, "b": 100}, metric_events=200,
            bucketing_changed=True)
        self.assertFalse(experiment_health.health(snap)["can_conclude"])



class ContractCodegenTest(unittest.TestCase):
    def test_kotlin_shape(self):
        out = contract_codegen.kotlin("SlotView")
        self.assertIn("data class SlotView(", out)
        self.assertIn("val id: String", out)
        self.assertIn("val required: Boolean", out)


    def test_cli_generates_types(self):
        import subprocess
        import sys
        proc = subprocess.run(
            [sys.executable, "scripts/contract_codegen.py", "--lang", "kotlin"],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
            check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("data class ImportView", proc.stdout)

    def test_typescript_optional(self):
        out = contract_codegen.typescript("RecipeRef")
        self.assertIn("export interface RecipeRef", out)
        self.assertIn("id: string;", out)
        self.assertIn("version?: number;", out)

    def test_bad_schema_rejected(self):
        with self.assertRaises(KeyError):
            contract_codegen.kotlin("Missing")

class TierGateTest(unittest.TestCase):
    def test_free_daily_path_never_locked(self):
        for cap in ("import", "preview", "edit", "export", "share", "reset"):
            self.assertTrue(tier_gate.check("free", cap)["allowed"])

    def test_pro_and_ccos_boundaries(self):
        self.assertFalse(tier_gate.check("free", "protocol_author")["allowed"])
        self.assertTrue(tier_gate.check("pro", "protocol_author")["allowed"])
        self.assertFalse(tier_gate.check("pro", "execute_task")["allowed"])
        self.assertTrue(tier_gate.check("ccos", "execute_task")["allowed"])
        with self.assertRaises(PermissionError):
            tier_gate.require("free", "graph_edit")
        with self.assertRaises(ValueError):
            tier_gate.check("vip", "import")

    def test_studio_tui_are_hosts(self):
        self.assertTrue(tier_gate.check("studio", "studio_inspect")["allowed"])
        self.assertTrue(tier_gate.check("tui", "tui_inspect")["allowed"])
        self.assertFalse(tier_gate.check("free", "studio_inspect")["allowed"])


class ContractsTest(unittest.TestCase):
    def test_import_roundtrip(self):
        view = contracts.ImportView(
            "ready", "t", (contracts.SlotView("GOAL", "目标", "v"),),
            ("issue",), "r1", 2)
        back = contracts.ImportView.from_dict(view.to_dict())
        self.assertEqual(back, view)

    def test_project_roundtrip(self):
        p = contracts.ProjectSummary("p1", "t", "ready", 4, "r1")
        self.assertEqual(contracts.ProjectSummary.from_dict(p.to_dict()), p)

    def test_bad_schema_rejected(self):
        with self.assertRaises(ValueError):
            contracts.ImportView.from_dict({"schema": "bad"})
        with self.assertRaises(ValueError):
            contracts.ProjectSummary.from_dict({"schema": "bad"})

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
