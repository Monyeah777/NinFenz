#!/usr/bin/env python3
"""S2C2F SCA-3 runtime end-of-life policy regression tests."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import eol_policy  # noqa: E402


class EolPolicyTest(unittest.TestCase):
    def _copy(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        doc = json.loads((ROOT / eol_policy.POLICY_REL).read_text(encoding="utf-8"))
        declarations = doc["declarations"]
        paths = set(declarations["python_requires"] + declarations["dockerfiles"])
        paths.add(declarations["node_engines"])
        for rel in paths:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        for rel in (
            ".github/workflows/slsa-build-l3.yml",
            ".github/workflows/dependency-audit.yml",
        ):
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        policy = root / eol_policy.POLICY_REL
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return root

    def test_current_repository_is_inside_supported_windows(self):
        issues, warns, stats = eol_policy.scan(ROOT, today=date(2026, 11, 2))
        self.assertEqual([], issues)
        self.assertEqual([], warns)
        self.assertEqual(["3.11", "3.12"], stats["python_versions"])
        self.assertEqual(["22", "24"], stats["node_majors"])

    def test_expired_runtime_fails_closed(self):
        root = self._copy()
        policy = root / eol_policy.POLICY_REL
        doc = json.loads(policy.read_text(encoding="utf-8"))
        doc["runtimes"][0]["eol"] = "2026-10-31"
        policy.write_text(json.dumps(doc), encoding="utf-8")
        issues, _, _ = eol_policy.scan(root, today=date(2026, 11, 2))
        self.assertTrue(any("已过期" in issue for issue in issues), issues)

    def test_unsupported_workflow_runtime_is_rejected(self):
        root = self._copy()
        path = root / ".github/workflows/slsa-build-l3.yml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "python-version: '3.11'", "python-version: '3.10'"
            ),
            encoding="utf-8",
        )
        issues, _, _ = eol_policy.scan(root, today=date(2026, 11, 2))
        self.assertTrue(any("Python 3.10" in issue for issue in issues), issues)

    def test_python_requires_floor_cannot_claim_eol_python(self):
        root = self._copy()
        path = root / "engine/rust/pyo3/pyproject.toml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'requires-python = ">=3.11,<3.12"', 'requires-python = ">=3.9,<3.10"'
            ),
            encoding="utf-8",
        )
        issues, _, _ = eol_policy.scan(root, today=date(2026, 11, 2))
        self.assertTrue(any("下限 3.9" in issue for issue in issues), issues)

    def test_node_engine_cannot_advertise_expired_major(self):
        root = self._copy()
        path = root / "packaging/npm/package.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["engines"]["node"] = ">=18.17"
        path.write_text(json.dumps(doc), encoding="utf-8")
        issues, _, _ = eol_policy.scan(root, today=date(2026, 11, 2))
        self.assertTrue(any("Node 18" in issue for issue in issues), issues)

    def test_stale_review_is_rejected(self):
        root = self._copy()
        policy = root / eol_policy.POLICY_REL
        doc = json.loads(policy.read_text(encoding="utf-8"))
        doc["reviewed_at"] = "2026-01-01"
        doc["max_review_age_days"] = 30
        policy.write_text(json.dumps(doc), encoding="utf-8")
        issues, _, _ = eol_policy.scan(root, today=date(2026, 11, 2))
        self.assertTrue(any("支持矩阵已过期" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
