#!/usr/bin/env python3
"""NF-Final 最终 Gate 审计判据（质量报告收口）。

真源 = `results/final_dod.json`（`nf-final-dod/1`）；人读 = `FINAL_DOD.md`。
判据：Gate 汇总齐全且 P0=0；门禁实测与 quality_baseline/verify_report 一致；OPEN 清单带 owner
且非阻断；claims 边界；现场复算（G0–G4 DoD、conformance、CQ、SELF_AUDIT、稳定性、文档 claims）。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import docs_claims as dc  # noqa: E402
from core import quality_baseline as qb  # noqa: E402
from core import stability as st  # noqa: E402

REG = ROOT / "results" / "final_dod.json"
DOC = ROOT / "results" / "FINAL_DOD.md"
VERIFY = ROOT / "protocol" / "verification_report.json"
CONF = ROOT / "protocol" / "conformance_report.json"
CQ = ROOT / "results" / "cq" / "scan.json"
SELF_AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
GATES = ("G0", "G1", "G2", "G3", "G4", "G5")
VERDICTS = ("pass", "pass-with-open-items", "blocked")
DOD_IDS = tuple("FIN-0%d" % i for i in range(1, 9))


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-final-dod/1":
        return ["schema 不匹配"]
    gates = doc.get("gates") or []
    ids = [str(g.get("id")) for g in gates]
    if ids != list(GATES):
        issues.append("gates 必须恰为 G0…G5（当前 %s）" % ids)
    fails = 0
    for gate in gates:
        gid = str(gate.get("id"))
        if str(gate.get("verdict")) not in VERDICTS:
            issues.append("%s verdict 非法" % gid)
        if int(gate.get("p0") or 0) != 0:
            fails += 1
            issues.append("%s P0 非 0（阻断）" % gid)
        dod = str(gate.get("dod") or "")
        if dod.startswith("results/") and not (Path(root) / dod).is_file():
            issues.append("%s dod 件不在场：%s" % (gid, dod))
    if fails:
        issues.append("最终 Gate 存在 P0 阻断")
    meas = doc.get("gate_measurements") or {}
    if int(meas.get("checks") or 0) != qb.EXPECTED_CHECKS:
        issues.append("gate_measurements.checks 与 quality_baseline 不一致")
    if int(meas.get("pass") or 0) != qb.EXPECTED_PASS:
        issues.append("gate_measurements.pass 与 quality_baseline 不一致")
    if str(meas.get("label")) != qb.CHECK_LABEL:
        issues.append("gate_measurements.label 与 quality_baseline 不一致")
    if int(meas.get("fail") or 0) != 0:
        issues.append("gate_measurements.fail 非 0")
    dod_rows = {str(r.get("id")): r for r in doc.get("final_dod") or []}
    for need in DOD_IDS:
        if need not in dod_rows:
            issues.append("final_dod 缺 %s" % need)
        elif str(dod_rows[need].get("status")) != "pass":
            issues.append("%s 非 pass" % need)
    opens = {str(o.get("id")): o for o in doc.get("open_items") or []}
    for need in ("OPEN-EXTERNAL", "OPEN-TOOLS", "OPEN-PRODUCT"):
        if need not in opens:
            issues.append("open_items 缺 %s" % need)
    for oid, item in opens.items():
        if item.get("blocking") is not False:
            issues.append("OPEN %s 不得 blocking=true（收口不关闭外部项，但不得阻断）" % oid)
        if not item.get("owner"):
            issues.append("OPEN %s 缺 owner" % oid)
    claims = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    for marker in ("不等于", "不声称"):
        if marker not in claims:
            issues.append("claims_boundary 必须含「%s」" % marker)
    repro = doc.get("reproduction") or {}
    if "verify.sh --checks-only" not in str(repro.get("gate")):
        issues.append("reproduction.gate 必须给 verify.sh --checks-only")
    if not any("--full" in str(x) for x in repro.get("unrun") or []):
        issues.append("reproduction.unrun 必须如实列出未跑的 full 档")
    # 现场复算
    vr = _json(VERIFY)
    if int((vr.get("summary") or {}).get("fail") or 0) != 0:
        issues.append("verification_report fail 非 0")
    declared = vr.get("declared") or {}
    if int(declared.get("expected_checks") or 0) != qb.EXPECTED_CHECKS:
        issues.append("verification_report declared.expected_checks 与基线不一致")
    if int(declared.get("expected_pass") or 0) != qb.EXPECTED_PASS:
        issues.append("verification_report declared.expected_pass 与基线不一致")
    conf = _json(CONF)
    if str(conf.get("verdict")) != "conformant":
        issues.append("conformance verdict 非 conformant")
    cq = _json(CQ)
    if int(cq.get("p0") or 0) != 0:
        issues.append("CQ P0 非 0")
    sa = _json(SELF_AUDIT)
    if int((sa.get("stop") or {}).get("p0") or 0) != 0:
        issues.append("SELF_AUDIT P0 非 0")
    issues += st.check(str(root))
    issues += dc.check(str(root))
    return issues


class FinalDodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_final_dod_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertEqual("nf-final-dod/1", self.doc["schema"])

    def test_doc_cross_consistent(self):
        for gate in self.doc["gates"]:
            self.assertIn(gate["id"], self.text)
        for row in self.doc["final_dod"]:
            self.assertIn(row["id"], self.text)
        for item in self.doc["open_items"]:
            self.assertIn(item["id"], self.text)
        for marker in ("pass-with-open-items", "P0 阻断", "FINAL DOD", "未跑"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        bad_p0 = copy.deepcopy(self.doc)
        bad_p0["gates"][1]["p0"] = 1
        self.assertTrue(issues_for(bad_p0, str(ROOT)), "Gate P0 非 0 必须红")

        bad_meas = copy.deepcopy(self.doc)
        bad_meas["gate_measurements"]["pass"] = 90
        self.assertTrue(issues_for(bad_meas, str(ROOT)), "门禁数字漂移必须红")

        missing_gate = copy.deepcopy(self.doc)
        missing_gate["gates"] = [g for g in missing_gate["gates"] if g["id"] != "G5"]
        self.assertTrue(issues_for(missing_gate, str(ROOT)), "缺 Gate 必须红")

        blocking = copy.deepcopy(self.doc)
        blocking["open_items"][0]["blocking"] = True
        self.assertTrue(issues_for(blocking, str(ROOT)), "OPEN 阻断必须红")

        no_owner = copy.deepcopy(self.doc)
        no_owner["open_items"][0].pop("owner", None)
        self.assertTrue(issues_for(no_owner, str(ROOT)), "OPEN 缺 owner 必须红")

        bad_claims = copy.deepcopy(self.doc)
        bad_claims["claims_boundary"] = ["一切通过"]
        self.assertTrue(issues_for(bad_claims, str(ROOT)), "claims 边界缺失必须红")


if __name__ == "__main__":
    unittest.main()
