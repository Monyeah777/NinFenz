#!/usr/bin/env python3
"""WP-33 治理报告/审计包判据（可复算 + 诚实等级 + OPEN 有 owner）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import governance_report as gr  # noqa: E402

REPORT = ROOT / gr.REPORT_REL
AUDIT = ROOT / gr.AUDIT_REL


class GovernanceReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        cls.live = gr.build(str(ROOT))

    def test_check_green(self):
        self.assertEqual([], gr.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(gr.render_report(self.live["report"]), REPORT.read_text(encoding="utf-8"))
        self.assertEqual(gr.render_audit(self.live["audit"]), AUDIT.read_text(encoding="utf-8"))

    def test_levels_honest(self):
        levels = self.report["levels"]
        self.assertTrue(levels["T1"]["ok"])
        for level in ("T2", "T3", "T4"):
            self.assertFalse(levels[level]["ok"], "%s 不应声称可达" % level)
            self.assertTrue(levels[level]["missing"], "%s 必须写缺项" % level)
            self.assertEqual(2, levels[level]["exit_code"])

    def test_audit_all_green(self):
        self.assertEqual(7, self.audit["summary"]["total"])
        self.assertEqual(0, self.audit["summary"]["fail"])
        for item in self.audit["checks"]:
            self.assertTrue(item["ok"], item["id"])
            self.assertTrue(item["evidence"])

    def test_open_items_have_owner(self):
        for item in self.report["open_items"]:
            self.assertTrue(item["owner"])

    def test_mutations_red(self):
        def check_pair(report_doc, audit_doc):
            r_old = REPORT.read_text(encoding="utf-8")
            a_old = AUDIT.read_text(encoding="utf-8")
            try:
                REPORT.write_text(gr.render_report(report_doc), encoding="utf-8", newline="\n")
                AUDIT.write_text(gr.render_audit(audit_doc), encoding="utf-8", newline="\n")
                return gr.check(str(ROOT))
            finally:
                REPORT.write_text(r_old, encoding="utf-8", newline="\n")
                AUDIT.write_text(a_old, encoding="utf-8", newline="\n")

        fake = copy.deepcopy(self.report)
        fake["levels"]["T3"]["ok"] = True
        fake["levels"]["T3"]["achievable"] = "T3"
        fake["levels"]["T3"]["exit_code"] = 0
        self.assertTrue(check_pair(fake, self.audit), "T3 冒充必须红")

        drift = copy.deepcopy(self.report)
        drift["self_audit"]["p0"] = 1
        self.assertTrue(check_pair(drift, self.audit), "报告漂移必须红")

        bad_audit = copy.deepcopy(self.audit)
        bad_audit["checks"][0]["ok"] = False
        self.assertTrue(check_pair(self.report, bad_audit), "审计项红必须被 check 发现")


if __name__ == "__main__":
    unittest.main()
