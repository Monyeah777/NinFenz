"""方法包判据：领域专业性必须是**可校验的数据**，不是文档里的形容词。

判据盯五件事：
① 包形状（id/version/domain、expert_moves 必需字段、evidence_standards 必填）；
② 可执行（每个 maps_to 必须指向仓内**真实存在**的原子/算子/move id）；
③ 组合（并集去重、序稳定、不评分）；
④ 诚实（未知包/坏包 fail-closed 并给修复指引）；
⑤ 接线（研究计划确实带上了领域块，且 CLI 可列）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cognition_plan, method_pack  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
PACK_IDS = ("watermarking", "evidence-audit", "metacognition",
            "evaluation-design", "prompt-injection-defense")


class PackShapeTest(unittest.TestCase):
    def test_index_lists_registered_packs(self):
        packs = method_pack.list_packs(str(ROOT))
        self.assertEqual(set(PACK_IDS), {p["id"] for p in packs})

    def test_every_registered_pack_validates(self):
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            self.assertEqual([], method_pack.validate_pack(pack), pid)

    def test_pack_requires_core_fields(self):
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [{"id": "X1", "name": "n", "why": "w",
                                 "maps_to": ["k.partition"]}]}
        issues = method_pack.validate_pack(bad)
        self.assertTrue(any("evidence_standards" in i for i in issues), issues)
        self.assertTrue(any("common_failures" in i for i in issues), issues)

    def test_unknown_maps_to_is_rejected(self):
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [{"id": "X1", "name": "n", "why": "w",
                                 "maps_to": ["no.such.atom"]}],
               "evidence_standards": [{"claim_kind": "k", "required": ["r"]}],
               "common_failures": ["f"]}
        self.assertTrue(any("未知动作" in i for i in method_pack.validate_pack(bad)))

    def test_duplicate_move_id_is_rejected(self):
        mv = {"id": "X1", "name": "n", "why": "w", "maps_to": ["k.partition"]}
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [mv, dict(mv)],
               "evidence_standards": [{"claim_kind": "k", "required": ["r"]}],
               "common_failures": ["f"]}
        self.assertTrue(any("重复" in i for i in method_pack.validate_pack(bad)))


class PackContentTest(unittest.TestCase):
    def test_watermarking_pack_covers_attack_surface(self):
        pack = method_pack.load_pack(str(ROOT), "watermarking")
        names = " ".join(m["name"] for m in pack["expert_moves"])
        self.assertIn("攻击面", names)
        self.assertIn("同步", names)
        std = method_pack.obligations(pack, "robustness")
        self.assertTrue(any("BER" in r for r in std["standards"][0]["required"]))

    def test_evidence_audit_pack_contains_claim_card(self):
        pack = method_pack.load_pack(str(ROOT), "evidence-audit")
        names = " ".join(m["name"] for m in pack["expert_moves"])
        self.assertIn("立卡", names)
        std = method_pack.obligations(pack, "closure")
        self.assertTrue(any("Claim Card" in r for r in std["standards"][0]["required"]))

    def test_evaluation_design_pack_has_pre_registration_and_controls(self):
        pack = method_pack.load_pack(str(ROOT), "evaluation-design")
        ids = {m["id"] for m in pack["expert_moves"]}
        for need in ("ev.pre_register", "ev.blind_partition", "ev.negative_control",
                     "ev.synthetic_guard", "ev.cost_accounting"):
            self.assertIn(need, ids, "评测设计包缺关键动作：" + need)
        kinds = {st["claim_kind"] for st in pack["evidence_standards"]}
        self.assertEqual({"efficacy", "cost", "reliability"}, kinds)
        self.assertTrue(any("合成" in f for f in pack["common_failures"]))

    def test_prompt_injection_pack_has_plane_separation_and_receipts(self):
        pack = method_pack.load_pack(str(ROOT), "prompt-injection-defense")
        ids = {m["id"] for m in pack["expert_moves"]}
        for need in ("pi.plane_separation", "pi.allowlist_surface", "pi.consent_gate",
                     "pi.receipt_audit", "pi.redteam_cases"):
            self.assertIn(need, ids, "注入防御包缺关键动作：" + need)
        kinds = {st["claim_kind"] for st in pack["evidence_standards"]}
        self.assertEqual({"defense-efficacy", "audit-trail", "least-privilege"}, kinds)
        # 例子里必须点名真实接线件，不能只说概念
        text = " ".join(str(x.get("case") or "") for x in pack["examples"])
        self.assertIn("mcp_ingress", text)


    def test_prompt_injection_moves_have_real_code_anchors(self):
        """包里的动作不能只是文字：每个 pi.* 动作都要在真实代码里有锚点。

        映射（动作 → 代码锚点）写死在本判据里，改了实现就得同步改这里——
        这样「包说我们做了平面分离/白名单/同意门/回执」就不是自述，而是可核。
        """
        anchors = {
            "pi.allowlist_surface": ("desktop/src/core/mcp_ingress.py", ("allow_tools", "deny")),
            "pi.consent_gate": ("desktop/src/core/mcp_ingress.py", ("consent",)),
            "pi.receipt_audit": ("desktop/src/core/mcp_ingress.py", ("record_call", "receipt")),
            "pi.least_privilege": ("desktop/src/core/mcp_ingress.py", ("max_args_bytes",)),
            # 输出/参数侧 schema 复核在运行时（schema_check 注入点），不在 ingress 本身
            "pi.output_side_check": ("desktop/src/core/mcp_runtime.py", ("schema_check",)),
        }
        pack = method_pack.load_pack(str(ROOT), "prompt-injection-defense")
        ids = {m["id"] for m in pack["expert_moves"]}
        for move_id, (rel, tokens) in anchors.items():
            self.assertIn(move_id, ids, "包缺动作：" + move_id)
            text = (ROOT / rel).read_text(encoding="utf-8")
            hit = [t for t in tokens if t in text]
            self.assertTrue(hit, "动作 " + move_id + " 在 " + rel + " 里没有锚点（"
                            + "/".join(tokens) + "）")

    def test_metacognition_pack_has_calibration_standard(self):
        pack = method_pack.load_pack(str(ROOT), "metacognition")
        std = method_pack.obligations(pack, "calibration")
        self.assertTrue(any("基线" in r for r in std["standards"][0]["required"]))

    def test_unknown_claim_kind_is_rejected_with_guide(self):
        pack = method_pack.load_pack(str(ROOT), "watermarking")
        with self.assertRaises(ValueError) as ctx:
            method_pack.obligations(pack, "no-such-kind")
        self.assertIn("修复指引", str(ctx.exception))


class ComposeTest(unittest.TestCase):
    def test_compose_unions_and_dedupes(self):
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in ("watermarking",
                                                                  "watermarking")]
        out = method_pack.compose(packs)
        ids = [m["id"] for m in out["expert_moves"]]
        self.assertEqual(len(ids), len(set(ids)), "重复包必须去重")

    def test_compose_keeps_kind_order_stable(self):
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in ("evidence-audit",
                                                                  "watermarking")]
        a = method_pack.compose(packs)
        b = method_pack.compose(packs)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual([s["claim_kind"] for s in a["evidence_standards"]],
                         [s["claim_kind"] for s in b["evidence_standards"]])

    def test_compose_requires_packs(self):
        with self.assertRaises(ValueError):
            method_pack.compose([])

    def test_unknown_pack_id_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            method_pack.load_pack(str(ROOT), "no-such-pack")
        self.assertIn("修复指引", str(ctx.exception))


class PlanIntegrationTest(unittest.TestCase):
    def test_plan_without_packs_has_no_domain_block(self):
        doc = cognition_plan.plan("水印抗转码", 1, root=str(ROOT))
        self.assertIsNone(doc["domain"])

    def test_plan_with_pack_carries_expert_moves(self):
        doc = cognition_plan.plan("屏幕拍摄水印", 1, root=str(ROOT),
                                  pack_ids=["watermarking"])
        self.assertEqual(["watermarking"], doc["domain"]["packs"])
        self.assertGreaterEqual(len(doc["domain"]["expert_moves"]), 3)
        self.assertTrue(doc["domain"]["common_failures"])

    def test_plan_with_two_packs_composes(self):
        doc = cognition_plan.plan("证据链审计", 1, root=str(ROOT),
                                  pack_ids=["watermarking", "evidence-audit"])
        self.assertEqual(2, len(doc["domain"]["packs"]))
        kinds = {s["claim_kind"] for s in doc["domain"]["evidence_standards"]}
        self.assertIn("robustness", kinds)
        self.assertIn("closure", kinds)


class CliTest(unittest.TestCase):
    def test_packs_list(self):
        proc = subprocess.run([*NF, "cognition", "--packs-list"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        self.assertIn("watermarking", proc.stdout)

    def test_plan_with_pack_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            proc = subprocess.run([*NF, "cognition", "--plan", "屏幕拍摄水印",
                                   "--depth", "1", "--pack", "watermarking",
                                   "--out", str(out), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual(["watermarking"], doc["domain"]["packs"])
            self.assertEqual(doc, json.loads(out.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
