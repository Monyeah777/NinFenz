#!/usr/bin/env python3
"""运维/事件/BCP/供应商契约（NF-Final WP-0D，P0 盲区 BL-03/BL-04）。

真源 = `protocol/ops.json`（`nf-ops/1`）+ `protocol/vendors.json`（`nf-vendors/1`）；
人读面 = `docs/security/INCIDENT_RESPONSE.md` · `docs/sre/{SRE,BCP_DR}.md` ·
`docs/legal/VENDORS.md`（+ `SECURITY.md` 第七节入口）；机器演练报告 = `results/ops/drills.json`。
判据：
1. 登记：S0–S3 分级齐备、runbook 步骤/证据在场、披露口径逻辑有序、SLO/BCP 场景/演练清单结构完整；
2. 供应商：kind/criticality/status 词表；used_by/attestation 路径在场；critical/high 必须有
   attestation；退出计划有 fallback/步骤/owner；不得声明处理用户数据；
3. 演练可执行且**非空洞**：桌面演练按严重度确定性映射；恢复演练做「备份→篡改→检出→恢复→再验」
   闭环（并独立证明篡改必红）；披露演练验通道与窗口；供应商退出就绪静态检查；
4. 报告：在盘 `results/ops/drills.json` == 实时重算（手改/少跑即红）；
5. 文档：id 与真源逐条对应；SECURITY.md 有入口；新文档禁用词只在否定语境；
6. 变异自证：删 runbook 步/删分级/删演练类/退出计划缺兜底/关键供应商缺 attestation/
   声明处理用户数据/used_by 不在场，判据都必须红。
"""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ops  # noqa: E402
from core.trust import bundle as tb  # noqa: E402

OPS = ROOT / "protocol" / "ops.json"
VENDORS = ROOT / "protocol" / "vendors.json"
REPORT = ROOT / "results" / "ops" / "drills.json"
DOCS = {
    "IR": ROOT / "docs" / "security" / "INCIDENT_RESPONSE.md",
    "SRE": ROOT / "docs" / "sre" / "SRE.md",
    "BCP": ROOT / "docs" / "sre" / "BCP_DR.md",
    "VENDORS": ROOT / "docs" / "legal" / "VENDORS.md",
}
SECURITY = ROOT / "SECURITY.md"
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class OpsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ops = _json(OPS)
        cls.vendors = _json(VENDORS)
        cls.report = _json(REPORT)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}
        cls.security = _text(SECURITY)

    def test_registries_valid(self):
        self.assertEqual([], ops.validate_ops(self.ops, str(ROOT)))
        self.assertEqual([], ops.validate_vendors(self.vendors, str(ROOT)))

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        steps = (self.ops.get("incident_runbook") or {}).get("steps") or []
        for step in steps:
            self.assertIn(step["id"], self.texts["IR"], "runbook 步骤未入文档：%s" % step["id"])
        for sev in ops.SEVERITIES:
            self.assertIn(sev, self.texts["IR"], "分级未入文档：%s" % sev)
        for item in self.ops.get("slo") or []:
            self.assertIn(item["id"], self.texts["SRE"], "SLO 未入文档：%s" % item["id"])
        bcp = self.ops.get("bcp") or {}
        for asset in bcp.get("assets") or []:
            self.assertIn(asset["id"], self.texts["BCP"], "BCP 资产未入文档：%s" % asset["id"])
        for scen in bcp.get("scenarios") or []:
            self.assertIn(scen["id"], self.texts["BCP"], "BCP 场景未入文档：%s" % scen["id"])
        for ven in self.vendors.get("vendors") or []:
            self.assertIn(ven["id"], self.texts["VENDORS"], "vendor 未入文档：%s" % ven["id"])
        for marker in ("INCIDENT_RESPONSE.md", "BCP_DR.md", "VENDORS.md", "ops_drill.py"):
            self.assertIn(marker, self.security, "SECURITY.md 缺入口：" + marker)

    def test_no_overclaim_in_new_docs(self):
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))

    def test_report_committed_and_complete(self):
        self.assertEqual([], ops.check_committed(str(ROOT)))
        kinds = {d.get("kind") for d in self.report.get("drills") or []}
        self.assertEqual(set(ops.DR_KINDS), kinds, "演练必须覆盖四类")
        counts = self.report.get("counts") or {}
        self.assertEqual(4, counts.get("severities"))
        self.assertEqual(len(self.vendors.get("vendors") or []), counts.get("vendors"))

    def test_tabletop_mapping_is_deterministic(self):
        s0 = ops.tabletop(self.ops, "S0")
        self.assertTrue(all(r["status"] == "required" for r in s0["steps"]))
        self.assertTrue(s0["disclosure_required"])
        s3 = ops.tabletop(self.ops, "S3")
        skipped = {r["id"] for r in s3["steps"] if r["status"] == "skipped"}
        self.assertEqual({"IR-03", "IR-06"}, skipped)
        self.assertFalse(s3["disclosure_required"])
        with self.assertRaises(ValueError):
            ops.tabletop(self.ops, "S9")

    def test_recovery_drill_restores_and_tamper_proof(self):
        drill = ops.recovery_drill()
        self.assertEqual("pass", drill["status"])
        self.assertEqual(["备份", "篡改被检出", "从备份恢复后可验"],
                         [s["name"] for s in drill["steps"]])
        # 独立证明「篡改必被检出」——不是演练自说自话
        claims = [{"id": "C-001", "type": "evidence", "subject_digest": "b" * 64,
                   "payload_digest": "c" * 64}]
        good = tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", claims)
        self.assertTrue(tb.verify_bundle(good)["ok"])
        bad = copy.deepcopy(good)
        bad["claims"][0]["payload_digest"] = "f" * 64
        self.assertFalse(tb.verify_bundle(bad)["ok"], "篡改必须被检出")

    def test_disclosure_drill(self):
        for sev in ("S0", "S1"):
            drill = ops.disclosure_drill(self.ops, sev)
            self.assertEqual("pass", drill["status"], sev)
            self.assertTrue(drill["private_channel"])
            self.assertLessEqual(drill["ack_days"], drill["disclose_days"])

    def test_vendor_readiness(self):
        drill = ops.vendor_readiness(self.vendors, str(ROOT))
        self.assertEqual("pass", drill["status"])
        self.assertEqual(len(self.vendors.get("vendors") or []), len(drill["vendors"]))
        for row in drill["vendors"]:
            self.assertEqual("pass", row["status"], row)

    def test_registry_mutations_red(self):
        no_step = copy.deepcopy(self.ops)
        no_step["incident_runbook"]["steps"] = [
            s for s in no_step["incident_runbook"]["steps"] if s["id"] != "IR-04"]
        self.assertTrue(any("IR-04" in i or "evidence" in i
                            for i in ops.validate_ops(no_step)), "删 runbook 步必须红")

        bad_sev = copy.deepcopy(self.ops)
        bad_sev["severity_vocabulary"].pop("S3")
        self.assertTrue(ops.validate_ops(bad_sev), "缺分级必须红")

        no_kind = copy.deepcopy(self.ops)
        no_kind["drills"] = [d for d in no_kind["drills"] if d["kind"] != "recovery"]
        self.assertTrue(any("drills" in i for i in ops.validate_ops(no_kind)),
                        "删演练类必须红")

        no_fallback = copy.deepcopy(self.vendors)
        next(v for v in no_fallback["vendors"] if v["id"] == "V-04")["exit_plan"]["fallback"] = ""
        self.assertTrue(ops.validate_vendors(no_fallback, str(ROOT)), "缺兜底必须红")

        weak_attest = copy.deepcopy(self.vendors)
        next(v for v in weak_attest["vendors"] if v["id"] == "V-05")["attestation"] = []
        self.assertTrue(ops.validate_vendors(weak_attest, str(ROOT)),
                        "critical/high 缺 attestation 必须红")

        user_data = copy.deepcopy(self.vendors)
        user_data["vendors"][0]["data_terms"]["stores_user_data"] = True
        self.assertTrue(ops.validate_vendors(user_data, str(ROOT)),
                        "声明处理用户数据必须红")

        missing_used_by = copy.deepcopy(self.vendors)
        missing_used_by["vendors"][0]["used_by"] = ["desktop/src/core/nonexistent_zzz.py"]
        self.assertTrue(ops.validate_vendors(missing_used_by, str(ROOT)),
                        "used_by 不在场必须红")

    def test_report_drift_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / ops.REPORT_REL
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("{\"schema\": \"nf-ops-drills/1\"}\n", encoding="utf-8")
            self.assertTrue(ops.check_committed(tmp), "报告漂移/缺真源必须红")


if __name__ == "__main__":
    unittest.main()
