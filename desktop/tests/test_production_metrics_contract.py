#!/usr/bin/env python3
"""WP-24 生产指标判据（首次成功/返工/成本/复用；口径可复算，缺数据不冒充）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import production_metrics as pm  # noqa: E402

REG = ROOT / pm.METRICS_REL


class ProductionMetricsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(REG.read_text(encoding="utf-8"))
        cls.live = pm.build(str(ROOT))

    def test_check_green(self):
        self.assertEqual([], pm.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(pm.render(self.live), REG.read_text(encoding="utf-8"))

    def test_four_measured_metrics(self):
        metrics = {m["id"]: m for m in self.doc["metrics"]}
        for mid in ("M-01", "M-02", "M-03", "M-04"):
            self.assertEqual("measured", metrics[mid]["status"])
            self.assertTrue(metrics[mid]["source"])
        self.assertEqual(1.0, metrics["M-01"]["value"])
        self.assertEqual(0.0, metrics["M-02"]["value"])
        self.assertGreaterEqual(metrics["M-03"]["value"], 1)
        self.assertGreaterEqual(metrics["M-04"]["value"], 1)

    def test_no_data_honest(self):
        for metric in self.doc["metrics"]:
            if metric["status"] != "no-data":
                continue
            self.assertIsNone(metric["value"])
            self.assertTrue(metric["owner"])
            self.assertTrue(metric.get("note"))

    def test_mutations_red(self):
        def check_doc(doc):
            original = REG.read_text(encoding="utf-8")
            try:
                with open(REG, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(pm.render(doc))
                return pm.check(str(ROOT))
            finally:
                with open(REG, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(original)

        fake = copy.deepcopy(self.doc)
        next(m for m in fake["metrics"] if m["status"] == "measured")["source"] = ""
        self.assertTrue(check_doc(fake), "measured 缺 source 必须红")

        lied = copy.deepcopy(self.doc)
        next(m for m in lied["metrics"] if m["status"] == "no-data")["value"] = 1.0
        self.assertTrue(check_doc(lied), "no-data 填 value 必须红")

        drift = copy.deepcopy(self.doc)
        drift["metrics"][0]["value"] = 0.0
        self.assertTrue(check_doc(drift), "指标漂移必须红")


if __name__ == "__main__":
    unittest.main()
