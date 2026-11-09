"""MCP 兼容头判据（P6）：对外说 MCP，对内走 CCOS——增强字段不许破坏兼容，且必须有牙。

判据五组：
① **兼容**：顶层只允许 name/description/inputSchema；
   增强字段全在 _meta；纯 MCP 客户端既不报错也读不到扩展。
② **声明完整**：side_effect/idempotent/requires_consent/resource/outputSchema/evidence 必填且合法；
③ **有副作用必须同意**：side_effect != none 而 requires_consent=False → 拒（逃生舱无痕反例）；
④ **可下架**：清单签名验签失败 → 拒用；工具被吊销 → 拒用；
⑤ **调用留证**：每调用一条 nf-call-receipt/1，链可重放；同一调用经 MCP 与 HTTP 证据同源。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_manifest as mf  # noqa: E402

SCRIPT = (sys.executable, str(ROOT / "scripts" / "mcp_manifest.py"))
TOOLS = [
    {"name": "check_file", "description": "门禁体检",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "label_file", "description": "写标识",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}}},
    {"name": "serve_query", "description": "网络查询", "inputSchema": {"type": "object"}},
]
SEED = bytes(range(32))


class CompatibilityTest(unittest.TestCase):
    def test_build_keeps_mcp_top_level_only(self):
        manifest = mf.build(TOOLS)
        for item in manifest["tools"]:
            extra = set(item) - set(mf.TOP_LEVEL_ALLOWED) - {"_meta"}
            self.assertEqual(set(), extra)

    def test_extensions_live_in_meta(self):
        manifest = mf.build(TOOLS)
        for item in manifest["tools"]:
            ccos = item["_meta"]["ccos"]
            for field in ("side_effect", "idempotent", "requires_consent", "resource",
                          "outputSchema", "evidence"):
                self.assertIn(field, ccos)

    def test_descriptions_preserved(self):
        manifest = mf.build(TOOLS)
        self.assertEqual("门禁体检", manifest["tools"][0]["description"])

    def test_side_effect_inference(self):
        manifest = mf.build(TOOLS)
        by_name = {t["name"]: t["_meta"]["ccos"] for t in manifest["tools"]}
        self.assertEqual("local", by_name["label_file"]["side_effect"])
        self.assertEqual("network", by_name["serve_query"]["side_effect"])


class ValidateTest(unittest.TestCase):
    def test_valid_manifest(self):
        self.assertEqual([], mf.validate(mf.build(TOOLS)))

    def test_top_level_extra_field_is_rejected(self):
        manifest = mf.build(TOOLS)
        manifest["tools"][0]["side_effect"] = "none"
        issues = mf.validate(manifest)
        self.assertTrue(any("顶层出现非 MCP 字段" in i for i in issues))

    def test_side_effect_without_consent_is_rejected(self):
        manifest = mf.build(TOOLS)
        manifest["tools"][1]["_meta"]["ccos"]["requires_consent"] = False
        issues = mf.validate(manifest)
        self.assertTrue(any("有副作用却不需要同意" in i for i in issues))

    def test_missing_output_schema_is_rejected(self):
        manifest = mf.build(TOOLS)
        manifest["tools"][0]["_meta"]["ccos"].pop("outputSchema")
        self.assertTrue(any("outputSchema" in i for i in mf.validate(manifest)))

    def test_deprecated_without_replacement_is_rejected(self):
        manifest = mf.build(TOOLS)
        manifest["tools"][0]["_meta"]["ccos"]["deprecated_at"] = "2026-01-01"
        self.assertTrue(any("replacement" in i for i in mf.validate(manifest)))

    def test_bad_side_effect_value_is_rejected(self):
        manifest = mf.build(TOOLS)
        manifest["tools"][0]["_meta"]["ccos"]["side_effect"] = "maybe"
        self.assertTrue(any("side_effect 非法" in i for i in mf.validate(manifest)))


class SignatureTest(unittest.TestCase):
    def test_sign_and_verify(self):
        manifest = mf.build(TOOLS)
        envelope = mf.sign(manifest, SEED)
        self.assertTrue(mf.verify_signature(manifest, envelope)["ok"])

    def test_tampered_manifest_fails(self):
        manifest = mf.build(TOOLS)
        envelope = mf.sign(manifest, SEED)
        manifest["tools"][0]["description"] = "改过的描述"
        self.assertFalse(mf.verify_signature(manifest, envelope)["ok"])

    def test_revoked_tool_is_blocked(self):
        manifest = mf.build(TOOLS)
        envelope = mf.sign(manifest, SEED)
        res = mf.verify_signature(manifest, envelope, ["check_file"], "check_file")
        self.assertFalse(res["ok"])
        self.assertTrue(any("吊销" in i for i in res["issues"]))

    def test_wrong_seed_fails_against_pinned_root(self):
        """只验「签名自洽」没用——换种子重签一样能过；必须钉根才算来源可信。"""
        manifest = mf.build(TOOLS)
        envelope = mf.sign(manifest, SEED)
        other = mf.sign(manifest, bytes(range(1, 33)))
        forged = dict(envelope, pubkey=other["pubkey"], signature=other["signature"])
        self.assertTrue(mf.verify_signature(manifest, forged)["ok"], "未钉根时只证明自洽")
        self.assertFalse(mf.verify_signature(manifest, forged,
                                             expected_pubkey=envelope["pubkey"])["ok"])

    def test_correct_seed_passes_with_pinned_root(self):
        manifest = mf.build(TOOLS)
        envelope = mf.sign(manifest, SEED)
        self.assertTrue(mf.verify_signature(manifest, envelope,
                                            expected_pubkey=envelope["pubkey"])["ok"])


class ReceiptTest(unittest.TestCase):
    def test_receipt_chain_replays(self):
        first = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        second = mf.receipt("label_file", {"path": "a"}, {"label": "ok"},
                            prev=first["digest"])
        self.assertTrue(mf.replay_receipts([first, second])["ok"])

    def test_tampered_receipt_is_caught(self):
        first = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        first["verdict"] = "fail"
        self.assertFalse(mf.replay_receipts([first])["ok"])

    def test_broken_chain_is_caught(self):
        first = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        second = mf.receipt("label_file", {"path": "a"}, {"label": "ok"})
        self.assertFalse(mf.replay_receipts([first, second])["ok"])

    def test_same_call_across_adapters(self):
        mcp = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        http = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        self.assertTrue(mf.same_call_evidence(mcp, http))

    def test_different_args_are_not_same_evidence(self):
        a = mf.receipt("check_file", {"path": "a"}, {"verdict": "pass"})
        b = mf.receipt("check_file", {"path": "b"}, {"verdict": "pass"})
        self.assertFalse(mf.same_call_evidence(a, b))


class ScriptTest(unittest.TestCase):
    def test_report_is_reproducible(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "mcp_manifest.py"),
                               "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"], report["checks"])
        self.assertTrue(report["checks"]["revoked_blocked"])
        self.assertTrue(report["checks"]["same_call_evidence"])




class RealToolSurfaceTest(unittest.TestCase):
    """D-04：清单必须派生自**真实** MCP 工具面，而不是手写示例。"""

    def test_real_tool_defs_importable(self):
        from core import mcp_runtime
        defs = list(mcp_runtime.TOOL_DEFS)
        self.assertGreaterEqual(len(defs), 8)
        for item in defs:
            for field in ("name", "description", "inputSchema"):
                self.assertIn(field, item, item.get("name"))

    def test_annotations_drive_side_effect(self):
        """真工具自带 annotations：readOnlyHint → side_effect=none、不需要同意。"""
        from core import mcp_runtime
        manifest = mf.build(list(mcp_runtime.TOOL_DEFS))
        self.assertEqual([], mf.validate(manifest))
        for item in manifest["tools"]:
            ccos = item["_meta"]["ccos"]
            self.assertEqual("none", ccos["side_effect"], item["name"])
            self.assertFalse(ccos["requires_consent"], item["name"])

    def test_readonly_annotation_beats_name_inference(self):
        """库内前缀推断会把 library_read 当成 local；annotations 必须压过推断。"""
        tool = {"name": "library_read", "description": "读库",
                "inputSchema": {"type": "object"},
                "annotations": {"readOnlyHint": True, "idempotentHint": True}}
        manifest = mf.build([tool])
        ccos = manifest["tools"][0]["_meta"]["ccos"]
        self.assertEqual("none", ccos["side_effect"])
        self.assertFalse(ccos["requires_consent"])
        self.assertTrue(ccos["idempotent"])

    def test_destructive_annotation_requires_consent(self):
        tool = {"name": "write_thing", "description": "写",
                "inputSchema": {"type": "object"},
                "annotations": {"destructiveHint": True}}
        ccos = mf.build([tool])["tools"][0]["_meta"]["ccos"]
        self.assertEqual("local", ccos["side_effect"])
        self.assertTrue(ccos["requires_consent"])

    def test_output_schema_is_carried_over(self):
        from core import mcp_runtime
        manifest = mf.build(list(mcp_runtime.TOOL_DEFS))
        carried = [t for t in manifest["tools"]
                   if t["_meta"]["ccos"]["outputSchema"] is not None]
        self.assertEqual(len(manifest["tools"]), len(carried))

    def test_script_reports_real_source(self):
        proc = subprocess.run([*SCRIPT, "--json"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        report = json.loads(proc.stdout)
        self.assertEqual("mcp_runtime.TOOL_DEFS", report["tool_source"])
        self.assertTrue(report["checks"]["tool_source_is_real"])


if __name__ == "__main__":
    unittest.main()
