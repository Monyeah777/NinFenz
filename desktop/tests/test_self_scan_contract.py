#!/usr/bin/env python3
"""WP-50 自扫描全维度判据（S0–S15 聚合 + gap/open 诚实登记）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import self_scan as ss  # noqa: E402

REG = ROOT / ss.REL
REPORT = ROOT / ss.REPORT_REL


class SelfScanContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_registry_and_check_green(self):
        self.assertEqual("nf-self-scan/1", self.reg["schema"])
        self.assertEqual([], ss.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(ss.render(ss.build(str(ROOT))), REPORT.read_text(encoding="utf-8"))

    def test_all_dimensions_present(self):
        ids = [d["id"] for d in self.report["dimensions"]]
        self.assertEqual(["S%d" % i for i in range(16)], ids)
        for dim in self.report["dimensions"]:
            self.assertIn(dim["status"], ("covered", "covered-by-existing", "gap", "open"))
            self.assertTrue(dim["detail"])
            for rel in dim["evidence"]:
                self.assertTrue((ROOT / rel).exists(), "%s 证据不在场：%s" % (dim["id"], rel))

    def test_gap_open_have_owner_and_next(self):
        for dim in self.report["dimensions"]:
            if dim["status"] in ("gap", "open"):
                self.assertTrue(dim["owner"], "%s 缺 owner" % dim["id"])
                self.assertTrue(dim["next"], "%s 缺 next" % dim["id"])

    def test_summary_consistent(self):
        for status in ("covered", "covered-by-existing", "gap", "open"):
            want = sum(1 for d in self.report["dimensions"] if d["status"] == status)
            self.assertEqual(want, self.report["summary"][status], status)
        self.assertEqual(16, sum(self.report["summary"].values()))

    def test_claims_boundary(self):
        boundary = " ".join(self.report["claims_boundary"])
        self.assertIn("不是认证", boundary)

    def test_mutations_red(self):
        original = REPORT.read_text(encoding="utf-8")
        try:
            fake = copy.deepcopy(self.report)
            gap = next(d for d in fake["dimensions"] if d["status"] == "gap")
            gap["status"] = "covered"
            gap["evidence"] = []
            REPORT.write_text(ss.render(fake), encoding="utf-8", newline="\n")
            self.assertTrue(ss.check(str(ROOT)), "无证据的 covered 必须红")

            no_owner = copy.deepcopy(self.report)
            gap2 = next(d for d in no_owner["dimensions"] if d["status"] == "gap")
            gap2["owner"] = ""
            REPORT.write_text(ss.render(no_owner), encoding="utf-8", newline="\n")
            self.assertTrue(ss.check(str(ROOT)), "gap 缺 owner 必须红")
        finally:
            REPORT.write_text(original, encoding="utf-8", newline="\n")

    def test_probe_gap_detected(self):
        """删除/重排矩阵（S4）与红队（S15）必须是 gap/open，不能写 covered。"""
        dims = {d["id"]: d for d in self.report["dimensions"]}
        self.assertEqual("gap", dims["S4"]["status"])
        self.assertEqual("open", dims["S15"]["status"])


if __name__ == "__main__":
    unittest.main()
