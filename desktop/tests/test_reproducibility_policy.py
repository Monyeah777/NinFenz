#!/usr/bin/env python3
"""Reproducible Builds evidence and overclaim regression tests."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import reproducibility_policy as policy  # noqa: E402


class ReproducibilityPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(
            (ROOT / policy.EVIDENCE_REL).read_text(encoding="utf-8")
        )
        cls.slsa = json.loads((ROOT / policy.SLSA_REL).read_text(encoding="utf-8"))

    def test_current_evidence_is_bound_to_slsa_run(self):
        issues, stats = policy.validate_doc(ROOT, self.doc, self.slsa)
        self.assertEqual([], issues)
        self.assertEqual(3, stats["artifacts"])

    def test_run_and_commit_must_match(self):
        doc = copy.deepcopy(self.doc)
        doc["run_id"] += 1
        doc["source_commit"] = "0" * 40
        issues, _ = policy.validate_doc(ROOT, doc, self.slsa)
        self.assertTrue(any("run_id" in issue for issue in issues), issues)
        self.assertTrue(any("source_commit" in issue for issue in issues), issues)

    def test_single_build_is_not_reproducibility(self):
        doc = copy.deepcopy(self.doc)
        doc["artifacts"][0]["builds"] = 1
        issues, _ = policy.validate_doc(ROOT, doc, self.slsa)
        self.assertTrue(any("2 次构建" in issue for issue in issues), issues)

    def test_digest_must_match_attested_subject(self):
        doc = copy.deepcopy(self.doc)
        doc["artifacts"][0]["sha256"] = "0" * 64
        issues, _ = policy.validate_doc(ROOT, doc, self.slsa)
        self.assertTrue(any("SLSA subject" in issue for issue in issues), issues)

    def test_cross_machine_overclaim_is_rejected(self):
        doc = copy.deepcopy(self.doc)
        doc["scope"] = "cross-machine"
        issues, _ = policy.validate_doc(ROOT, doc, self.slsa)
        self.assertTrue(any("跨机器" in issue for issue in issues), issues)

    def test_required_artifact_kind_cannot_disappear(self):
        doc = copy.deepcopy(self.doc)
        doc["artifacts"] = [row for row in doc["artifacts"]
                            if row["kind"] != "python-wheel"]
        issues, _ = policy.validate_doc(ROOT, doc, self.slsa)
        self.assertTrue(any("python-wheel" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
