#!/usr/bin/env python3
"""Standards four-state ledger: derivation and fail-closed mutations."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import standards_coverage as sc  # noqa: E402


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class CurrentLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_current_ledger_is_valid_and_has_consumable_examples(self):
        self.assertEqual([], self.issues)
        self.assertGreaterEqual(self.report["summary"]["catalogued"], 370)
        self.assertGreaterEqual(self.report["summary"]["asserted"], 8)
        self.assertEqual(
            self.report["summary"]["asserted"],
            self.report["summary"]["consumable"],
        )
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertEqual("consumable", rows["junit-xml"]["state"])
        self.assertTrue(rows["junit-xml"]["asserted"])

    def test_unbound_catalog_is_explicit(self):
        self.assertGreaterEqual(self.report["summary"]["not_domain_bound"], 300)
        self.assertEqual(
            self.report["summary"]["not_domain_bound"],
            len(self.report["not_domain_bound"]),
        )

    def test_committed_report_is_fresh(self):
        issues, _report = sc.check(ROOT)
        self.assertEqual([], issues)


class Rfc8785LedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_rfc8785_jcs_is_consumable_and_keeps_internal_rule_separate(self):
        self.assertEqual([], self.issues)
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertIn("rfc8785-jcs", rows)
        row = rows["rfc8785-jcs"]
        self.assertEqual("data", row["layer"])
        self.assertEqual("consumable", row["state"])
        self.assertTrue(row["asserted"])

        ledger = json.loads(
            (ROOT / "protocol" / "standards_assertions.json").read_text(encoding="utf-8")
        )
        claim = next(
            item for item in ledger["claims"] if item["id"] == "jcs-three-implementation-contract"
        )
        self.assertEqual("rfc8785-jcs", claim["standard"])
        self.assertIn(
            "desktop/tests/test_jcs_spec_gap.py::JcsSpecGapTest.test_astral_key_order_differs_from_spec",
            claim["negative_tests"],
        )
        consumer_paths = {item["path"] for item in claim["consumers"]}
        self.assertEqual(
            {
                "scripts/jcs.py",
                "scripts/cross_lang_verify.py",
                "engine/rust/canonical/src/main.rs",
                "engine/dotnet/tools/nf-canonical/Jcs.cs",
            },
            consumer_paths,
        )


class MultiformatsCidLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_multiformats_cid_is_consumable_with_fail_closed_profile(self):
        self.assertEqual([], self.issues)
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertIn("multiformats-cid", rows)
        row = rows["multiformats-cid"]
        self.assertEqual("data", row["layer"])
        self.assertEqual("consumable", row["state"])
        self.assertTrue(row["asserted"])

        ledger = json.loads(
            (ROOT / "protocol" / "standards_assertions.json").read_text(encoding="utf-8")
        )
        claim = next(
            item for item in ledger["claims"] if item["id"] == "cidv1-raw-sha256-profile"
        )
        self.assertEqual("multiformats-cid", claim["standard"])
        self.assertIn(
            "desktop/tests/test_interop_export.py::InteropExportTest.test_cidv1_profile_rejects_non_profile_cids",
            claim["negative_tests"],
        )
        consumer_paths = {item["path"] for item in claim["consumers"]}
        self.assertEqual(
            {
                "desktop/src/core/interop_export.py",
                "scripts/interop_thirdparty_kit.py",
                "engine/dotnet/src/Nf.Engine/Interop.cs",
            },
            consumer_paths,
        )


class Iso29119LedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_iso29119_four_layer_mapping_is_consumable(self):
        self.assertEqual([], self.issues)
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertIn("iso-iec-ieee-29119", rows)
        row = rows["iso-iec-ieee-29119"]
        self.assertEqual("eng", row["layer"])
        self.assertEqual("consumable", row["state"])
        self.assertTrue(row["asserted"])

        ledger = json.loads(
            (ROOT / "protocol" / "standards_assertions.json").read_text(encoding="utf-8")
        )
        claim = next(
            item for item in ledger["claims"]
            if item["id"] == "iso29119-four-layer-evidence"
        )
        self.assertEqual("iso-iec-ieee-29119", claim["standard"])
        self.assertIn(
            "desktop/tests/test_p6_evaluations.py::StandardsMapTest.test_missing_artifact_turns_red",
            claim["negative_tests"],
        )
        consumer_paths = {item["path"] for item in claim["consumers"]}
        self.assertEqual(
            {"scripts/standards_map.py", "scripts/risk_baseline.py"},
            consumer_paths,
        )


class CycloneDxVexLedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_cyclonedx_vex_is_consumable_with_dual_format_parity(self):
        self.assertEqual([], self.issues)
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertIn("cyclonedx-vex", rows)
        row = rows["cyclonedx-vex"]
        self.assertEqual("eng", row["layer"])
        self.assertEqual("consumable", row["state"])
        self.assertTrue(row["asserted"])
        self.assertTrue(row["domain_bound"])

        ledger = json.loads(
            (ROOT / "protocol" / "standards_assertions.json").read_text(encoding="utf-8")
        )
        claim = next(
            item for item in ledger["claims"]
            if item["id"] == "cyclonedx-vex-dual-format"
        )
        self.assertEqual("cyclonedx-vex", claim["standard"])
        self.assertIn(
            "desktop/tests/test_supply_chain_l3.py::VexTest.test_openvex_cyclonedx_mismatch_is_rejected",
            claim["negative_tests"],
        )
        consumer_paths = {item["path"] for item in claim["consumers"]}
        self.assertEqual(
            {
                "scripts/generate_vex.py",
                "packaging/npm/tools/build_release.py",
                "scripts/build_vsa.py",
                "scripts/validate_cyclonedx_vex.py",
            },
            consumer_paths,
        )


class Rfc3161LedgerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.issues, cls.report = sc.build(ROOT)

    def test_rfc3161_is_consumable_with_fail_closed_time_proof(self):
        self.assertEqual([], self.issues)
        rows = {row["id"]: row for row in self.report["standards"]}
        self.assertIn("rfc3161-tsp", rows)
        row = rows["rfc3161-tsp"]
        self.assertEqual("eng", row["layer"])
        self.assertEqual("consumable", row["state"])
        self.assertTrue(row["asserted"])
        self.assertTrue(row["domain_bound"])

        ledger = json.loads(
            (ROOT / "protocol" / "standards_assertions.json").read_text(encoding="utf-8")
        )
        claim = next(
            item for item in ledger["claims"]
            if item["id"] == "rfc3161-offline-time-proof"
        )
        self.assertEqual("rfc3161-tsp", claim["standard"])
        self.assertIn(
            "desktop/tests/test_timestamp.py::LocalTsaTest.test_tampered_token_and_record_are_rejected",
            claim["negative_tests"],
        )
        consumer_paths = {item["path"] for item in claim["consumers"]}
        self.assertEqual(
            {"scripts/time_stamp.py", "desktop/src/core/timestamp.py"},
            consumer_paths,
        )


class LedgerMutationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _write(
            self.root,
            "desktop/tests/test_sample.py",
            "import unittest\n"
            "class SampleTest(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n"
            "    def test_reject_bad(self): self.assertRaises(ValueError, int, 'x')\n",
        )
        _write(self.root, "scripts/consumer.py", "def consume():\n    return 'sample'\n")
        _write(self.root, "verify.sh", "check1(){ :; }\ncheck2(){ :; }\n")
        _write(self.root, "evidence.json", "{}\n")
        _write(self.root, "protocol/assertions.json", json.dumps({
            "schema": "nf-assertions/1",
            "assertions": [{"id": "sample-rule"}],
        }))
        self.catalog = {
            "schema": "nf-standards-catalog/1",
            "coverage": {
                "standards": 1, "reachable": 1, "unreachable": 0,
                "depends_edges": 0, "by_layer": {
                    "data": 0, "eng": 1, "form": 0, "gov": 0, "iface": 0,
                }, "bodies": 1,
            },
            "standards": [{
                "id": "sample", "body": "Example", "title": "Sample",
                "url": "https://example.invalid/sample", "ext_points": ["extension"],
                "layer": "eng",
                "evidence": {"reachable": True},
            }],
        }
        self.binding = {
            "schema": "nf-standards-binding/1", "catalog": sc.CATALOG_REL,
            "count": 1, "bindings_total": 1, "support_bindings_total": 0,
            "packs": [{"code": "P1", "bindings": [{"standard": "sample"}]}],
        }
        self.ledger = {
            "schema": sc.SCHEMA,
            "claims": [{
                "id": "sample-runtime", "standard": "sample",
                "assertion": "sample has executable evidence",
                "tests": ["desktop/tests/test_sample.py::SampleTest.test_ok"],
                "negative_tests": [
                    "desktop/tests/test_sample.py::SampleTest.test_reject_bad"
                ],
                "checks": ["check2"],
                "assertion_ids": ["sample-rule"],
                "evidence": ["evidence.json"],
                "consumers": [{"path": "scripts/consumer.py", "symbol": "consume"}],
            }],
        }

    def _validate(self):
        return sc.validate_documents(
            self.root, copy.deepcopy(self.catalog), copy.deepcopy(self.binding),
            copy.deepcopy(self.ledger),
        )

    def test_valid_synthetic_claim_reaches_consumable(self):
        issues, report = self._validate()
        self.assertEqual([], issues)
        self.assertEqual("consumable", report["standards"][0]["state"])

    def test_unknown_standard_and_duplicate_claim_are_rejected(self):
        self.ledger["claims"].append(dict(self.ledger["claims"][0]))
        self.ledger["claims"].append(dict(
            self.ledger["claims"][0],
            id="unknown-standard",
            standard="not-in-catalog",
        ))
        issues, _ = self._validate()
        self.assertTrue(any("claim id 重复" in issue for issue in issues), issues)
        self.assertTrue(any("未知 standard" in issue for issue in issues), issues)

    def test_positive_and_negative_evidence_are_both_required(self):
        self.ledger["claims"][0]["negative_tests"] = []
        issues, _ = self._validate()
        self.assertTrue(any("negative_tests 必须非空" in issue for issue in issues), issues)

    def test_missing_test_symbol_and_consumer_fail_closed(self):
        self.ledger["claims"][0]["tests"] = [
            "desktop/tests/test_sample.py::SampleTest.test_missing"
        ]
        self.ledger["claims"][0]["consumers"][0]["symbol"] = "missing_consumer"
        issues, _ = self._validate()
        self.assertTrue(any("测试方法不存在" in issue for issue in issues), issues)
        self.assertTrue(any("consumer symbol 不存在" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
