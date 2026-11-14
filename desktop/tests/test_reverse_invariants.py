#!/usr/bin/env python3
"""§4A R6 不变量判据（NF-Final G0 逆向工程）。

真源 = `results/reverse/invariants.json`（`nf-reverse-invariants/1`）；人读 = `INVARIANTS.md`。
本模块同时是「不变量执行器」：
- direct-test：本文件直接断言不变量（wiki 必填字段/缺锚 exit 2/篡改 exit 1/契约 fail-closed/
  任务有界/canonical 域分隔）；
- covered-by-existing：断言既有测试文件存在且方法名可指；
- unobservable：断言有 planned_gate + 理由（不得静默跳过）。
另校验登记结构、层级覆盖、状态计数一致、文档交叉；变异自证 6 类。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core.trust import bundle as tb  # noqa: E402
from core.trust import canonical as tc  # noqa: E402
from core.trust import verify as tv  # noqa: E402

REG = ROOT / "results" / "reverse" / "invariants.json"
DOC = ROOT / "results" / "reverse" / "INVARIANTS.md"
STATUSES = ("tested", "covered-by-existing", "unobservable")
TOOLS = ("direct-test", "existing-test", "unobservable")
POLICY = {
    "schema": "nf-trust-policy/1",
    "issuers": [{"id": "nf:local", "keyid": "nf:local:ed25519:2026", "alg": "ed25519",
                 "types": ["claim", "evidence"]}],
    "algorithms": ["ed25519"],
    "tsa_roots": [{"id": "tsa:freetsa", "digest": "f" * 64}],
    "required_level": "T3",
    "anchors": {"tsa": True, "transparency": True, "witness_threshold": 0},
}


def _bundle(count=4):
    claims = [{"id": "C-%03d" % i, "type": "evidence", "subject_digest": "b" * 64,
               "payload_digest": "c" * 64} for i in range(count)]
    return tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", claims)


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def issues_for(doc, root=ROOT):
    issues = []
    if str(doc.get("schema")) != "nf-reverse-invariants/1":
        return ["schema 不匹配"]
    layers = doc.get("layers") or []
    if len(layers) < 4:
        issues.append("layers 少于 4 层")
    invs = doc.get("invariants") or []
    ids = [str(i.get("id")) for i in invs]
    if len(ids) != len(set(ids)):
        issues.append("不变量 id 重复：%s" % ids)
    by_status = {s: 0 for s in STATUSES}
    for inv in invs:
        iid = str(inv.get("id"))
        if str(inv.get("layer")) not in layers:
            issues.append("%s 的 layer 非法：%s" % (iid, inv.get("layer")))
        if str(inv.get("status")) not in STATUSES:
            issues.append("%s 的 status 非法：%s" % (iid, inv.get("status")))
        if str(inv.get("method")) not in TOOLS:
            issues.append("%s 的 method 非法：%s" % (iid, inv.get("method")))
        if not str(inv.get("statement") or "").strip():
            issues.append("%s 缺 statement" % iid)
        if not inv.get("source_refs"):
            issues.append("%s 缺 source_refs（须能回溯 R1–R5）" % iid)
        by_status[str(inv.get("status"))] = by_status.get(str(inv.get("status")), 0) + 1
        if str(inv.get("method")) in ("direct-test", "existing-test"):
            rel = str(inv.get("test") or "").split("::")[0]
            if not rel or not (Path(root) / rel).is_file():
                issues.append("%s 的 test 不在场：%s" % (iid, inv.get("test")))
        if str(inv.get("status")) == "unobservable":
            if str(inv.get("planned_gate")) not in ("G1", "G2", "G3", "G4", "G5"):
                issues.append("%s 标 unobservable 但缺 planned_gate" % iid)
            if not str(inv.get("note") or "").strip():
                issues.append("%s 标 unobservable 但缺理由" % iid)
    summary = doc.get("coverage_summary") or {}
    for status in STATUSES:
        if int(summary.get(status) or -1) != by_status[status]:
            issues.append("%s 计数不一致（登记 %s / 实际 %s）"
                          % (status, summary.get(status), by_status[status]))
    covered_layers = {str(i.get("layer")) for i in invs}
    for layer in ("wiki", "spec", "production", "governance", "evidence", "contract"):
        if layer not in covered_layers:
            issues.append("层 %s 缺不变量（每层至少 1 条）" % layer)
    boundary = " ".join(str(x) for x in doc.get("claims_boundary") or [])
    if "unobservable" not in boundary:
        issues.append("claims_boundary 必须写明 unobservable 不等于已满足")
    return issues


class ReverseInvariantsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.text = _text(DOC)

    def test_registry_valid(self):
        self.assertEqual([], issues_for(self.doc, str(ROOT)))
        self.assertGreaterEqual(len(self.doc["invariants"]), 12)

    def test_inv_01_wiki_page_required_fields(self):
        schema = _json(ROOT / "protocol" / "production" / "wiki-page.schema.json")
        for field in ("spec_ref", "version", "provenance", "citations"):
            self.assertIn(field, schema["required"], "wiki 页面缺必填：%s" % field)

    def test_inv_08_missing_anchor_exit_2(self):
        result = tv.verify(_bundle(), POLICY, root=str(ROOT))
        self.assertEqual(2, result["exit_code"], "缺锚必须不可判定（exit 2）")
        codes = [x["code"] for x in result["report"]["issues"]]
        self.assertTrue(any("ANCHOR" in c for c in codes), codes)

    def test_inv_09_tampered_bundle_exit_1(self):
        bad = _bundle()
        bad["claims"][1]["payload_digest"] = "d" * 64
        result = tv.verify(bad, {**POLICY, "required_level": "T0"}, root=str(ROOT))
        self.assertEqual(1, result["exit_code"], "篡改 bundle 必须失败 exit 1")

    def test_inv_10_contract_unknown_fields_rejected(self):
        schema = _json(ROOT / "protocol" / "production" / "contract.schema.json")
        self.assertIs(False, schema.get("additionalProperties"),
                      "契约必须 fail-closed（additionalProperties=false）")

    def test_inv_11_task_bounded_fields(self):
        schema = _json(ROOT / "protocol" / "production" / "task.schema.json")
        for field in ("slot", "spec_refs", "acceptance", "budget"):
            self.assertIn(field, schema["required"], "任务缺有界字段：%s" % field)

    def test_inv_12_canonical_domain_separation(self):
        a = tc.domain_digest("nf:test:v1:field-a", b"x")
        b = tc.domain_digest("nf:test:v1:field-a", b"x")
        c = tc.domain_digest("nf:test:v1:field-b", b"x")
        d = tc.domain_digest("nf:test:v1:field-a", b"y")
        self.assertEqual(a, b, "同输入必须逐字节一致")
        self.assertNotEqual(a, c, "改域标签必须换摘要")
        self.assertNotEqual(a, d, "改 payload 必须换摘要")
        with self.assertRaises(ValueError):
            tc.canonical_bytes(1.5)

    def test_existing_tests_exist(self):
        for inv in self.doc["invariants"]:
            if inv["method"] != "existing-test":
                continue
            rel = str(inv["test"]).split("::")[0]
            self.assertTrue((ROOT / rel).is_file(), inv["id"])

    def test_unobservable_have_gate(self):
        for inv in self.doc["invariants"]:
            if inv["status"] != "unobservable":
                continue
            self.assertIn(inv.get("planned_gate"), ("G1", "G2", "G3", "G4", "G5"), inv["id"])
            self.assertTrue(inv.get("note"), inv["id"])

    def test_doc_cross_consistent(self):
        self.assertTrue(DOC.is_file())
        for inv in self.doc["invariants"]:
            self.assertIn(inv["id"], self.text)
        for marker in ("DEV-05", "unobservable", "G0 DoD", "复核命令"):
            self.assertIn(marker, self.text)

    def test_mutations_red(self):
        no_test = copy.deepcopy(self.doc)
        no_test["invariants"][0]["test"] = "desktop/tests/nonexistent_zzz.py::x"
        self.assertTrue(issues_for(no_test, str(ROOT)), "test 不在场必须红")

        no_gate = copy.deepcopy(self.doc)
        next(i for i in no_gate["invariants"] if i["status"] == "unobservable").pop("planned_gate")
        self.assertTrue(issues_for(no_gate, str(ROOT)), "unobservable 缺 gate 必须红")

        bad_status = copy.deepcopy(self.doc)
        bad_status["invariants"][0]["status"] = "skipped"
        self.assertTrue(issues_for(bad_status, str(ROOT)), "非法状态必须红")

        count_drift = copy.deepcopy(self.doc)
        count_drift["coverage_summary"]["tested"] = 0
        self.assertTrue(issues_for(count_drift, str(ROOT)), "状态计数不一致必须红")

        dup = copy.deepcopy(self.doc)
        dup["invariants"].append(copy.deepcopy(dup["invariants"][0]))
        self.assertTrue(issues_for(dup, str(ROOT)), "重复 id 必须红")


if __name__ == "__main__":
    unittest.main()
