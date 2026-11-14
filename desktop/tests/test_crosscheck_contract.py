#!/usr/bin/env python3
"""WP-51 跨实现/断网/删除矩阵判据（Go parity 静态对账 + 断网探针 + 10 删除矩阵）。"""

import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assembly_runtime as ar  # noqa: E402
from core import crosscheck as cc  # noqa: E402

REG = ROOT / cc.REL
REPORT = ROOT / cc.REPORT_REL


class CrosscheckContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_registry_check_and_freshness(self):
        self.assertEqual("nf-crosscheck/1", self.reg["schema"])
        self.assertEqual([], cc.check(str(ROOT)))
        self.assertEqual(cc.render(cc.build(str(ROOT))), REPORT.read_text(encoding="utf-8"))

    def test_parity_honest(self):
        parity = self.report["parity"]
        if shutil.which("go"):
            self.assertIn(parity["runtime"], ("pass", "open"))
        else:
            self.assertEqual("open", parity["runtime"], "Go 缺失时不得声称运行时 parity")
            self.assertEqual("static-only", parity["status"])
        self.assertGreaterEqual(parity["evidence"]["vector_total"], 50)
        self.assertGreaterEqual(parity["evidence"]["vector_files"], 7)

    def test_offline_green(self):
        offline = self.report["offline"]
        self.assertTrue(offline["ok"], offline.get("error"))
        self.assertEqual(6, len(offline["checks"]))
        for name, ok in offline["checks"].items():
            self.assertTrue(ok, "断网下管线失败：%s" % name)

    def test_deletion_matrix_complete(self):
        cases = self.report["deletion_matrix"]
        self.assertEqual(10, len(cases))
        for case in cases:
            self.assertTrue(case["detected"], "%s 漏检" % case["id"])
        self.assertEqual(0, self.report["summary"]["deletion_missed"])
        self.assertEqual(10, self.report["summary"]["deletion_detected"])

    def test_mutations_red(self):
        original = REPORT.read_text(encoding="utf-8")
        try:
            missed = copy.deepcopy(self.report)
            missed["deletion_matrix"][0]["detected"] = False
            REPORT.write_text(cc.render(missed), encoding="utf-8", newline="\n")
            self.assertTrue(cc.check(str(ROOT)), "漏检必须红")

            fake_parity = copy.deepcopy(self.report)
            fake_parity["parity"]["runtime"] = "pass"
            REPORT.write_text(cc.render(fake_parity), encoding="utf-8", newline="\n")
            self.assertTrue(cc.check(str(ROOT)), "Go 缺失却写运行时 pass 必须红")
        finally:
            REPORT.write_text(original, encoding="utf-8", newline="\n")

    def test_assembly_plan_deletion_detected(self):
        """WP-51 修复：删除计划步骤必须被 validate_record 检出（计划 vs 轨迹对齐）。"""
        record = json.loads((ROOT / "results/assembly/sample-document.assembly.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual([], ar.validate_record(record, str(ROOT)))
        broken = copy.deepcopy(record)
        broken["assembly"]["steps"].pop(0)
        issues = ar.validate_record(broken, str(ROOT))
        self.assertTrue(any("不对齐" in i for i in issues), issues)

    def test_claims_boundary(self):
        boundary = " ".join(self.report["claims_boundary"])
        self.assertIn("OPEN", boundary)


if __name__ == "__main__":
    unittest.main()
