#!/usr/bin/env python3
"""OpenSSF Security Insights v2.2.0 profile regression tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import security_insights  # noqa: E402


class SecurityInsightsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load(
            (ROOT / security_insights.PROFILE_REL).read_text(encoding="utf-8")
        )

    def test_current_profile_is_valid_and_fresh(self):
        issues, stats = security_insights.scan(ROOT, today=date(2026, 11, 2))
        self.assertEqual([], issues)
        self.assertEqual("2.2.0", stats["schema_version"])
        self.assertGreaterEqual(stats["tools"], 5)
        self.assertEqual(3, stats["attestations"])

    def test_schema_version_is_pinned(self):
        doc = copy.deepcopy(self.doc)
        doc["header"]["schema-version"] = "2.1.0"
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("schema-version" in issue for issue in issues), issues)

    def test_primary_contact_must_be_unambiguous(self):
        doc = copy.deepcopy(self.doc)
        doc["project"]["administrators"].append(
            {"name": "Duplicate", "primary": True}
        )
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("恰有一个" in issue for issue in issues), issues)

    def test_repository_must_be_active(self):
        doc = copy.deepcopy(self.doc)
        doc["repository"]["status"] = "abandoned"
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("status" in issue for issue in issues), issues)

    def test_stale_profile_fails(self):
        doc = copy.deepcopy(self.doc)
        doc["header"]["last-reviewed"] = "2026-01-01"
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("已过期" in issue for issue in issues), issues)

    def test_insecure_reference_is_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["project"]["homepage"] = "http://ninfenz.dev/"
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("HTTPS" in issue for issue in issues), issues)

    def test_release_attestations_are_complete(self):
        doc = copy.deepcopy(self.doc)
        doc["repository"]["release"]["attestations"] = []
        issues, _ = security_insights.validate_doc(ROOT, doc, date(2026, 11, 2))
        self.assertTrue(any("provenance" in issue for issue in issues), issues)
        self.assertTrue(any("verification_summary" in issue for issue in issues), issues)

    def test_evidence_is_bound_to_profile_digest(self):
        evidence = json.loads(
            (ROOT / security_insights.EVIDENCE_REL).read_text(encoding="utf-8")
        )
        digest = security_insights.hashlib.sha256(
            (ROOT / security_insights.PROFILE_REL).read_bytes()
        ).hexdigest()
        self.assertEqual(digest, evidence["subject_sha256"])
        self.assertEqual("2.2.0", evidence["schema_version"])
        self.assertEqual("PASS", evidence["cue_vet"])


if __name__ == "__main__":
    unittest.main()
