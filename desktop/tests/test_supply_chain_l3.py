#!/usr/bin/env python3
"""OSPS L3 evidence and fail-closed VEX/readiness negative tests."""
import importlib.util
import json
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
        for rel in (READINESS.READINESS_REL, READINESS.POLICY_REL, READINESS.WORKFLOW_REL):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        return root

    def test_current_tree_never_claims_build_l3(self):
        issues, stats = READINESS.scan(ROOT)
        self.assertEqual([], issues)
        self.assertEqual("SLSA_BUILD_LEVEL_2", stats["claimed_level"])

    def test_policy_cannot_promote_shared_runner_to_l3(self):
        root = self._root_copy()
        path = root / READINESS.POLICY_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["verified_levels"].append("SLSA_BUILD_LEVEL_3")
        path.write_text(json.dumps(doc), encoding="utf-8")
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("不得" in issue and "Build L3" in issue for issue in issues))

    def test_trusted_builder_blocker_cannot_be_removed(self):
        root = self._root_copy()
        path = root / READINESS.READINESS_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        next(item for item in doc["requirements"]
             if item["id"] == "trusted-builder")["status"] = "satisfied"
        path.write_text(json.dumps(doc), encoding="utf-8")
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("trusted L3 builder" in issue for issue in issues))

    def test_deprecated_generator_cannot_return(self):
        root = self._root_copy()
        path = root / READINESS.WORKFLOW_REL
        path.write_text(
            path.read_text(encoding="utf-8") + "\n# slsa-github-generator\n",
            encoding="utf-8",
        )
        issues, _ = READINESS.scan(root)
        self.assertTrue(any("Node.js SLSA builder" in issue for issue in issues))


class VsaPredicateTest(unittest.TestCase):
    def test_predicate_can_only_sign_policy_levels(self):
        policy = json.loads(
            (ROOT / "packaging/supply-chain/verification-policy.json")
            .read_text(encoding="utf-8")
        )
        doc = VSA.predicate(policy, "a" * 64, "b" * 40, "123", "2026-10-27T00:00:00Z")
        self.assertEqual(["SLSA_BUILD_LEVEL_2"], doc["verifiedLevels"])
        self.assertEqual("PASSED", doc["verificationResult"])
        self.assertEqual({"sha256": "a" * 64}, doc["policy"]["digest"])

    def test_l3_policy_is_rejected(self):
        policy = json.loads(
            (ROOT / "packaging/supply-chain/verification-policy.json")
            .read_text(encoding="utf-8")
        )
        policy["verified_levels"].append("SLSA_BUILD_LEVEL_3")
        with self.assertRaisesRegex(ValueError, "禁止签发 Build L3"):
            VSA.predicate(
                policy, "a" * 64, "b" * 40, "123", "2026-10-27T00:00:00Z"
            )


if __name__ == "__main__":
    unittest.main()
