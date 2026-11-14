#!/usr/bin/env python3
"""G0 DoD 收口审计判据（NF-Final §14.3/§11.2/§13A/§4A）。

真源 = `results/g0_dod.json`（`nf-g0-dod/1`）；人读 = `G0_DOD.md`。
判据：
1. 结构：gate=G0；verdict ∈ {pass, pass-with-open-items, blocked}；P0 阻断 = fail 条目数；
2. 每条判据：source/status 词表；n/a 必写 reason；pass-with-open 必写 gaps；evidence 全部在场；
3. DOD-06 现场核 SELF_AUDIT（stop.p0==0）；G0-4A 必须含 §4A 七件全部路径；
4. open_items：OPEN-PRODUCT/OPEN-EXTERNAL 必须在场、有 owner、blocking=false 显式；
   OPEN-PRODUCT 与 product.json 对齐，OPEN-EXTERNAL 与 assurance gaps 对齐；
5. 文档交叉（全部 id/verdict/next_gate）；变异自证 6 类。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

REG = ROOT / "results" / "g0_dod.json"
DOC = ROOT / "results" / "G0_DOD.md"
SELF_AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
SOURCES = ("14.3", "11.2", "3A", "4A", "13A", "12.1/12.2", "13B", "13C/CQ2-G0")
STATUSES = ("pass", "pass-with-open", "n/a", "fail")
VERDICTS = ("pass", "pass-with-open-items", "blocked")
REVERSE_FILES = ("results/reverse/INVENTORY.md", "results/reverse/CONTRACT_MAP.md",
                 "results/reverse/BEHAVIOR.md", "results/reverse/COUPLING.md",
                 "results/reverse/FAILURE_ARCHAEOLOGY.md", "results/reverse/PEER_DIFF.md",
                 "results/reverse/INVARIANTS.md")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-g0-dod/1":
        return ["schema 不匹配"]
    if str(doc.get("gate")) != "G0":
        issues.append("gate 必须为 G0")
    verdict = str(doc.get("verdict"))
    if verdict not in VERDICTS:
        issues.append("verdict 非法：%s" % verdict)
    criteria = doc.get("criteria") or []
    if len(criteria) < 8:
        issues.append("判据少于 8 条（§14.3 有 8 条）")
    fails = [c for c in criteria if str(c.get("status")) == "fail"]
    p0 = int(doc.get("p0_blockers") or 0)
    if p0 != len(fails):
        issues.append("p0_blockers 与 fail 条目数不一致（%s / %s）" % (p0, len(fails)))
    if verdict == "pass" and any(status != "pass" for status in
                                (str(c.get("status")) for c in criteria)):
        issues.append("verdict=pass 但存在非 pass 判据")
    ids = [str(c.get("id")) for c in criteria]
    if len(ids) != len(set(ids)):
        issues.append("判据 id 重复：%s" % ids)
    for crit in criteria:
        cid = str(crit.get("id"))
        if str(crit.get("source")) not in SOURCES:
            issues.append("%s 的 source 非法：%s" % (cid, crit.get("source")))
        status = str(crit.get("status"))
        if status not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (cid, status))
        if not str(crit.get("text") or "").strip():
            issues.append("%s 缺 text" % cid)
        for rel in crit.get("evidence") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 evidence 不在场：%s" % (cid, rel))
        if not crit.get("evidence"):
            issues.append("%s 缺 evidence" % cid)
        if status == "n/a" and not str(crit.get("reason") or "").strip():
            issues.append("%s 标 n/a 但缺 reason" % cid)
        if status == "pass-with-open" and not crit.get("gaps"):
            issues.append("%s 标 pass-with-open 但缺 gaps" % cid)
    # DOD-06 现场核 SELF_AUDIT
    sa = _json(SELF_AUDIT)
    if int((sa.get("stop") or {}).get("p0") or 0) != 0:
        issues.append("SELF_AUDIT stop.p0 非 0（与 DOD-06 冲突）")
    # G0-4A 必须含七件
    four_a = next((c for c in criteria if str(c.get("id")) == "G0-4A"), None)
    if four_a is None:
        issues.append("缺 G0-4A 判据")
    else:
        ev = set(four_a.get("evidence") or [])
        for rel in REVERSE_FILES:
            if rel not in ev:
                issues.append("G0-4A 缺 §4A 产物：%s" % rel)
    # open_items 对齐
    opens = {str(o.get("id")): o for o in doc.get("open_items") or []}
    for need in ("OPEN-PRODUCT", "OPEN-EXTERNAL"):
        if need not in opens:
            issues.append("open_items 缺 %s" % need)
        elif "owner" not in opens[need] or "blocking" not in opens[need]:
            issues.append("%s 必须写 owner/blocking" % need)
        elif opens[need].get("blocking") is not False:
            issues.append("%s 不得标 blocking=true（外部操作非 G0 阻断）" % need)
    product = _json(ROOT / "protocol" / "product.json")
    if "OPEN-PRODUCT" not in {str(o.get("id")) for o in product.get("open_items") or []}:
        issues.append("OPEN-PRODUCT 未在 product.json 登记")
    assurance = _json(ROOT / "results" / "assurance" / "CLAIMS.json")
    if "OPEN-EXTERNAL" not in {str(o.get("id")) for o in assurance.get("gaps") or []}:
        issues.append("OPEN-EXTERNAL 未在保证案例 gaps 登记")
    if str(doc.get("next_gate")) != "G1":
        issues.append("next_gate 必须为 G1")
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "不等于" not in boundary:
        issues.append("claims_boundary 必须写明 pass-with-open ≠ 零缺陷")
    return issues


class G0DodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_g0_dod_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertEqual(0, self.doc["p0_blockers"])
        self.assertEqual("pass-with-open-items", self.doc["verdict"])

    def test_self_audit_p0_zero(self):
        sa = _json(SELF_AUDIT)
        self.assertEqual(0, int((sa.get("stop") or {}).get("p0") or 0))

    def test_4a_files_present(self):
        for rel in REVERSE_FILES:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for crit in self.doc["criteria"]:
            self.assertIn(crit["id"], self.text)
        for item in self.doc["open_items"]:
            self.assertIn(item["id"], self.text)
        for marker in ("pass-with-open-items", "G1", "P0 阻断", "复核命令"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        failed = copy.deepcopy(self.doc)
        failed["criteria"][0]["status"] = "fail"
        self.assertTrue(issues_for(failed, str(ROOT)), "fail 条目必须红")

        bad_evidence = copy.deepcopy(self.doc)
        bad_evidence["criteria"][0]["evidence"] = ["results/nonexistent_zzz.md"]
        self.assertTrue(issues_for(bad_evidence, str(ROOT)), "证据不在场必须红")

        na_no_reason = copy.deepcopy(self.doc)
        next(c for c in na_no_reason["criteria"] if c["status"] == "n/a").pop("reason", None)
        self.assertTrue(issues_for(na_no_reason, str(ROOT)), "n/a 缺理由必须红")

        open_no_gap = copy.deepcopy(self.doc)
        next(c for c in open_no_gap["criteria"] if c["status"] == "pass-with-open")["gaps"] = []
        self.assertTrue(issues_for(open_no_gap, str(ROOT)), "pass-with-open 缺 gaps 必须红")

        no_4a = copy.deepcopy(self.doc)
        no_4a["criteria"] = [c for c in no_4a["criteria"] if c["id"] != "G0-4A"]
        self.assertTrue(issues_for(no_4a, str(ROOT)), "缺 G0-4A 必须红")

        p0_mismatch = copy.deepcopy(self.doc)
        p0_mismatch["p0_blockers"] = 5
        self.assertTrue(issues_for(p0_mismatch, str(ROOT)), "p0 不一致必须红")


if __name__ == "__main__":
    unittest.main()
