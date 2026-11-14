#!/usr/bin/env python3
"""产品发现契约（NF-Final WP-0A，P1 盲区 BL-06）。

真源 = `protocol/product.json`（`nf-product/1`）；人读面 = `docs/product/{PRFAQ,GTM,INTERVIEWS}.md`。
判据：
1. 问题/JTBD 三要素、价值假设逐条挂「指标 + 反指标」、状态默认 unverified；
2. `validated-external` 只允许在存在真实访谈证据件（`results/product/interviews/*.json`，
   schema=nf-interview/1）时成立——不伪造访谈结论；
3. MVP 做/不做/成功判据、支持分级、定价假设（不得写价格/SLA 承诺）、试点 external-open；
4. 访谈计划（guide 在场、target_count ≥3、状态 planned-external）与 OPEN-PRODUCT/OPEN-METRICS
   显式登记；不以外部背书作为质量论据；
5. 变异自证：伪 validated、缺反指标、缺 open、缺 guide、写过 SLA、缺 JTBD 要素 —— 都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import product  # noqa: E402

REG = ROOT / "protocol" / "product.json"
DOCS = {
    "PRFAQ": ROOT / "docs" / "product" / "PRFAQ.md",
    "GTM": ROOT / "docs" / "product" / "GTM.md",
    "INTERVIEWS": ROOT / "docs" / "product" / "INTERVIEWS.md",
}
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class ProductContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_registry_valid(self):
        self.assertEqual([], product.validate(self.doc, str(ROOT)))
        summary = product.summary(self.doc, str(ROOT))
        self.assertGreaterEqual(summary["hypotheses"], 4)
        self.assertGreaterEqual(summary["metrics"], 3)
        self.assertGreaterEqual(summary["countermetrics"], 2)
        self.assertEqual(0, summary["external_validated"], "未执行访谈前不得有 validated-external")

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        for job in self.doc["problem"]["jtbd"]:
            self.assertIn(job["id"], self.texts["PRFAQ"])
        for hyp in self.doc["value_hypotheses"]:
            self.assertIn(hyp["id"], self.texts["PRFAQ"])
            self.assertEqual("unverified", hyp["status"],
                             "%s 未验证却在文档/登记里变了状态" % hyp["id"])
        for tier in self.doc["gtm"]["support_tiers"]:
            self.assertIn(tier["id"], self.texts["GTM"])
        for slot in self.doc["interviews"]["slots"]:
            self.assertIn(slot, self.texts["INTERVIEWS"])
        self.assertIn("planned-external", self.texts["INTERVIEWS"])

    def test_metric_countermetric_wiring(self):
        counters = {c["id"] for c in self.doc["countermetrics"]}
        for metric in self.doc["metrics"]:
            self.assertIn(metric["countermetric"], counters, metric["id"])
        for hyp in self.doc["value_hypotheses"]:
            self.assertIn(hyp["metric"], {m["id"] for m in self.doc["metrics"]})
            self.assertIn(hyp["countermetric"], counters)

    def test_external_open_registered(self):
        opens = {o["id"] for o in self.doc["open_items"]}
        self.assertIn("OPEN-PRODUCT", opens)
        self.assertIn("OPEN-PRODUCT", self.texts["PRFAQ"])
        self.assertEqual("planned-external", self.doc["interviews"]["status"])
        self.assertGreaterEqual(self.doc["interviews"]["target_count"], 3)
        self.assertTrue((ROOT / self.doc["interviews"]["guide"]).is_file())
        self.assertEqual("external-open", self.doc["gtm"]["pilot"]["status"])

    def test_no_overclaim(self):
        boundary = " ".join(self.doc["claims_boundary"])
        self.assertIn("外部背书", boundary)
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))
        self.assertNotIn("已验证需求", "\n".join(self.texts.values()),
                         "不得写「已验证需求」（未执行访谈）")

    def test_mutations_red(self):
        fake_valid = copy.deepcopy(self.doc)
        fake_valid["value_hypotheses"][0]["status"] = "validated-external"
        self.assertTrue(product.validate(fake_valid, str(ROOT)),
                        "无访谈证据件却标 validated-external 必须红")

        bad_metric = copy.deepcopy(self.doc)
        bad_metric["metrics"][0]["countermetric"] = "CM-99"
        self.assertTrue(product.validate(bad_metric, str(ROOT)), "指标挂不存在反指标必须红")

        no_open = copy.deepcopy(self.doc)
        no_open["open_items"] = [o for o in no_open["open_items"] if o["id"] != "OPEN-PRODUCT"]
        self.assertTrue(product.validate(no_open, str(ROOT)), "缺 OPEN-PRODUCT 必须红")

        no_guide = copy.deepcopy(self.doc)
        no_guide["interviews"]["guide"] = "docs/product/nonexistent_zzz.md"
        self.assertTrue(product.validate(no_guide, str(ROOT)), "访谈 guide 不在场必须红")

        sla = copy.deepcopy(self.doc)
        sla["gtm"]["pricing_hypothesis"]["note"] = "承诺 SLA 99.9%"
        self.assertTrue(product.validate(sla, str(ROOT)), "写 SLA 承诺必须红")

        bad_jtbd = copy.deepcopy(self.doc)
        bad_jtbd["problem"]["jtbd"][0]["so"] = ""
        self.assertTrue(product.validate(bad_jtbd, str(ROOT)), "缺 JTBD 要素必须红")

        no_owner = copy.deepcopy(self.doc)
        no_owner["value_hypotheses"][0]["owner"] = ""
        self.assertTrue(product.validate(no_owner, str(ROOT)), "假设缺 owner 必须红")


if __name__ == "__main__":
    unittest.main()
