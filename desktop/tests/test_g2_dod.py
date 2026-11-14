#!/usr/bin/env python3
"""G2 DoD 收口审计判据（NF-Final §14.3 / §11.2 G2 / §13A QG2 / L4·L7）。

真源 = `results/g2_dod.json`（`nf-g2-dod/1`）；人读 = `G2_DOD.md`。
判据：
1. 结构：gate=G2；verdict/P0 一致；source/status 词表；n-a 必写 reason；pass-with-open 必写 gaps；证据在场；
2. **现场复算**：两 adapter E2E delivered；output-report ok；delivery verify 无 issue；adapter parity；
   production metrics check 空且 measured/no-data 诚实；SELF_AUDIT stop.p0=0；
3. G2-ART 必须含 WP-20…24 全部证据；open_items 至少 OPEN-PRODUCT/OPEN-EXTERNAL 且非阻断；
4. 文档交叉；变异自证 6 类。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import agent_adapter as aa  # noqa: E402
from core import assembly_runtime as ar  # noqa: E402
from core import context_packer as cp  # noqa: E402
from core import delivery as dv  # noqa: E402
from core import output_validation as ov  # noqa: E402
from core import production_metrics as pm  # noqa: E402
from core import spec_compiler as sc  # noqa: E402

REG = ROOT / "results" / "g2_dod.json"
DOC = ROOT / "results" / "G2_DOD.md"
SELF_AUDIT = ROOT / "results" / "trust" / "SELF_AUDIT.json"
PACK_DIR = "results/delivery/wiki-module-M06"
INTENT = "spec/intents/sample-document.json"
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
    if str(doc.get("schema")) != "nf-g2-dod/1":
        return ["schema 不匹配"]
    if str(doc.get("gate")) != "G2":
        issues.append("gate 必须为 G2")
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
    art = next((c for c in criteria if str(c.get("id")) == "G2-ART"), None)
    if art is None:
        issues.append("缺 G2-ART")
    else:
        ev = " ".join(art.get("evidence") or [])
        for need in ("agent_adapter.py", "assembly_runtime.py", "output_validation.py",
                     "delivery.py", "production_metrics.py", "verify.sh"):
            if need not in ev:
                issues.append("G2-ART 缺证据：%s" % need)
    opens = {str(o.get("id")): o for o in doc.get("open_items") or []}
    for need in ("OPEN-PRODUCT", "OPEN-EXTERNAL"):
        if need not in opens:
            issues.append("open_items 缺 %s" % need)
        elif opens[need].get("blocking") is not False:
            issues.append("%s 不得 blocking=true" % need)
    if str(doc.get("next_gate")) != "G3":
        issues.append("next_gate 必须为 G3")
    # 现场复算
    sa = _json(SELF_AUDIT)
    if int((sa.get("stop") or {}).get("p0") or 0) != 0:
        issues.append("SELF_AUDIT stop.p0 非 0")
    for aid in ("mock", "local-template"):
        rec = ar.run(INTENT, aid, str(root))
        if rec["run"]["status"] != "delivered":
            issues.append("%s E2E 未 delivered" % aid)
        issues += ar.validate_record(rec, str(root))
    intent = _json(ROOT / INTENT)
    task = sc.compile_intent(intent, str(root), INTENT)["tasks"][0]
    pack = cp.pack_task(task, str(root), budget_chars=2000, role="author")
    out = aa.run("mock", task, pack, str(root))
    if not ov.validate(out, task, pack, str(root))["ok"]:
        issues.append("output-report 未过")
    dels, drep = dv.verify(PACK_DIR, str(root))
    issues += dels
    if not drep.get("ok"):
        issues.append("delivery verify 未过")
    ad = _json(ROOT / "results" / "adapter" / "adapter-report.json")
    if not ad.get("parity"):
        issues.append("adapter parity 非 true")
    issues += pm.check(str(root))
    metrics = {m["id"]: m for m in _json(ROOT / "results" / "production" / "metrics.json")["metrics"]}
    for mid in ("M-01", "M-02", "M-03", "M-04"):
        if metrics[mid]["status"] != "measured":
            issues.append("%s 非 measured" % mid)
    for metric in metrics.values():
        if metric["status"] == "no-data" and metric.get("value") is not None:
            issues.append("%s no-data 但填了 value" % metric["id"])
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "不等于" not in boundary:
        issues.append("claims_boundary 必须写 pass-with-open ≠ 零缺陷")
    return issues


class G2DodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_g2_dod_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertEqual(0, self.doc["p0_blockers"])
        self.assertEqual("pass-with-open-items", self.doc["verdict"])

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for crit in self.doc["criteria"]:
            self.assertIn(crit["id"], self.text)
        for item in self.doc["open_items"]:
            self.assertIn(item["id"], self.text)
        for marker in ("pass-with-open-items", "G3", "P0 阻断", "QG2"):
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
        no_art["criteria"] = [c for c in no_art["criteria"] if c["id"] != "G2-ART"]
        self.assertTrue(issues_for(no_art, str(ROOT)), "缺 G2-ART 必须红")

        p0 = copy.deepcopy(self.doc)
        p0["p0_blockers"] = 2
        self.assertTrue(issues_for(p0, str(ROOT)), "p0 不一致必须红")

        bad_gate = copy.deepcopy(self.doc)
        bad_gate["next_gate"] = "G2"
        self.assertTrue(issues_for(bad_gate, str(ROOT)), "next_gate 非 G3 必须红")


if __name__ == "__main__":
    unittest.main()
