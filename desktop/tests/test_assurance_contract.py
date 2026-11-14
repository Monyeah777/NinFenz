#!/usr/bin/env python3
"""保证案例 + RAID 契约（NF-Final WP-0G，P2 盲区 BL-12）。

真源 = `results/assurance/CLAIMS.json`（`nf-assurance-claims/1`）+ `protocol/raid.json`
（`nf-raid/1`）；人读面 = `docs/assurance/ASSURANCE_CASE.md` + `docs/RAID.md` + `docs/ETHICS.md`。
判据：
1. 保证案例：Goal C0-C3 / Argument A1-A8 固定；每条 Argument 有 assumption+rebuttal+真实证据；
   supported ≥2 件且含测试/门禁证据；partial/open/accepted-risk 必须写缺口 id 且缺口有 owner；
2. 「测试通过不能替代论证」：证据必须指向代码/契约/测试/门禁；
3. RAID：风险 R-01…R-08 概率/影响/owner/触发/缓解/复审齐全；RAID 四类（风险/假设/问题/依赖）
   与干系人、变更控制登记；缺口 ↔ RAID issue 一一绑定（双向）；
4. 伦理：docs/ETHICS.md 列干系人与价值冲突（EV 表）且不越级声称；
5. 变异自证：删证据、supported 证据不足、缺 open、缺口缺 owner、缺风险、断 RAID link、
   风险矩阵非法 —— 判据都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import assurance  # noqa: E402

CLAIMS = ROOT / "results" / "assurance" / "CLAIMS.json"
RAID = ROOT / "protocol" / "raid.json"
DOCS = {
    "CASE": ROOT / "docs" / "assurance" / "ASSURANCE_CASE.md",
    "RAID": ROOT / "docs" / "RAID.md",
    "ETHICS": ROOT / "docs" / "ETHICS.md",
}
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class AssuranceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.claims = _json(CLAIMS)
        cls.raid = _json(RAID)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_audit_clean_and_facts(self):
        issues, facts = assurance.audit(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(4, facts["goals"])
        self.assertEqual(8, facts["arguments"])
        self.assertEqual(8, facts["risks"])
        self.assertEqual(5, facts["gaps"])

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        for goal in self.claims["goals"]:
            self.assertIn(goal["id"], self.texts["CASE"])
        for arg in self.claims["arguments"]:
            self.assertIn(arg["id"], self.texts["CASE"])
        for gap in self.claims["gaps"]:
            self.assertIn(gap["id"], self.texts["CASE"])
        for item in self.raid["risks"]:
            self.assertIn(item["id"], self.texts["RAID"])
        for group in ("assumptions", "issues", "dependencies"):
            for item in self.raid[group]:
                self.assertIn(item["id"], self.texts["RAID"])
        for item in self.raid["stakeholders"]:
            self.assertIn(item["id"], self.texts["ETHICS"] + self.texts["RAID"])
        for marker in ("EV-01", "EV-06", "IEEE 7000", "Value Sensitive Design"):
            self.assertIn(marker, self.texts["ETHICS"])

    def test_arguments_are_real_arguments(self):
        self.assertIn("测试通过", self.claims["note"])
        self.assertIn("替代论证", self.claims["note"])
        gaps = {g["id"] for g in self.claims["gaps"]}
        for arg in self.claims["arguments"]:
            self.assertTrue(arg["assumption"].strip(), "%s 缺 assumption" % arg["id"])
            self.assertTrue(arg["rebuttal"].strip(), "%s 缺 rebuttal" % arg["id"])
            if arg["status"] == "supported":
                self.assertGreaterEqual(len(arg["evidence"]), 2, arg["id"])
                self.assertTrue(any(str(x).startswith(("desktop/tests/", "scripts/", "verify.sh"))
                                    for x in arg["evidence"]), arg["id"])
            else:
                self.assertIn(arg.get("open"), gaps, "%s 的 open 未进 gaps" % arg["id"])

    def test_gap_raid_linkage(self):
        gap_ids = {g["id"] for g in self.claims["gaps"]}
        linked = {i["link_gap"] for i in self.raid["issues"] if i.get("link_gap")}
        self.assertEqual(gap_ids, linked, "缺口与 RAID issue 必须一一对应")
        for gap in self.claims["gaps"]:
            self.assertTrue(gap["owner"].strip(), "%s 缺 owner" % gap["id"])
            self.assertIn(gap["status"], ("open", "accepted-risk", "closed"))

    def test_raid_completeness(self):
        self.assertEqual(list(assurance.RISK_IDS),
                         [r["id"] for r in self.raid["risks"]])
        self.assertEqual(list(assurance.SCALE), self.raid["risk_matrix"]["scale"])
        for risk in self.raid["risks"]:
            for field in ("owner", "trigger", "mitigation", "review"):
                self.assertTrue(risk[field].strip(), "%s 缺 %s" % (risk["id"], field))
            self.assertIn(risk["probability"], assurance.SCALE)
            self.assertIn(risk["impact"], assurance.SCALE)
        self.assertGreaterEqual(len(self.raid["stakeholders"]), 3)
        self.assertTrue((ROOT / self.raid["change_control"]["evidence"]).is_file())

    def test_no_overclaim(self):
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))

    def test_mutations_red(self):
        no_evidence = copy.deepcopy(self.claims)
        no_evidence["arguments"][0]["evidence"] = []
        self.assertTrue(assurance.validate_claims(no_evidence, str(ROOT)), "缺证据必须红")

        thin = copy.deepcopy(self.claims)
        thin["arguments"][0]["evidence"] = ["protocol/independence.json"]
        self.assertTrue(assurance.validate_claims(thin, str(ROOT)),
                        "supported 证据不足/缺测试证据必须红")

        no_open = copy.deepcopy(self.claims)
        next(a for a in no_open["arguments"] if a["status"] == "open").pop("open", None)
        self.assertTrue(assurance.validate_claims(no_open, str(ROOT)), "非 supported 缺 open 必须红")

        bad_gap = copy.deepcopy(self.claims)
        bad_gap["gaps"][0]["owner"] = ""
        self.assertTrue(assurance.validate_claims(bad_gap, str(ROOT)), "缺口缺 owner 必须红")

        no_risk = copy.deepcopy(self.raid)
        no_risk["risks"] = [r for r in no_risk["risks"] if r["id"] != "R-08"]
        self.assertTrue(assurance.validate_raid(no_risk, str(ROOT)), "缺风险必须红")

        bad_matrix = copy.deepcopy(self.raid)
        bad_matrix["risk_matrix"]["scale"] = ["tiny", "big"]
        self.assertTrue(assurance.validate_raid(bad_matrix, str(ROOT)), "风险矩阵非法必须红")

        broken_link = copy.deepcopy(self.raid)
        broken_link["issues"] = broken_link["issues"][:-1]
        self.assertTrue(assurance.link_issues(self.claims, broken_link),
                        "断 RAID link 必须红")


if __name__ == "__main__":
    unittest.main()
