#!/usr/bin/env python3
"""WP-54 CQ6 综合审查判据（八维评分卡/红线/棘轮/整改/复审签署状态）。"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cq6_scorecard as cq  # noqa: E402

REG = ROOT / cq.REL
CARD = ROOT / cq.REPORT_REL
BASE = ROOT / cq.BASELINE_REL


class CQ6ScorecardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(REG.read_text(encoding="utf-8"))
        cls.card = json.loads(CARD.read_text(encoding="utf-8"))
        cls.base = json.loads(BASE.read_text(encoding="utf-8"))

    def test_registry(self):
        self.assertEqual("nf-cq6/1", self.reg["schema"])
        weights = sum(int(d["weight"]) for d in self.reg["dimensions"])
        self.assertEqual(100, weights, "八维权重合计必须 100")
        self.assertFalse(self.reg["signoff"]["ai_may_sign"])

    def test_check_green(self):
        self.assertEqual([], cq.check(str(ROOT)))

    def test_committed_equals_live(self):
        self.assertEqual(cq.render(cq.build(str(ROOT))), CARD.read_text(encoding="utf-8"))

    def test_scoring_consistency(self):
        dims = self.card["dimensions"]
        self.assertEqual(8, len(dims))
        for dim in dims:
            self.assertTrue(0 <= dim["score"] <= 5, dim["id"])
            self.assertTrue(dim["reason"])
            self.assertTrue(dim["evidence"])
            for rel in dim["evidence"]:
                self.assertTrue((ROOT / rel).exists(), "%s 证据不在场：%s" % (dim["id"], rel))
        weighted = sum(d["score"] * d["weight"] for d in dims) / 100.0
        self.assertAlmostEqual(round(weighted, 2), self.card["overall"], places=2)

    def test_red_lines_and_grade(self):
        p0 = self.card["red_lines"]["p0"]
        min_dim = self.card["red_lines"]["min_dimension"]
        self.assertEqual(0, p0, "P0 必须为 0")
        grade = self.card["grade"]
        self.assertIn(grade, ("A", "B", "C", "D", "E"))
        if min_dim < 2 or p0:
            self.assertIn(grade, ("C", "D", "E"), "红线触发时不得 A/B")
        bands = {"A": 4.5, "B": 4.0, "C": 3.0, "D": 2.0, "E": 0.0}
        expected = next(g for g, floor in sorted(bands.items(), key=lambda kv: -kv[1])
                        if self.card["overall"] >= floor)
        if min_dim >= 2 and not p0:
            self.assertEqual(expected, grade, "分档与总分不一致")

    def test_ratchet_against_baseline(self):
        self.assertEqual([], self.card["ratchet"]["regressions"], "棘轮不得回退")
        self.assertGreaterEqual(self.card["overall"], self.base["overall"],
                                "总分不得低于基线")
        prev = {d["id"]: d["score"] for d in self.base["dimensions"]}
        for dim in self.card["dimensions"]:
            self.assertGreaterEqual(dim["score"], prev[dim["id"]], dim["id"])

    def test_remediation_owners(self):
        self.assertTrue(self.card["remediation"])
        for item in self.card["remediation"]:
            self.assertTrue(item["owner"])
            self.assertIn(item["status"], ("open", "in-progress", "done", "accepted-risk"))

    def test_signoff_not_faked(self):
        sign = self.card["signoff"]
        self.assertFalse(sign["ai_may_sign"])
        self.assertEqual("pending-human", sign["status"],
                         "AI 不能代签；人类复审前保持 pending-human")
        self.assertTrue(sign["owner"])

    def test_mutations_red(self):
        original = CARD.read_text(encoding="utf-8")
        try:
            bad = copy.deepcopy(self.card)
            bad["overall"] = 4.9
            bad["grade"] = "A"
            CARD.write_text(cq.render(bad), encoding="utf-8", newline="\n")
            self.assertTrue(cq.check(str(ROOT)), "分数与重算不一致必须红")

            fake_sign = copy.deepcopy(self.card)
            fake_sign["signoff"]["ai_may_sign"] = True
            CARD.write_text(cq.render(fake_sign), encoding="utf-8", newline="\n")
            self.assertTrue(cq.check(str(ROOT)), "AI 代签必须红")
        finally:
            CARD.write_text(original, encoding="utf-8", newline="\n")

    def test_baseline_regression_detected(self):
        original = BASE.read_text(encoding="utf-8")
        try:
            base = copy.deepcopy(self.base)
            base["dimensions"][0]["score"] = 5
            base["overall"] = 5.0
            BASE.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
            card = cq.build(str(ROOT))
            self.assertTrue(card["ratchet"]["regressions"], "低于基线必须记 regression")
        finally:
            BASE.write_text(original, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    unittest.main()
