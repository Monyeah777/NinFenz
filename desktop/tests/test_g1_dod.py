#!/usr/bin/env python3
"""G1 DoD 收口审计判据（NF-Final §14.3 / §11.2 G1 / §13A QG1 / L3）。

真源 = `results/g1_dod.json`（`nf-g1-dod/1`）；人读 = `results/G1_DOD.md`。
判据：
1. 结构：gate=G1；verdict ∈ {pass, pass-with-open-items, blocked}；P0 = fail 条目数；
2. 每条：source/status 词表；n/a 必写 reason；pass-with-open 必写 gaps；evidence 全部在场；
3. **现场复算**：Wiki 页面数/类型覆盖（133：14/13/3/100/3）；spec 编译确定性+校验；
   context pack citation_rate=1.0 且 over_budget=false；SELF_AUDIT stop.p0=0；
4. G1-ART 必须含 WP-10…13 全部证据；open_items 至少 OPEN-PRODUCT/OPEN-EXTERNAL 且非阻断；
5. 文档交叉（全部 id/verdict/next_gate）；变异自证 6 类。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import context_packer as cp  # noqa: E402
from core import spec_compiler as sc  # noqa: E402
from core import wiki_compiler as wc  # noqa: E402

REG = ROOT / "results" / "g1_dod.json"
DOC = ROOT / "results" / "G1_DOD.md"
SELF_AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
SOURCES = ("14.3", "11.2", "13A")
STATUSES = ("pass", "pass-with-open", "n/a", "fail")
VERDICTS = ("pass", "pass-with-open-items", "blocked")
EXPECTED_TYPES = {"protocol": 14, "module": 13, "pipeline": 3, "domain": 100, "asset": 3}


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-g1-dod/1":
        return ["schema 不匹配"]
    if str(doc.get("gate")) != "G1":
        issues.append("gate 必须为 G1")
    verdict = str(doc.get("verdict"))
    if verdict not in VERDICTS:
        issues.append("verdict 非法：%s" % verdict)
    criteria = doc.get("criteria") or []
    if len(criteria) < 12:
        issues.append("判据少于 12 条（G1 DoD + QG1 应有更多）")
    fails = [c for c in criteria if str(c.get("status")) == "fail"]
    if int(doc.get("p0_blockers") or 0) != len(fails):
        issues.append("p0_blockers 与 fail 条目数不一致")
    ids = [str(c.get("id")) for c in criteria]
    if len(ids) != len(set(ids)):
        issues.append("判据 id 重复")
    for crit in criteria:
        cid = str(crit.get("id"))
        if str(crit.get("source")) not in SOURCES:
            issues.append("%s 的 source 非法：%s" % (cid, crit.get("source")))
        status = str(crit.get("status"))
        if status not in STATUSES:
            issues.append("%s 的 status 非法" % cid)
        if status == "n/a" and not str(crit.get("reason") or "").strip():
            issues.append("%s 标 n/a 但缺 reason" % cid)
        if status == "pass-with-open" and not crit.get("gaps"):
            issues.append("%s 标 pass-with-open 但缺 gaps" % cid)
        for rel in crit.get("evidence") or []:
            if not (Path(root) / rel).exists():
                issues.append("%s 的 evidence 不在场：%s" % (cid, rel))
        if not crit.get("evidence"):
            issues.append("%s 缺 evidence" % cid)
    four = next((c for c in criteria if str(c.get("id")) == "G1-ART"), None)
    if four is None:
        issues.append("缺 G1-ART")
    else:
        ev = " ".join(four.get("evidence") or [])
        for need in ("wiki_compiler.py", "spec_compiler.py", "context_packer.py", "verify.sh"):
            if need not in ev:
                issues.append("G1-ART 缺证据：%s" % need)
    opens = {str(o.get("id")): o for o in doc.get("open_items") or []}
    for need in ("OPEN-PRODUCT", "OPEN-EXTERNAL"):
        if need not in opens:
            issues.append("open_items 缺 %s" % need)
        elif opens[need].get("blocking") is not False:
            issues.append("%s 不得标 blocking=true" % need)
    if str(doc.get("next_gate")) != "G2":
        issues.append("next_gate 必须为 G2")
    # 现场复算
    sa = _json(SELF_AUDIT)
    if int((sa.get("stop") or {}).get("p0") or 0) != 0:
        issues.append("SELF_AUDIT stop.p0 非 0")
    pages, rest = wc.build(str(root))
    counts = {}
    for page in pages.get("pages") or []:
        counts[page["type"]] = counts.get(page["type"], 0) + 1
    if counts != EXPECTED_TYPES:
        issues.append("Wiki 类型覆盖与记录不一致：%s" % counts)
    intent = _json(ROOT / "spec/intents/sample-document.json")
    b1 = sc.compile_intent(intent, str(root), "spec/intents/sample-document.json")
    b2 = sc.compile_intent(intent, str(root), "spec/intents/sample-document.json")
    if sc.render(b1) != sc.render(b2):
        issues.append("spec 编译不确定")
    issues += sc.validate_bundle(b1, str(root))
    pack = cp.pack_task(b1["tasks"][0], str(root), budget_chars=4000, role="reviewer")
    if pack["report"]["citation_rate"] != 1.0:
        issues.append("context pack citation_rate 非 100%%")
    if pack["report"]["over_budget"]:
        issues.append("context pack 超预算")
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "不等于" not in boundary:
        issues.append("claims_boundary 必须写明 pass-with-open ≠ 零缺陷")
    return issues


class G1DodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_g1_dod_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertEqual(0, self.doc["p0_blockers"])
        self.assertEqual("pass-with-open-items", self.doc["verdict"])

    def test_live_metrics(self):
        pages, rest = wc.build(str(ROOT))
        self.assertEqual(133, len(pages["pages"]))
        counts = {}
        for page in pages["pages"]:
            counts[page["type"]] = counts.get(page["type"], 0) + 1
        self.assertEqual(EXPECTED_TYPES, counts)

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for crit in self.doc["criteria"]:
            self.assertIn(crit["id"], self.text)
        for item in self.doc["open_items"]:
            self.assertIn(item["id"], self.text)
        for marker in ("pass-with-open-items", "G2", "P0 阻断", "QG1"):
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
        no_art["criteria"] = [c for c in no_art["criteria"] if c["id"] != "G1-ART"]
        self.assertTrue(issues_for(no_art, str(ROOT)), "缺 G1-ART 必须红")

        p0 = copy.deepcopy(self.doc)
        p0["p0_blockers"] = 3
        self.assertTrue(issues_for(p0, str(ROOT)), "p0 不一致必须红")

        bad_gate = copy.deepcopy(self.doc)
        bad_gate["next_gate"] = "G1"
        self.assertTrue(issues_for(bad_gate, str(ROOT)), "next_gate 非 G2 必须红")


if __name__ == "__main__":
    unittest.main()
