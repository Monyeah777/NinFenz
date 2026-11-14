#!/usr/bin/env python3
"""AI 治理 + 评测效度契约（NF-Final WP-0F，P0 盲区 BL-02/BL-05）。

真源 = `protocol/ai_governance.json`（`nf-ai-governance/1`）+ `protocol/eval_validity.json`
（`nf-eval-validity/1`）；人读面 = `docs/ai/AI_GOVERNANCE.md` + `docs/eval/EVAL_PROTOCOL.md`；
具体预注册协议 = `protocol/eval/protocol.json`；inter-rater 样本 = `results/eval/interrater_sample.json`。
判据：
1. 登记：影响评估四标准、人类监督/透明度/救济证据在场；风险登记概率/影响/缓解/owner/状态，
   非 enforced 必须写 planned_gate；监管映射覆盖六个框架，claim 只允许 mechanism-alignment/not-claimed；
2. 效度：预注册字段 + 冻结规则；样本量 ≥3；每个 metric 必须挂存在的 countermetric；
   五类效度威胁有 check+证据；具体协议必须过 `eval_harness.validate_protocol` 且已冻结；
3. inter-rater：Cohen's kappa 由样本现算且 ≥0.6；构造的低一致性样本必须被判失败；
4. 不越级：不声称合规/认证；打分不写回运行时（no_scoring 恒真）；
5. 变异自证：删风险行/reclaim 合规/指标缺反指标/kappa 阈值非法/缺预注册字段/缺监管框架，
   判据都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ai_governance as ag  # noqa: E402
from core import eval_harness as eh  # noqa: E402
from core import eval_validity as ev  # noqa: E402

AI = ROOT / "protocol" / "ai_governance.json"
EVAL = ROOT / "protocol" / "eval_validity.json"
DOCS = {
    "AI": ROOT / "docs" / "ai" / "AI_GOVERNANCE.md",
    "EVAL": ROOT / "docs" / "eval" / "EVAL_PROTOCOL.md",
}
NEGATION = ("不", "非", "无", "未")
TEST_EVIDENCE = ("desktop/tests/", "verify.sh", "scripts/")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class AiEvalContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai = _json(AI)
        cls.eval = _json(EVAL)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}
        cls.sample = _json(ROOT / "results" / "eval" / "interrater_sample.json")

    def test_registries_valid(self):
        self.assertEqual([], ag.validate(self.ai, str(ROOT)))
        self.assertEqual([], ev.validate(self.eval, str(ROOT)))

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        for criterion in self.ai["impact_assessment"]["criteria"]:
            self.assertIn(criterion["id"], self.texts["AI"])
        for risk in self.ai["model_risk_register"]:
            self.assertIn(risk["id"], self.texts["AI"], "风险未入文档：%s" % risk["id"])
        for row in self.ai["regulatory_mapping"]:
            name = row["framework"].split("（")[0].split(" ")[0]
            self.assertIn(name, self.texts["AI"], "框架未入文档：%s" % row["framework"])
        for cm in self.eval["countermetrics"]:
            self.assertIn(cm["id"], self.texts["EVAL"])
        for metric in self.eval["metrics"]:
            self.assertIn(metric["id"], self.texts["EVAL"])
        for threat in self.eval["validity_threats"]:
            self.assertIn(threat["id"], self.texts["EVAL"])

    def test_ai_claims_restricted_and_no_overclaim(self):
        boundary = " ".join(self.ai["scope"]["claims_boundary"])
        self.assertIn("不声称", boundary, "claims_boundary 必须显式否定合规声明")
        for row in self.ai["regulatory_mapping"]:
            self.assertIn(row["claim"], ag.CLAIMS,
                          "%s 的 claim 越界：%s" % (row["framework"], row["claim"]))
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))

    def test_risk_register_rules(self):
        risks = self.ai["model_risk_register"]
        self.assertGreaterEqual(len(risks), 4)
        for risk in risks:
            self.assertIn(risk["status"], ag.STATUSES)
            if risk["status"] in ("partial", "planned"):
                self.assertIn(risk.get("planned_gate"), ag.GATES,
                              "%s 标 %s 必须写 planned_gate" % (risk["id"], risk["status"]))
            if risk["status"] == "enforced":
                self.assertTrue(any(str(x).startswith(TEST_EVIDENCE) for x in risk["evidence"]),
                                "%s 标 enforced 但缺测试证据" % risk["id"])
        summary = ag.risk_summary(self.ai)
        self.assertEqual(len(risks), summary["risks"])
        self.assertEqual(len(self.ai["regulatory_mapping"]), summary["frameworks"])

    def test_concrete_protocol_preregistered(self):
        protocol = eh.load_protocol(str(ROOT))
        self.assertTrue(protocol.get("frozen_before_run"))
        self.assertEqual([], eh.validate_protocol(protocol))
        dims = {str(d.get("id")) for d in protocol.get("dimensions") or []}
        mapped = {m["name"] for m in self.eval["metrics"]}
        self.assertEqual(dims, mapped, "指标映射必须覆盖具体协议的全部维度")

    def test_interrater_kappa(self):
        report = ev.interrater(self.eval, str(ROOT))
        self.assertEqual("cohen_kappa", report["method"])
        self.assertEqual("pass", report["status"], report)
        self.assertAlmostEqual(0.833333, report["kappa"], places=5)
        # 低一致性样本必须被判失败（同一算法，不是写死结论）
        low = [("pass", "fail")] * 6 + [("pass", "pass")] * 2
        self.assertLess(ev.cohen_kappa(low), report["min_kappa"])

    def test_countermetric_wiring(self):
        counters = {c["id"] for c in self.eval["countermetrics"]}
        for metric in self.eval["metrics"]:
            self.assertIn(metric["countermetric"], counters,
                          "%s 未挂反指标" % metric["id"])
        self.assertGreaterEqual(len(counters), 3)

    def test_no_runtime_scoring(self):
        verify = _json(ROOT / "protocol" / "trust" / "verify.schema.json")
        self.assertIs(True, verify["properties"]["no_scoring"].get("const"),
                      "no_scoring 必须恒真（ADR-010）")
        threats = {t["id"] for t in self.eval["validity_threats"]}
        self.assertIn("VT-05", threats, "必须有一条威胁覆盖「打分写回运行时」")

    def test_mutations_red(self):
        bad_claim = copy.deepcopy(self.ai)
        bad_claim["regulatory_mapping"][0]["claim"] = "compliant"
        self.assertTrue(ag.validate(bad_claim, str(ROOT)), "claim 声称合规必须红")

        no_gate = copy.deepcopy(self.ai)
        for risk in no_gate["model_risk_register"]:
            if risk["status"] == "partial":
                risk.pop("planned_gate", None)
                break
        self.assertTrue(ag.validate(no_gate, str(ROOT)), "partial 缺 planned_gate 必须红")

        missing_framework = copy.deepcopy(self.ai)
        missing_framework["regulatory_mapping"] = [
            r for r in missing_framework["regulatory_mapping"] if "EU AI Act" not in r["framework"]]
        self.assertTrue(ag.validate(missing_framework, str(ROOT)), "缺监管框架必须红")

        bad_evidence = copy.deepcopy(self.ai)
        bad_evidence["model_risk_register"][0]["evidence"] = ["desktop/tests/nonexistent_zzz.py"]
        self.assertTrue(ag.validate(bad_evidence, str(ROOT)), "风险证据不在场必须红")

        no_counter = copy.deepcopy(self.eval)
        no_counter["metrics"][0]["countermetric"] = "CM-99"
        self.assertTrue(ev.validate(no_counter, str(ROOT)), "指标挂不存在反指标必须红")

        bad_kappa = copy.deepcopy(self.eval)
        bad_kappa["inter_rater"]["min_kappa"] = 1.5
        self.assertTrue(ev.validate(bad_kappa, str(ROOT)), "kappa 阈值越界必须红")

        no_prereg = copy.deepcopy(self.eval)
        no_prereg["preregistration"]["required_fields"] = ["schema"]
        self.assertTrue(ev.validate(no_prereg, str(ROOT)), "预注册字段缺失必须红")

        bad_method = copy.deepcopy(self.eval)
        bad_method["inter_rater"]["method"] = "vibes"
        self.assertTrue(ev.validate(bad_method, str(ROOT)), "非法一致性方法必须红")


if __name__ == "__main__":
    unittest.main()
