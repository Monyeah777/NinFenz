#!/usr/bin/env python3
"""OWASP ASVS 5.0.0 scoped evidence matrix regression tests."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import asvs_policy  # noqa: E402


class AsvsPolicyTest(unittest.TestCase):
    def test_current_matrix_is_complete_and_internally_consistent(self):
        issues, stats = asvs_policy.scan(ROOT)
        self.assertEqual([], issues)
        self.assertEqual(191, stats["requirements"])
        self.assertEqual({"enforced": 78, "partial": 4, "not-applicable": 109},
                         stats["statuses"])
        self.assertEqual(13, len(stats["chapters"]))
        self.assertGreaterEqual(stats["controls"]["data_classes"], 5)

        doc = json.loads((ROOT / asvs_policy.MATRIX_REL).read_text(encoding="utf-8"))
        partial = {row["id"] for row in doc["requirements"]
                   if row["status"] == "partial"}
        self.assertEqual({"V5.2.2", "V11.2.2", "V16.4.2", "V16.4.3"}, partial)

    def _copy_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        matrix = ROOT / asvs_policy.MATRIX_REL
        target = root / asvs_policy.MATRIX_REL
        target.parent.mkdir(parents=True)
        shutil.copy2(matrix, target)
        doc = json.loads(target.read_text(encoding="utf-8"))
        for entry in doc["requirements"]:
            for rel in entry.get("evidence", []):
                if rel.startswith("external:"):
                    continue
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
        return root, target, doc

    def _write(self, target, doc):
        target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_missing_or_duplicate_requirement_fails_closed(self):
        root, target, doc = self._copy_root()
        doc["requirements"].pop()
        self._write(target, doc)
        issues, _ = asvs_policy.scan(root)
        self.assertTrue(any("需求数量" in issue for issue in issues))

        root, target, doc = self._copy_root()
        doc["requirements"][-1] = dict(doc["requirements"][0])
        self._write(target, doc)
        issues, _ = asvs_policy.scan(root)
        self.assertTrue(any("ID 重复" in issue for issue in issues))

    def test_partial_and_na_require_gap_and_evidence(self):
        root, target, doc = self._copy_root()
        doc["requirements"][0]["status"] = "partial"
        doc["requirements"][0]["gap"] = ""
        doc["requirements"][0]["evidence"] = []
        self._write(target, doc)
        issues, _ = asvs_policy.scan(root)
        self.assertTrue(any("必须记录 gap" in issue for issue in issues))
        self.assertTrue(any("evidence 必须是非空数组" in issue for issue in issues))

    def test_false_certification_claim_is_rejected(self):
        root, target, doc = self._copy_root()
        doc["claim"]["certified"] = True
        self._write(target, doc)
        issues, _ = asvs_policy.scan(root)
        self.assertTrue(any("不得声称第三方 ASVS 认证" in issue for issue in issues))

    def test_critical_control_cannot_drop_to_partial(self):
        root, target, doc = self._copy_root()
        next(entry for entry in doc["requirements"]
             if entry["id"] == "V7.2.3")["status"] = "partial"
        next(entry for entry in doc["requirements"]
             if entry["id"] == "V7.2.3")["gap"] = "not verified"
        self._write(target, doc)
        issues, _ = asvs_policy.scan(root)
        self.assertTrue(any("关键控制未 enforced" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
