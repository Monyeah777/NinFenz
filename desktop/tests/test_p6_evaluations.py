"""P6-04…P6-11 整改件判据：每条都必须会因为「缺一件」而变红，而不是永远为绿。

为什么这样判：这八项大多是**映射/取数**类交付物，最容易退化成「写得很全的散文」。
故每条判据都同时给**正向覆盖**（真仓全绿）与**变异自证**（抽掉一件必须红）。
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sm = _load("p6_sm", "scripts/standards_map.py")
dq = _load("p6_dq", "scripts/data_quality.py")
rb = _load("p6_rb", "scripts/risk_baseline.py")


class StandardsMapTest(unittest.TestCase):
    """P6-05 / P6-09 / P6-10。"""

    def test_real_repo_satisfies_all_three(self):
        rep = sm.report(ROOT)
        self.assertEqual([], rep["issues"], rep["issues"])
        self.assertTrue(rep["ok"])

    def test_iso29119_has_exactly_the_four_layers(self):
        self.assertEqual(sorted(sm.ISO29119_REQUIRED),
                         sorted(r["layer"] for r in sm.ISO29119_LAYERS))

    def test_ai_rmf_has_exactly_the_four_functions(self):
        self.assertEqual(sorted(sm.AI_RMF_REQUIRED),
                         sorted(r["function"] for r in sm.AI_RMF))

    def test_atam_rows_all_carry_risk_sensitivity_tradeoff(self):
        for row in sm.ATAM_SCENARIOS:
            for field in ("risk", "sensitivity", "tradeoff"):
                self.assertTrue(str(row.get(field) or "").strip(), f"{row['attribute']}.{field}")

    def test_missing_artifact_turns_red(self):
        issues = sm.check_mapping(sm.ISO29119_LAYERS, "layer", sm.ISO29119_REQUIRED,
                                  lambda _rel: False, "P6-05")
        self.assertEqual(len(sm.ISO29119_LAYERS), len(issues), issues)

    def test_wrong_coverage_turns_red(self):
        tampered = tuple({**r, "layer": "extra"} if i == 0 else r
                         for i, r in enumerate(sm.ISO29119_LAYERS))
        self.assertTrue(sm.check_mapping(tampered, "layer", sm.ISO29119_REQUIRED,
                                        lambda _rel: True, "P6-05"))


class ProvenanceAndDataQualityTest(unittest.TestCase):
    """P6-07 / P6-08。"""

    def test_real_repo_satisfies_both(self):
        rep = dq.report(ROOT)
        self.assertEqual([], rep["issues"], rep["issues"])

    def test_prov_three_ways_are_present_and_consistent(self):
        prov = dq.prov_graph(ROOT)
        self.assertTrue(prov["entities"] and prov["activities"] and prov["agents"])
        receipts = json.loads((ROOT / dq.RECEIPTS_REL).read_text(encoding="utf-8"))
        self.assertEqual(receipts["count"], len(prov["entities"]),
                         "PROV 实体数必须与回执自述 count 一致")

    def test_missing_source_turns_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            prov = dq.prov_graph(Path(tmp))
        self.assertFalse(prov["ok"])
        self.assertEqual([], prov["entities"])

    def test_vector_quality_detects_a_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            vdir = Path(tmp) / dq.VECTOR_DIR
            vdir.mkdir(parents=True)
            (vdir / "jcs_conformance.json").write_text(json.dumps({"schema": "nf-test-vectors/1",
                "vectors": [{"id": "x", "level": "L1", "compare_rule": "byte",
                             "expected": "{}", "langs": {}}]}), encoding="utf-8")
            rep = dq.vector_quality(Path(tmp))
        flat = " ".join(rep["issues"])
        self.assertIn("spec_clause", flat)
        self.assertFalse(rep["fair"]["findable"])

    def test_real_vector_set_is_fair_on_all_four_letters(self):
        fair = dq.vector_quality(ROOT)["fair"]
        self.assertEqual({"findable", "accessible", "interoperable", "reusable"}, set(fair))
        self.assertTrue(all(fair.values()), fair)


class RiskAndBaselineTest(unittest.TestCase):
    """P6-04 / P6-06 / P6-11。"""

    def test_stride_covers_exactly_six_classes_with_evidence(self):
        rep = rb.stride_report(ROOT)
        self.assertEqual([], rep["issues"], rep["issues"])
        self.assertEqual(sorted(rb.STRIDE_CLASSES),
                         sorted(r["class"] for r in rep["rows"]))
        self.assertTrue(all(r["evidence_present"] for r in rep["rows"]))

    def test_stride_missing_evidence_turns_red(self):
        rep = rb.stride_report(ROOT, exists=lambda _rel: False)
        self.assertFalse(rep["ok"])
        self.assertEqual(len(rb.STRIDE_CLASSES),
                         len([i for i in rep["issues"] if "不在场" in i]))

    def test_no_metric_is_reported_without_a_basis(self):
        """反造假的核心判据：**每个有数字的键必须带出处，每个空键必须写清缺什么**。"""
        m = rb.dora_metrics(ROOT)
        self.assertEqual(sorted(rb.DORA_KEYS), sorted(m["dora"]))
        self.assertEqual(sorted(rb.SPACE_KEYS), sorted(m["space"]))
        for group in (m["dora"], m["space"]):
            for key, val in group.items():
                if val["value"] is not None:
                    self.assertTrue(str(val.get("basis") or "").strip(), f"{key} 无出处")
                else:
                    self.assertTrue(str(val.get("why") or "").strip(), f"{key} 无缺席原因")

    def test_tags_give_real_deployment_and_lead_time(self):
        m = rb.dora_metrics(ROOT)
        self.assertIsNotNone(m["dora"]["deployment_frequency"]["value"])
        self.assertIsNotNone(m["dora"]["lead_time_for_changes"]["value"])
        self.assertGreater(m["dora_derived"]["tag_count"], 5)
        self.assertGreater(m["dora_derived"]["lead_samples"], 0)

    def test_change_failure_rate_comes_from_the_incident_registry(self):
        m = rb.dora_metrics(ROOT)
        cfr = m["dora"]["change_failure_rate"]
        self.assertIsNotNone(cfr["value"])
        self.assertIn(rb.POSTMORTEM_DIR, cfr["basis"])
        posts = rb.postmortems(ROOT)
        self.assertTrue(posts, "复盘件应被读到（本仓的正式事故登记面）")

    def test_time_to_restore_is_unknown_only_for_a_named_reason(self):
        m = rb.dora_metrics(ROOT)
        mttr = m["dora"]["time_to_restore"]
        if mttr["value"] is None:
            self.assertIn("restored", mttr["why"])
        else:
            self.assertTrue(mttr["basis"])

    def test_records_face_can_compute_both_remaining_keys(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp) / "rec.json"
            rec.write_text(json.dumps({"schema": rb.RECORDS_SCHEMA, "deployments": [
                {"id": "a", "failed": False},
                {"id": "b", "failed": True, "restored_s": 1200}]}), encoding="utf-8")
            dora = rb.dora_metrics(ROOT, "", str(rec))["dora"]
        self.assertEqual(0.5, dora["change_failure_rate"]["value"])
        self.assertEqual(20.0, dora["time_to_restore"]["value"])

    def test_measured_counts_are_positive(self):
        counts = rb.dora_metrics(ROOT)["counts"]
        self.assertGreater(counts["test_files"], 100)
        self.assertGreater(counts["verify_checks"], 10)
        self.assertGreater(counts["core_modules"], 100)

    def test_default_speedup_curve_is_present_and_sourced(self):
        curve = rb.dora_metrics(ROOT)["speedup_curve"]
        self.assertTrue(curve, "缺省基线（protocol/generated/eval_timings.json）应在场")
        self.assertGreaterEqual(len(curve), 2)
        for row in curve:
            self.assertTrue(row["source"], "无出处的数字不得进报告")
            self.assertIsNotNone(row["speedup"])

    def test_speedup_curve_needs_sourced_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps({"samples": [
                {"face": "gate-check", "before_s": 137.13, "after_s": 11.71,
                 "source": "计划 §23.59 落地版实测"}]}), encoding="utf-8")
            curve = rb.dora_metrics(ROOT, str(good))["speedup_curve"]
            self.assertEqual(1, len(curve))
            self.assertAlmostEqual(11.71, curve[0]["speedup"], places=2)
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"samples": [{"face": "x", "before_s": 2, "after_s": 1}]}),
                           encoding="utf-8")
            self.assertIsNone(rb.dora_metrics(ROOT, str(bad))["speedup_curve"],
                              "无出处的数字不入报告")

    def test_evaluation_digest_is_reproducible(self):
        a = rb.evaluation_digest(ROOT)
        b = rb.evaluation_digest(ROOT)
        self.assertEqual(a["digest"], b["digest"], "P6-11：同输入必须同输出")
        self.assertEqual(4, len(a["parts"]))
        self.assertTrue(a["digest"].startswith("sha256:"))

    def test_digest_changes_when_an_input_changes(self):
        base = rb.evaluation_digest(ROOT)["digest"]
        with tempfile.TemporaryDirectory() as tmp:
            extra = Path(tmp) / "t.json"
            extra.write_text(json.dumps({"samples": [
                {"face": "x", "before_s": 2.0, "after_s": 1.0, "source": "s"}]}), encoding="utf-8")
            self.assertNotEqual(base, rb.evaluation_digest(ROOT, str(extra))["digest"])


if __name__ == "__main__":
    unittest.main()
