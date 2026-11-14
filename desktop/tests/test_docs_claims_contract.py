#!/usr/bin/env python3
"""WP-50 文档 claims 一致性判据（数字/标签/禁用措辞 vs 门禁实测）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import docs_claims as dc  # noqa: E402
from core import quality_baseline as qb  # noqa: E402

REG = ROOT / dc.REL
REPORT = ROOT / dc.REPORT_REL


def _mutate_readme(old, new):
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    assert old in original
    try:
        path.write_text(original.replace(old, new, 1), encoding="utf-8", newline="\n")
        return dc.build(str(ROOT))
    finally:
        path.write_text(original, encoding="utf-8", newline="\n")


class DocsClaimsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_check_green(self):
        self.assertEqual([], dc.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(dc.render(dc.build(str(ROOT))), REPORT.read_text(encoding="utf-8"))

    def test_expected_from_quality_baseline(self):
        self.assertEqual(qb.EXPECTED_PASS, self.report["expected"]["pass_count"])
        self.assertEqual(qb.CHECK_LABEL, self.report["expected"]["check_label"])
        self.assertEqual(qb.EXPECTED_CHECKS, self.report["expected"]["baseline_checks"])
        self.assertGreaterEqual(self.report["counts"]["claims"], 10)

    def test_stale_pass_red(self):
        report = _mutate_readme("PASS=%d" % qb.EXPECTED_PASS,
                                "PASS=%d" % (qb.EXPECTED_PASS - 5))
        self.assertTrue(report["violations"], "过期 PASS 数字必须红")
        self.assertTrue(any(v["kind"] == "pass_count" for v in report["violations"]))

    def test_stale_label_red(self):
        label = qb.CHECK_LABEL
        report = _mutate_readme(label, label.rsplit("/", 1)[0])
        self.assertTrue(report["violations"], "过期 check 标签必须红")

    def test_forbidden_claim_red(self):
        report = _mutate_readme("# NinFenz", "# NinFenz（已认证）")
        self.assertTrue(report["violations"], "非否定语境的认证措辞必须红")

    def test_negative_context_allowed(self):
        report = _mutate_readme("# NinFenz", "# NinFenz（不是认证产品）")
        self.assertEqual([], [v for v in report["violations"]
                              if v["kind"] == "forbidden-claim"])

    def test_template_mutation_red(self):
        doc = copy.deepcopy(self.reg)
        doc["documents"].append({"rel": "docs/nonexistent_zzz.md", "kinds": ["pass_count"]})
        original = REG.read_text(encoding="utf-8")
        try:
            REG.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8", newline="\n")
            report = dc.build(str(ROOT))
        finally:
            REG.write_text(original, encoding="utf-8", newline="\n")
        self.assertTrue(any(v["kind"] == "missing-doc" for v in report["violations"]))

    def test_baseline_keys_checked(self):
        values = {(c["doc"], c.get("key")) for c in self.report["claims"]
                  if c["kind"] == "baseline_keys"}
        self.assertIn(("docs/meta/VERSION-MATRIX.md", "baseline_checks"), values)
        self.assertIn(("docs/meta/VERSION-MATRIX.md", "baseline_pass"), values)

    def test_claims_boundary(self):
        boundary = " ".join(self.reg.get("claims_boundary") or [])
        self.assertIn("不替代", boundary)


if __name__ == "__main__":
    unittest.main()
