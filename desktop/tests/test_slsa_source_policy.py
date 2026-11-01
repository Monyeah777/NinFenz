#!/usr/bin/env python3
"""SLSA v1.2 Source Track control-readiness regression tests."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import slsa_source_policy as source  # noqa: E402


class SourceReadinessTest(unittest.TestCase):
    def _root_copy(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel in (source.READINESS_REL, source.CONTROLS_REL):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        return root

    @staticmethod
    def _load(root: Path, rel: str) -> dict:
        return json.loads((root / rel).read_text(encoding="utf-8"))

    @staticmethod
    def _write(root: Path, rel: str, doc: dict) -> None:
        (root / rel).write_text(json.dumps(doc), encoding="utf-8")

    def test_current_tree_is_honest_about_source_level(self):
        issues, stats = source.scan(ROOT)
        self.assertEqual([], issues)
        self.assertEqual(0, stats["claimed_level"])
        self.assertEqual(3, stats["target_level"])
        self.assertFalse(stats["source_vsa_available"])
        self.assertFalse(stats["source_provenance_available"])

    def test_nonzero_claim_requires_source_attestations(self):
        root = self._root_copy()
        doc = self._load(root, source.READINESS_REL)
        doc["claimed_level"] = 1
        self._write(root, source.READINESS_REL, doc)
        issues, _ = source.scan(root)
        self.assertTrue(any("Source VSA" in issue for issue in issues), issues)
        self.assertTrue(any("Source Provenance" in issue for issue in issues), issues)

    def test_main_must_forbid_force_push_and_deletion(self):
        root = self._root_copy()
        doc = self._load(root, source.CONTROLS_REL)
        doc["branch_protection"]["allow_force_pushes"] = True
        doc["branch_protection"]["allow_deletions"] = True
        self._write(root, source.CONTROLS_REL, doc)
        issues, _ = source.scan(root)
        self.assertTrue(any("force push" in issue for issue in issues), issues)
        self.assertTrue(any("deletion" in issue for issue in issues), issues)

    def test_ruleset_bypass_actor_is_rejected(self):
        root = self._root_copy()
        doc = self._load(root, source.CONTROLS_REL)
        doc["branch_ruleset"]["bypass_actors"] = [{"actor_id": 1}]
        self._write(root, source.CONTROLS_REL, doc)
        issues, _ = source.scan(root)
        self.assertTrue(any("bypass" in issue for issue in issues), issues)

    def test_tags_require_immutable_ruleset(self):
        root = self._root_copy()
        doc = self._load(root, source.CONTROLS_REL)
        doc["tag_ruleset"] = None
        self._write(root, source.CONTROLS_REL, doc)
        issues, _ = source.scan(root)
        self.assertTrue(any("tag" in issue.lower() for issue in issues), issues)

    def test_platform_attestation_claim_needs_evidence_url(self):
        root = self._root_copy()
        readiness = self._load(root, source.READINESS_REL)
        readiness["platform_attestations"]["source_vsa"] = True
        readiness["platform_attestations"]["source_provenance"] = True
        self._write(root, source.READINESS_REL, readiness)
        issues, _ = source.scan(root)
        self.assertTrue(any("Source VSA" in issue for issue in issues), issues)
        self.assertTrue(any("Source Provenance" in issue for issue in issues), issues)

    def test_collector_normalizes_only_required_platform_fields(self):
        responses = {
            "repos/Monyeah777/NinFenz": {
                "id": 1,
                "html_url": "https://github.com/Monyeah777/NinFenz",
                "default_branch": "main",
                "visibility": "public",
            },
            "repos/Monyeah777/NinFenz/branches/main/protection": {
                "required_status_checks": {
                    "strict": True,
                    "contexts": ["static-checks-42", "gate"],
                },
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": True,
                    "required_approving_review_count": 0,
                },
                "required_linear_history": {"enabled": True},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
                "enforce_admins": {"enabled": True},
                "required_conversation_resolution": {"enabled": True},
            },
            "repos/Monyeah777/NinFenz/rulesets": [
                {"id": 7, "name": "main", "target": "branch", "enforcement": "active"},
            ],
            "repos/Monyeah777/NinFenz/rulesets/7": {
                "id": 7,
                "name": "main",
                "target": "branch",
                "enforcement": "active",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                "rules": [
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "strict_required_status_checks_policy": True,
                            "required_status_checks": [{"context": "static-checks-42"}],
                        },
                    },
                    {
                        "type": "pull_request",
                        "parameters": {
                            "required_approving_review_count": 0,
                            "dismiss_stale_reviews_on_push": True,
                            "required_review_thread_resolution": True,
                        },
                    },
                ],
                "bypass_actors": [],
            },
        }

        def api(path: str):
            return responses[path]

        snapshot = source.collect(api, collected_at="2026-11-01T00:00:00Z")
        self.assertEqual("https://github.com/Monyeah777/NinFenz", snapshot["repository"]["url"])
        self.assertEqual(
            ["gate", "static-checks-42"], snapshot["branch_protection"]["required_status_checks"]
        )
        self.assertEqual([], snapshot["branch_ruleset"]["bypass_actors"])
        self.assertNotIn("token", json.dumps(snapshot).lower())

    def test_ci_gate_uses_live_source_controls(self):
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/ci-verify.yml").read_text(encoding="utf-8")
        )
        job = workflow["jobs"]["source-controls"]
        self.assertNotIn("env", job["steps"][-1])
        self.assertIn("slsa_source_readiness.py --live", job["steps"][-1]["run"])
        self.assertIn("source-controls", workflow["jobs"]["gate"]["needs"])

    def test_source_scanner_has_a_declared_consumer(self):
        from core import judgement_coverage

        self.assertIn(
            "scripts/slsa_source_readiness.py",
            judgement_coverage.consumers_of("slsa_source_policy", ROOT),
        )


if __name__ == "__main__":
    unittest.main()
