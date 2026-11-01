#!/usr/bin/env python3
"""OSPS L3 evidence and fail-closed VEX/readiness negative tests."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VEX = _load("generate_vex")
VSA = _load("build_vsa")
READINESS = _load("slsa_l3_readiness")


class VexTest(unittest.TestCase):
    def _root_with_findings(self, findings):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        path = root / VEX.DISPOSITION_REL
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({
                "schema": "nf-vuln-disposition/1",
                "reviewed_at": "2026-10-27",
                "findings": findings,
            }),
            encoding="utf-8",
        )
        return root

    def test_not_affected_requires_justification_and_impact(self):
        root = self._root_with_findings([{
            "vulnerability": "CVE-2099-0001",
            "status": "not_affected",
        }])
        with self.assertRaisesRegex(ValueError, "justification/impact"):
            VEX.vex_doc(root)

    def test_affected_requires_action_statement(self):
        root = self._root_with_findings([{
            "vulnerability": "CVE-2099-0002",
            "status": "affected",
        }])
        with self.assertRaisesRegex(ValueError, "action_statement"):
            VEX.vex_doc(root)

    def test_unknown_status_is_rejected(self):
        root = self._root_with_findings([{
            "vulnerability": "CVE-2099-0003",
            "status": "probably-fine",
        }])
        with self.assertRaisesRegex(ValueError, "status 非法"):
            VEX.vex_doc(root)

    def test_empty_disposition_is_valid_openvex(self):
        doc = VEX.vex_doc(ROOT)
        self.assertEqual([], VEX.validate_vex(doc))
        self.assertEqual([], doc["statements"])
        self.assertEqual(doc, VEX.vex_doc(ROOT), "VEX ID 必须由内容寻址且可重复")

    def test_disposition_change_changes_vex_identity(self):
        first = VEX.vex_doc(self._root_with_findings([]))
        second = VEX.vex_doc(self._root_with_findings([{
            "vulnerability": "CVE-2099-0004",
            "status": "under_investigation",
            "action_statement": "Investigate reachability before release.",
        }]))
        self.assertNotEqual(first["@id"], second["@id"])


class ReadinessTest(unittest.TestCase):
    def _root_copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        readiness = json.loads(
            (ROOT / READINESS.READINESS_REL).read_text(encoding="utf-8")
        )
        rels = {
            READINESS.READINESS_REL,
            READINESS.POLICY_REL,
            READINESS.WORKFLOW_REL,
            READINESS.BUILDER_REL,
            READINESS.RELEASE_WORKFLOW_REL,
            READINESS.EVIDENCE_BUILDER_REL,
        }
        for row in readiness["requirements"]:
            rels.update(
                rel for rel in row["evidence"] if not str(rel).startswith("external:")
            )
        for rel in rels:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        return root

    def test_current_tree_claims_build_l3_consistently(self):
        issues, stats = READINESS.scan(ROOT)
        self.assertEqual([], issues)
        self.assertEqual("SLSA_BUILD_LEVEL_3", stats["claimed_level"])
        self.assertEqual({"satisfied": 6}, stats["statuses"])
        self.assertEqual(41309669898, stats["last_run_id"])

    def test_every_readiness_requirement_must_be_satisfied(self):
        root = self._root_copy()
        path = root / READINESS.READINESS_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        next(item for item in doc["requirements"]
             if item["id"] == "build-isolation")["status"] = "partial"
        path.write_text(json.dumps(doc), encoding="utf-8")
        issues, stats = READINESS.scan(root)
        self.assertEqual({"partial": 1, "satisfied": 5}, stats["statuses"])
        self.assertTrue(any("必须为 satisfied" in issue for issue in issues), issues)

    def test_policy_and_readiness_levels_must_agree(self):
        root = self._root_copy()
        path = root / READINESS.POLICY_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["verified_levels"] = ["SLSA_BUILD_LEVEL_2"]
        path.write_text(json.dumps(doc), encoding="utf-8")
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("verified_levels" in issue for issue in issues), issues)

    def test_caller_must_use_reusable_builder(self):
        root = self._root_copy()
        path = root / READINESS.WORKFLOW_REL
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "uses: ./.github/workflows/slsa-build-l3.yml",
                "uses: actions/checkout@" + "0" * 40,
            ),
            encoding="utf-8",
        )
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("reusable workflow" in issue for issue in issues), issues)

    def test_release_caller_must_use_reusable_evidence_builder(self):
        root = self._root_copy()
        path = root / READINESS.RELEASE_WORKFLOW_REL
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "uses: ./.github/workflows/release-evidence-l3.yml",
                "uses: actions/checkout@" + "0" * 40,
            ),
            encoding="utf-8",
        )
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("release.yml" in issue and "reusable" in issue for issue in issues),
                        issues)

    def test_reusable_builder_requires_internal_provenance_and_no_cache(self):
        root = self._root_copy()
        path = root / READINESS.BUILDER_REL
        text = path.read_text(encoding="utf-8")
        text = text.replace("actions/attest-build-provenance@", "actions/checkout@")
        text = text.replace(
            "python-version: '3.11'",
            "cache: pip\n          python-version: '3.11'",
        )
        path.write_text(text, encoding="utf-8")
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("内部生成 artifact provenance" in issue for issue in issues), issues)
        self.assertTrue(any("持久缓存" in issue for issue in issues), issues)

    def test_l3_requires_real_verified_run_evidence(self):
        root = self._root_copy()
        (root / READINESS.RUN_EVIDENCE_REL).unlink()
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("真实 L3 attestation 运行证据" in issue for issue in issues), issues)

    def test_l3_run_evidence_is_bound_to_workflow_contents(self):
        root = self._root_copy()
        path = root / READINESS.WORKFLOW_REL
        path.write_text(path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("验收运行后变更" in issue for issue in issues), issues)

    def test_pending_run_mode_only_relaxes_workflow_hash_staleness(self):
        root = self._root_copy()
        path = root / READINESS.WORKFLOW_REL
        path.write_text(path.read_text(encoding="utf-8") + "\n# pending\n", encoding="utf-8")
        evidence = root / READINESS.RUN_EVIDENCE_REL
        doc = json.loads(evidence.read_text(encoding="utf-8"))
        doc["provenance_verified"] = False
        evidence.write_text(json.dumps(doc), encoding="utf-8")
        old = os.environ.get(READINESS.PENDING_RUN_ENV)
        os.environ[READINESS.PENDING_RUN_ENV] = "1"
        try:
            issues, _ = READINESS.scan(root)
        finally:
            if old is None:
                os.environ.pop(READINESS.PENDING_RUN_ENV, None)
            else:
                os.environ[READINESS.PENDING_RUN_ENV] = old
        self.assertFalse(any("验收运行后变更" in issue for issue in issues), issues)
        self.assertTrue(any("provenance_verified" in issue for issue in issues), issues)

    def test_deprecated_generator_cannot_return(self):
        root = self._root_copy()
        path = root / READINESS.WORKFLOW_REL
        path.write_text(
            path.read_text(encoding="utf-8") + "\n# slsa-github-generator\n",
            encoding="utf-8",
        )
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("slsa-github-generator" in issue for issue in issues), issues)


class VsaPredicateTest(unittest.TestCase):
    def test_predicate_can_only_sign_policy_levels(self):
        policy = json.loads(
            (ROOT / "packaging/supply-chain/verification-policy.json")
            .read_text(encoding="utf-8")
        )
        doc = VSA.predicate(policy, "a" * 64, "b" * 40, "123", "2026-10-27T00:00:00Z")
        self.assertEqual(["SLSA_BUILD_LEVEL_3"], doc["verifiedLevels"])
        self.assertEqual("PASSED", doc["verificationResult"])
        self.assertEqual({"sha256": "a" * 64}, doc["policy"]["digest"])

    def test_l3_policy_is_rejected_when_readiness_is_incomplete(self):
        readiness = {
            "schema": "nf-slsa-l3-readiness/2",
            "standard": "SLSA v1.2 Build L3",
            "claimed_level": "SLSA_BUILD_LEVEL_3",
            "requirements": [
                {"id": ident, "status": "satisfied", "reason": "ok", "evidence": ["x"]}
                for ident in sorted(READINESS.EXPECTED_REQUIREMENTS)
            ],
        }
        readiness["requirements"][0]["status"] = "blocked"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, value in (
            (READINESS.READINESS_REL, readiness),
            (READINESS.POLICY_REL, json.loads(
                (ROOT / READINESS.POLICY_REL).read_text(encoding="utf-8"))),
        ):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")
        for rel in (
            READINESS.WORKFLOW_REL,
            READINESS.BUILDER_REL,
            READINESS.RELEASE_WORKFLOW_REL,
            READINESS.EVIDENCE_BUILDER_REL,
        ):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        (root / "x").write_text("", encoding="utf-8")
        policy = json.loads(
            (ROOT / "packaging/supply-chain/verification-policy.json")
            .read_text(encoding="utf-8")
        )
        with self.assertRaisesRegex(ValueError, "readiness 未通过"):
            VSA.predicate(
                policy, "a" * 64, "b" * 40, "123", "2026-10-27T00:00:00Z", root
            )


if __name__ == "__main__":
    unittest.main()
