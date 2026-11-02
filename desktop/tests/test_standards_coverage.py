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
