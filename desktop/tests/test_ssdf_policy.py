#!/usr/bin/env python3
"""NIST SSDF v1.1 scoped evidence and vulnerability-response regression tests."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ssdf_policy  # noqa: E402


class SsdfPolicyTest(unittest.TestCase):
    def test_current_scope_has_closed_ssdf_evidence(self):
        issues, stats = ssdf_policy.scan(ROOT)
        self.assertEqual([], issues)
        self.assertEqual(19, stats["practices"])
        self.assertEqual(42, stats["tasks"])
        self.assertEqual(11, stats["statuses"]["enforced"])
        self.assertEqual(8, stats["statuses"]["external-manual"])
        self.assertEqual(30, stats["task_statuses"]["enforced"])
        self.assertEqual(12, stats["task_statuses"]["external-manual"])
        self.assertNotIn("partial", stats["statuses"])
        self.assertNotIn("partial", stats["task_statuses"])
        self.assertFalse(stats["advisories"]["claims_no_vulnerabilities"])
        self.assertEqual("2026-10-29", stats["advisories"]["root_cause_reviewed_at"])

    def _copy_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        files = [
            ssdf_policy.MATRIX_REL,
            ssdf_policy.ADVISORIES_REL,
            ssdf_policy.VEX_REL,
            ssdf_policy.SECURITY_REL,
        ]
        for rel in files:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        doc = json.loads((root / ssdf_policy.MATRIX_REL).read_text(encoding="utf-8"))
        for row in doc["practices"]:
            for task in row["tasks"]:
                for rel in task["evidence"]:
                    if rel.startswith("external:"):
                        continue
                    target = root / rel
                    if target.exists():
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
        return root, doc

    def _write_matrix(self, root, doc):
        (root / ssdf_policy.MATRIX_REL).write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )

    def test_missing_and_unknown_practices_fail_closed(self):
        root, doc = self._copy_root()
        doc["practices"].pop()
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("missing SSDF practices" in issue for issue in issues), issues)

        root, doc = self._copy_root()
        doc["practices"].append(dict(doc["practices"][0], id="PW.99"))
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("unknown SSDF practices" in issue for issue in issues), issues)

    def test_retired_pw3_and_missing_tasks_fail_closed(self):
        root, doc = self._copy_root()
        doc["practices"] = [row for row in doc["practices"] if row["id"] != "PW.4"]
        doc["practices"].append({
            "id": "PW.3",
            "title": "Verify third-party software components",
            "status": "enforced",
            "tasks": [{
                "id": "PW.3.1",
                "title": "Retired practice",
                "status": "enforced",
                "verification": "fixture",
                "evidence": [ssdf_policy.SECURITY_REL.as_posix()],
            }],
        })
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("unknown SSDF practices" in issue for issue in issues), issues)
        self.assertTrue(any("missing SSDF tasks" in issue for issue in issues), issues)

    def test_partial_practice_is_a_baseline_regression(self):
        root, doc = self._copy_root()
        row = next(item for item in doc["practices"] if item["id"] == "RV.1")
        row["tasks"][0]["status"] = "partial"
        row["tasks"][0]["gap"] = "regressed"
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("partial SSDF task" in issue for issue in issues), issues)

    def test_external_manual_claims_need_a_real_gap(self):
        root, doc = self._copy_root()
        task = next(
            item
            for row in doc["practices"]
            for item in row["tasks"]
            if item["id"] == "PO.2.2"
        )
        task["gap"] = ""
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("external-manual requires gap" in issue for issue in issues), issues)

    def test_practice_status_is_derived_from_tasks(self):
        root, doc = self._copy_root()
        row = next(item for item in doc["practices"] if item["id"] == "PO.2")
        row["status"] = "enforced"
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("must be derived" in issue for issue in issues), issues)

    def test_official_table_hash_is_pinned(self):
        root, doc = self._copy_root()
        doc["standard"]["table_sha256"] = "0" * 64
        self._write_matrix(root, doc)
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("table_sha256" in issue for issue in issues), issues)

    def test_open_vulnerability_blocks_the_release_gate(self):
        root, _doc = self._copy_root()
        path = root / ssdf_policy.ADVISORIES_REL
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger["findings"] = [{
            "id": "NF-ADV-0001",
            "vulnerability": "CVE-2099-0001",
            "source": "github-advisory",
            "discovered_at": "2026-10-29",
            "status": "under_investigation",
            "severity": "high",
            "affected_versions": ["1.1.0"],
            "exploitability": "reachable",
            "impact": "A crafted request can reach the affected path.",
            "action": "Contain, patch, and verify before release.",
            "disclosure_url": "https://github.com/Monyeah777/NinFenz/security/advisories/test",
            "evidence": ["external:GitHub security advisory"],
        }]
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("unresolved advisory" in issue for issue in issues), issues)

    def test_fixed_vulnerability_requires_root_cause_and_vex(self):
        root, _doc = self._copy_root()
        regression = root / "desktop/tests/test_regression_fixture.py"
        regression.parent.mkdir(parents=True, exist_ok=True)
        regression.write_text("", encoding="utf-8")
        path = root / ssdf_policy.ADVISORIES_REL
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger["findings"] = [{
            "id": "NF-ADV-0002",
            "vulnerability": "CVE-2099-0002",
            "source": "github-advisory",
            "discovered_at": "2026-10-29",
            "status": "fixed",
            "severity": "high",
            "affected_versions": ["1.0.0"],
            "fixed_in": "1.0.1",
            "exploitability": "reachable",
            "impact": "A crafted request can reach the affected path.",
            "related_review": "Reviewed sibling parsers for the same defect class.",
            "regression_tests": ["desktop/tests/test_regression_fixture.py"],
            "disclosure_url": "https://github.com/Monyeah777/NinFenz/security/advisories/test",
            "evidence": ["external:GitHub security advisory"],
        }]
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("root_cause" in issue for issue in issues), issues)
        self.assertTrue(any("VEX statement" in issue for issue in issues), issues)

    def test_finding_requires_risk_assessment_metadata(self):
        root, _doc = self._copy_root()
        path = root / ssdf_policy.ADVISORIES_REL
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger["findings"] = [{
            "id": "NF-ADV-0003",
            "vulnerability": "CVE-2099-0003",
            "status": "under_investigation",
            "severity": "medium",
            "affected_versions": ["1.1.0"],
            "disclosure_url": "https://github.com/Monyeah777/NinFenz/security/advisories/test",
            "evidence": ["external:GitHub security advisory"],
        }]
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        issues, _ = ssdf_policy.scan(root)
        for expected in ("source", "discovered_at", "exploitability", "impact"):
            self.assertTrue(any(expected in issue for issue in issues), (expected, issues))

    def test_root_cause_review_is_required(self):
        root, _doc = self._copy_root()
        path = root / ssdf_policy.ADVISORIES_REL
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger.pop("root_cause_review", None)
        path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("root_cause_review is required" in issue for issue in issues), issues)

    def test_security_policy_requires_intake_and_severity_sla(self):
        root, _doc = self._copy_root()
        path = root / ssdf_policy.SECURITY_REL
        path.write_text("# Security\n", encoding="utf-8")
        issues, _ = ssdf_policy.scan(root)
        self.assertTrue(any("vulnerability intake" in issue for issue in issues), issues)
        self.assertTrue(any("severity response SLA" in issue for issue in issues), issues)

    def test_ci_and_release_workflows_enforce_ssdf_evidence(self):
        for rel in (".github/workflows/ci-verify.yml",
                    ".github/workflows/npm-publish.yml",
                    ".github/workflows/release-gate.yml"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("scripts/ssdf_policy.py", text, rel)


if __name__ == "__main__":
    unittest.main()
