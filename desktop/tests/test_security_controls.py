#!/usr/bin/env python3
"""Regression tests for the machine-verifiable application-security inventory."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import security_controls  # noqa: E402


class SecurityControlsTest(unittest.TestCase):
    def test_real_inventory_matches_code_and_documentation(self):
        issues, stats = security_controls.scan(ROOT)
        self.assertEqual([], issues)
        self.assertGreaterEqual(stats["data_classes"], 5)
        self.assertGreaterEqual(stats["communication_paths"], 3)
        self.assertGreaterEqual(stats["crypto_inventory"], 3)
        self.assertGreaterEqual(stats["resource_limits"], 9)

    def _copy_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        files = [
            security_controls.CONTROLS_REL,
            security_controls.DOC_REL,
            Path("scripts/plugin_host.py"),
        ]
        for rel in files:
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        doc = json.loads((root / security_controls.CONTROLS_REL).read_text(encoding="utf-8"))
        for row in doc["input_validation"]["rules"]:
            evidence = root / row["evidence"]
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.touch(exist_ok=True)
        return root, doc

    def _write(self, root, doc):
        (root / security_controls.CONTROLS_REL).write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_data_class_without_retention_is_red(self):
        root, doc = self._copy_root()
        doc["data_protection"]["classes"][0]["retention"] = ""
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("incomplete class" in issue for issue in issues), issues)

    def test_approved_algorithm_drift_is_red(self):
        root, doc = self._copy_root()
        doc["cryptography"]["approved_algorithms"].remove("SHA-256")
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("algorithm set drifted" in issue for issue in issues), issues)

    def test_unreviewed_runtime_external_path_is_red(self):
        root, doc = self._copy_root()
        doc["communications"][0]["external"] = True
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("external path is not reviewed" in issue for issue in issues), issues)

    def test_resource_limit_must_equal_code_constant(self):
        root, doc = self._copy_root()
        row = next(item for item in doc["resource_limits"]["limits"]
                   if item["id"] == "daemon.request")
        row["bytes"] += 1
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(
            any("declared limit differs from code" in issue for issue in issues),
            issues,
        )

    def test_production_debug_must_default_off(self):
        root, doc = self._copy_root()
        doc["production"]["debug_default"] = "enabled"
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("debug default must be disabled" in issue for issue in issues), issues)

    def test_immutable_log_gap_cannot_be_hidden(self):
        root, doc = self._copy_root()
        doc["logging"]["tamper_evident"] = False
        doc["logging"]["gap"] = ""
        self._write(root, doc)
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("must record the residual gap" in issue for issue in issues), issues)

    def test_human_document_anchor_drift_is_red(self):
        root, _doc = self._copy_root()
        path = root / security_controls.DOC_REL
        path.write_text(
            path.read_text(encoding="utf-8").replace("密码算法清单", "算法"),
            encoding="utf-8",
        )
        issues, _ = security_controls.scan(root)
        self.assertTrue(any("missing section anchor" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
