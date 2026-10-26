#!/usr/bin/env python3
"""OSPS/S2C2F evidence and attestation workflow regression tests."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "npm-publish.yml"


class SupplyChainEvidenceTest(unittest.TestCase):
    def test_controls_cover_every_active_l1_l2_requirement(self):
        proc = subprocess.run(
            [sys.executable, "scripts/supply_chain_policy.py", "--json"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(0, proc.returncode, proc.stderr or proc.stdout)
        doc = json.loads(proc.stdout)
        self.assertEqual([], doc["issues"])
        self.assertEqual(43, doc["stats"]["osps"]["controls"])
        self.assertEqual(13, doc["stats"]["s2c2f"]["controls"])
        self.assertEqual(4, doc["stats"]["package_sources"]["sources"])
        self.assertGreaterEqual(doc["stats"]["suppliers"]["suppliers"], 7)

    def test_partial_or_na_controls_keep_an_explicit_gap(self):
        for rel in ("packaging/supply-chain/osps-l1-l2.json",
                    "packaging/supply-chain/s2c2f-l1-l2.json"):
            doc = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            entries = doc.get("controls") or doc.get("requirements") or []
            for entry in entries:
                if entry["status"] in {"partial", "not-applicable"}:
                    self.assertTrue(entry.get("gap"), f"{rel}/{entry['id']} 缺 gap")

    def test_package_sources_are_https_without_credentials(self):
        from urllib.parse import urlparse

        doc = json.loads((ROOT / "packaging/supply-chain/package-sources.json")
                         .read_text(encoding="utf-8"))
        for source in doc["sources"]:
            url = urlparse(source["url"])
            self.assertEqual("https", url.scheme, source)
            self.assertFalse(url.username, source)
            self.assertFalse(url.password, source)

    def test_supplier_register_has_no_unapproved_or_unknown_license(self):
        doc = json.loads((ROOT / "packaging/supply-chain/suppliers.json")
                         .read_text(encoding="utf-8"))
        allowed = set(doc["licenses_allowed"])
        for supplier in doc["suppliers"]:
            self.assertEqual("approved", supplier["decision"], supplier)
            self.assertTrue(supplier["source"].startswith("https://"), supplier)
            self.assertTrue(supplier["license"] == "service" or supplier["license"] in allowed,
                            supplier)


class ReleaseProvenanceWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.jobs = cls.doc["jobs"]

    def test_pr_is_dry_run_and_manual_publish_defaults_off(self):
        self.assertIn("pull_request", self.doc[True])
        dispatch = self.doc[True]["workflow_dispatch"]
        self.assertFalse(dispatch["inputs"]["publish"]["default"])
        self.assertEqual("boolean", dispatch["inputs"]["publish"]["type"])
        self.assertNotIn("NPM_TOKEN", json.dumps(self.jobs["build"], ensure_ascii=False))

    def test_attestation_is_hosted_oidc_and_publish_depends_on_it(self):
        attest = self.jobs["attest"]
        self.assertEqual("write", attest["permissions"]["id-token"])
        self.assertEqual("write", attest["permissions"]["attestations"])
        steps = attest["steps"]
        attest_steps = [step for step in steps if str(step.get("uses", "")).startswith(
            "actions/attest-build-provenance@")]
        self.assertEqual(1, len(attest_steps), "缺 build provenance attestation")
        self.assertEqual(
            "actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8",
            attest_steps[0]["uses"],
        )
        subject = attest_steps[0]["with"]["subject-path"]
        for suffix in (".tgz", ".cdx.json", ".spdx3.json", "SHA256SUMS"):
            self.assertIn(suffix, subject)
        self.assertEqual(["build", "attest"], self.jobs["publish-npm"]["needs"])
        self.assertEqual(
            ["build", "attest", "publish-npm", "publish-github-packages"],
            self.jobs["github-release"]["needs"],
        )

    def test_workflow_never_interpolates_untrusted_metadata_into_shell(self):
        dangerous = ("github.ref_name", "github.head_ref", "github.event.pull_request",
                     "github.event.issue", "github.event.comment")

        def walk(value, name):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "run" and isinstance(child, str):
                        for needle in dangerous:
                            self.assertNotIn(
                                f"${{{{ {needle}",
                                child,
                                f"{name}: run 块直接插值不可信元数据：{needle}",
                            )
                    else:
                        walk(child, name)
            elif isinstance(value, list):
                for child in value:
                    walk(child, name)

        for path in sorted(WORKFLOW.parent.glob("*.yml")):
            walk(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)

    def test_build_is_reproducible_and_sboms_are_validated_before_attestation(self):
        build = json.dumps(self.jobs["build"], ensure_ascii=False)
        for needle in (
            "packaging/npm/tools/build_release.py",
            "--verify .artifacts/release",
            "scripts/validate_sboms.py",
            "scripts/supply_chain_policy.py",
            "tools/verify-tarball.mjs",
        ):
            self.assertIn(needle, build)
        self.assertIn("sha256sum -c SHA256SUMS",
                      json.dumps(self.jobs["publish-npm"], ensure_ascii=False))
        checkout = next(step for step in self.jobs["build"]["steps"]
                        if str(step.get("uses", "")).startswith("actions/checkout@"))
        self.assertFalse(checkout["with"]["persist-credentials"])


if __name__ == "__main__":
    unittest.main()
