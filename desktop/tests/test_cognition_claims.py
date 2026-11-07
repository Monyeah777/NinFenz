"""判据注册表 + 主张编译判据（P3 剩余）。

盯四件事：
① 注册表铁律：出现聚合分键 → 拒；角色升级 → 拒；review 层必须 external-blind；witness 必填；
② 判据评估三态：缺 witness → unknown（**不是 pass**）；review 层在本仓内永远 unknown；
③ 主张编译：方法包 evidence_standards → 义务清单；未知包/未知 claim_kind/未知判据 → 拒绝并给指引；
④ 核对三态：缺项 / 未知 / 满足分列，ready 只在两者都空时为真。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.cognition_workspace import claims as cl  # noqa: E402
from core.cognition_workspace import criteria as cr  # noqa: E402
from core.method_pack import load_pack  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))


class RegistryTest(unittest.TestCase):
    def test_registry_is_valid(self):
        doc = cr.load(str(ROOT))
        self.assertEqual([], cr.validate(doc))

    def test_three_layers_present(self):
        items = cr.list_criteria(str(ROOT))
        self.assertEqual({"craft", "standard", "review"}, {item["layer"] for item in items})

    def test_aggregate_score_key_is_rejected(self):
        doc = cr.load(str(ROOT))
        doc = json.loads(json.dumps(doc))
        doc["layers"]["craft"][0]["score"] = 0.8
        self.assertTrue(any("聚合分" in i for i in cr.validate(doc)))

    def test_role_upgrade_is_rejected(self):
        doc = cr.load(str(ROOT))
        doc = json.loads(json.dumps(doc))
        doc["layers"]["craft"][0]["source_role"] = "local-trusted"
        doc["layers"]["craft"][0]["max_role"] = "external-advisory"
        self.assertTrue(any("角色升级" in i for i in cr.validate(doc)))

    def test_review_layer_must_be_external_blind(self):
        doc = cr.load(str(ROOT))
        doc = json.loads(json.dumps(doc))
        doc["layers"]["review"][0]["kind"] = "computable"
        self.assertTrue(any("external-blind" in i for i in cr.validate(doc)))

    def test_unknown_criterion_has_guide(self):
        with self.assertRaises(ValueError) as ctx:
            cr.get(str(ROOT), "craft:no-such")
        self.assertIn("修复指引", str(ctx.exception))


class EvaluateTest(unittest.TestCase):
    def test_missing_witness_is_unknown_not_pass(self):
        res = cr.evaluate(str(ROOT), "craft:coherence", {})
        self.assertEqual("unknown", res["verdict"])
        self.assertFalse(res["witness_ok"])

    def test_partial_witness_is_unknown(self):
        res = cr.evaluate(str(ROOT), "craft:coherence", {"主张原文": "x"})
        self.assertEqual("unknown", res["verdict"])

    def test_full_witness_can_pass(self):
        item = cr.get(str(ROOT), "craft:coherence")
        witness = dict.fromkeys(item["witness"], "有")
        res = cr.evaluate(str(ROOT), "craft:coherence", witness)
        self.assertEqual("pass", res["verdict"])

    def test_review_layer_never_passes_internally(self):
        item = cr.get(str(ROOT), "review:blind-review-protocol")
        witness = dict.fromkeys(item["witness"], "有")
        res = cr.evaluate(str(ROOT), "review:blind-review-protocol", witness)
        self.assertEqual("unknown", res["verdict"])


class CompileClaimTest(unittest.TestCase):
    def test_compile_uses_pack_evidence_standards(self):
        pack = load_pack(str(ROOT), "watermarking")
        expected = [need for std in pack["evidence_standards"]
                    if std["claim_kind"] == "robustness" for need in std["required"]]
        doc = cl.compile_claim(str(ROOT), "关系嵌入扛缩放", "robustness", ["watermarking"])
        got = [need for block in doc["obligations"] for std in block["standards"]
               for need in std["required"]]
        self.assertEqual(expected, got)

    def test_compile_is_deterministic(self):
        a = cl.compile_claim(str(ROOT), "c", "robustness", ["watermarking"])
        b = cl.compile_claim(str(ROOT), "c", "robustness", ["watermarking"])
        self.assertEqual(a["digest"], b["digest"])

    def test_unknown_pack_has_guide(self):
        with self.assertRaises(ValueError) as ctx:
            cl.compile_claim(str(ROOT), "c", "robustness", ["no-such-pack"])
        self.assertIn("修复指引", str(ctx.exception))

    def test_unknown_claim_kind_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cl.compile_claim(str(ROOT), "c", "no-such-kind", ["watermarking"])
        self.assertIn("修复指引", str(ctx.exception))

    def test_unknown_criterion_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cl.compile_claim(str(ROOT), "c", "robustness", ["watermarking"],
                             ["craft:nope"])
        self.assertIn("修复指引", str(ctx.exception))

    def test_role_upgrade_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cl.compile_claim(str(ROOT), "c", "robustness", ["watermarking"],
                             ["craft:falsifiability"], role="local-trusted")
        self.assertIn("角色升级", str(ctx.exception))

    def test_multi_pack_composes(self):
        doc = cl.compile_claim(str(ROOT), "c", "closure",
                               ["watermarking", "evidence-audit"])
        kinds = [std["claim_kind"] for block in doc["obligations"]
                 for std in block["standards"]]
        self.assertIn("closure", kinds)


class CheckClaimTest(unittest.TestCase):
    def _doc(self):
        return cl.compile_claim(str(ROOT), "关系嵌入扛缩放", "robustness",
                                ["watermarking"])

    def test_empty_evidence_is_not_ready(self):
        res = cl.check_claim(self._doc(), {})
        self.assertFalse(res["ready"])
        self.assertTrue(res["missing"])

    def test_full_evidence_is_ready(self):
        doc = self._doc()
        ev = {need: {"status": "ok"} for block in doc["obligations"]
              for std in block["standards"] for need in std["required"]}
        res = cl.check_claim(doc, ev)
        self.assertTrue(res["ready"], res)
        self.assertEqual([], res["missing"])
        self.assertEqual([], res["unknown"])

    def test_unknown_evidence_blocks_ready(self):
        doc = self._doc()
        ev = {need: {"status": "ok"} for block in doc["obligations"]
              for std in block["standards"] for need in std["required"]}
        first = doc["obligations"][0]["standards"][0]["required"][0]
        ev[first] = {"status": "unknown"}
        res = cl.check_claim(doc, ev)
        self.assertFalse(res["ready"])
        self.assertIn(first, res["unknown"])

    def test_bad_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            cl.check_claim({"schema": "wrong"}, {})


class CliTest(unittest.TestCase):
    def test_criteria_listing(self):
        proc = subprocess.run([*NF, "cog", "criteria", "--json"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        doc = json.loads(proc.stdout)
        self.assertEqual("cog-criteria", doc["kind"])
        self.assertGreaterEqual(len(doc["items"]), 6)

    def test_claim_compile_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            claim_path = Path(tmp) / "claim.json"
            proc = subprocess.run([*NF, "cog", "claim", "--claim", "关系嵌入扛缩放",
                                   "--kind", "robustness", "--pack", "watermarking",
                                   "--out", str(claim_path), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            claim = json.loads(proc.stdout)
            evidence = {need: {"status": "ok"} for block in claim["obligations"]
                        for std in block["standards"] for need in std["required"]}
            ev_path = Path(tmp) / "ev.json"
            ev_path.write_text(json.dumps(evidence, ensure_ascii=False), encoding="utf-8")
            check = subprocess.run([*NF, "cog", "claim-check",
                                    "--claim-file", str(claim_path),
                                    "--evidence", str(ev_path), "--json"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=180)
            self.assertEqual(0, check.returncode, check.stderr[-300:])
            self.assertTrue(json.loads(check.stdout)["ready"])


if __name__ == "__main__":
    unittest.main()
