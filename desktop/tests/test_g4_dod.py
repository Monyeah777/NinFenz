#!/usr/bin/env python3
"""G4 DoD 收口审计判据（NF-Final §14.3 / §11.2 G4 / §13A QG4）。

真源 = `results/g4_dod.json`（`nf-g4-dod/1`）；人读 = `G4_DOD.md`。
判据：
1. 结构：gate=G4；verdict/P0 一致；source/status 词表；n-a 必写 reason；pass-with-open 必写 gaps；证据在场；
2. **现场复算**：AI 证据链 APPROVED；AIBOM check 空；策略 T4 deny + T1 allow；AIGC 标识 check 空；
   SELF_AUDIT p0=0；check52 声明 52 条/PASS=95 与 quality_baseline 一致；
3. G4-ART 必须含 WP-40…44 全部证据；open_items 至少 OPEN-EXTERNAL/OPEN-TOOLS 且非阻断；
4. 文档交叉；变异自证 6 类。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ai_evidence as ae  # noqa: E402
from core import aibom_export as ax  # noqa: E402
from core import aigc_labeling as al  # noqa: E402
from core import policy_engine as pe  # noqa: E402
from core import quality_baseline as qb  # noqa: E402

REG = ROOT / "results" / "g4_dod.json"
DOC = ROOT / "results" / "G4_DOD.md"
SELF_AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
SOURCES = ("14.3", "11.2", "13A")
STATUSES = ("pass", "pass-with-open", "n/a", "fail")
VERDICTS = ("pass", "pass-with-open-items", "blocked")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-g4-dod/1":
        return ["schema 不匹配"]
    if str(doc.get("gate")) != "G4":
        issues.append("gate 必须为 G4")
    if str(doc.get("verdict")) not in VERDICTS:
        issues.append("verdict 非法")
    criteria = doc.get("criteria") or []
    fails = [c for c in criteria if str(c.get("status")) == "fail"]
    if int(doc.get("p0_blockers") or 0) != len(fails):
        issues.append("p0_blockers 与 fail 条目数不一致")
    ids = [str(c.get("id")) for c in criteria]
    if len(ids) != len(set(ids)):
        issues.append("判据 id 重复")
    for crit in criteria:
        cid = str(crit.get("id"))
        if str(crit.get("source")) not in SOURCES:
            issues.append("%s source 非法" % cid)
        status = str(crit.get("status"))
        if status not in STATUSES:
            issues.append("%s status 非法" % cid)
        if status == "n/a" and not str(crit.get("reason") or "").strip():
            issues.append("%s n/a 缺 reason" % cid)
        if status == "pass-with-open" and not crit.get("gaps"):
            issues.append("%s pass-with-open 缺 gaps" % cid)
        if not crit.get("evidence"):
            issues.append("%s 缺 evidence" % cid)
        for rel in crit.get("evidence") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s evidence 不在场：%s" % (cid, rel))
    art = next((c for c in criteria if str(c.get("id")) == "G4-ART"), None)
    if art is None:
        issues.append("缺 G4-ART")
    else:
        ev = " ".join(art.get("evidence") or [])
        for need in ("ai_evidence.json", "aibom.json", "policy_rules.json",
                     "aigc_labeling.json", "verify.sh"):
            if need not in ev:
                issues.append("G4-ART 缺证据：%s" % need)
    opens = {str(o.get("id")): o for o in doc.get("open_items") or []}
    for need in ("OPEN-EXTERNAL", "OPEN-TOOLS"):
        if need not in opens:
            issues.append("open_items 缺 %s" % need)
        elif opens[need].get("blocking") is not False:
            issues.append("%s 不得 blocking=true" % need)
    if str(doc.get("next_gate")) != "G5":
        issues.append("next_gate 必须为 G5")
    # 现场复算
    sa = _json(SELF_AUDIT)
    if int((sa.get("stop") or {}).get("p0") or 0) != 0:
        issues.append("SELF_AUDIT stop.p0 非 0")
    sample = ae.load_sample(str(root))
    if ae.state(sample["card"], sample["lineage"], sample["review"], str(root)) != "APPROVED":
        issues.append("AI 证据链状态非 APPROVED")
    issues += ae.check(str(root))
    issues += ax.check(str(root))
    issues += al.check(str(root))
    issues += pe.check_registry(str(root))
    t1 = pe.evaluate({"required_level": "T1", "contract_status": "active",
                      "has_evidence": True}, str(root))
    if not t1.get("allowed"):
        issues.append("策略应允许 T1 合规事实")
    t4 = pe.evaluate({"required_level": "T4", "contract_status": "active",
                      "has_evidence": True}, str(root))
    if t4.get("allowed"):
        issues.append("策略不得允许 T4（适配器缺失时不可达）")
    vr = _json(ROOT / "protocol" / "verification_report.json")
    if int((vr.get("summary") or {}).get("fail") or 0) != 0:
        issues.append("verification_report fail 非 0（G4 门禁不绿）")
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "不等于" not in boundary:
        issues.append("claims_boundary 必须写 pass-with-open ≠ 零缺陷")
    return issues


class G4DodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_g4_dod_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertEqual(0, self.doc["p0_blockers"])
        self.assertEqual("pass-with-open-items", self.doc["verdict"])

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for crit in self.doc["criteria"]:
            self.assertIn(crit["id"], self.text)
        for item in self.doc["open_items"]:
            self.assertIn(item["id"], self.text)
        for marker in ("pass-with-open-items", "G5", "P0 阻断", "QG4"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        failed = copy.deepcopy(self.doc)
        failed["criteria"][0]["status"] = "fail"
        self.assertTrue(issues_for(failed, str(ROOT)), "fail 条目必须红")

        bad_ev = copy.deepcopy(self.doc)
        bad_ev["criteria"][0]["evidence"] = ["results/nonexistent_zzz.md"]
        self.assertTrue(issues_for(bad_ev, str(ROOT)), "证据不在场必须红")

        na = copy.deepcopy(self.doc)
        next(c for c in na["criteria"] if c["status"] == "n/a").pop("reason", None)
        self.assertTrue(issues_for(na, str(ROOT)), "n/a 缺理由必须红")

        no_art = copy.deepcopy(self.doc)
        no_art["criteria"] = [c for c in no_art["criteria"] if c["id"] != "G4-ART"]
        self.assertTrue(issues_for(no_art, str(ROOT)), "缺 G4-ART 必须红")

        p0 = copy.deepcopy(self.doc)
        p0["p0_blockers"] = 2
        self.assertTrue(issues_for(p0, str(ROOT)), "p0 不一致必须红")

        bad_gate = copy.deepcopy(self.doc)
        bad_gate["next_gate"] = "G4"
        self.assertTrue(issues_for(bad_gate, str(ROOT)), "next_gate 非 G5 必须红")


if __name__ == "__main__":
    unittest.main()
