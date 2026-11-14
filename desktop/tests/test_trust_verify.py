#!/usr/bin/env python3
"""trust.verify 判据：level 向量逐条 + nf-verify/1 报告 schema + exit 0/1/2 + CLI 契约。

为什么有它：FR-V-01 的验收是「统一验证入口输出 nf-verify/1，退出码 0/1/2」。本件把判定表钉在
冻结向量上，把报告钉在冻结 schema 上，再用子进程跑 scripts/trust_verify.py 验证真实退出码——
避免「库内对、CLI 面不对」。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core.trust import bundle as tb  # noqa: E402
from core.trust import verify as tv  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
SCRIPT = ROOT / "scripts" / "trust_verify.py"
POLICY = {
    "schema": "nf-trust-policy/1",
    "issuers": [{"id": "nf:local", "keyid": "nf:local:ed25519:2026", "alg": "ed25519",
                 "types": ["claim", "evidence"]}],
    "algorithms": ["ed25519"],
    "tsa_roots": [{"id": "tsa:freetsa", "digest": "f" * 64}],
    "required_level": "T0",
    "anchors": {"tsa": True, "transparency": False, "witness_threshold": 0},
}


def _bundle(count=4):
    claims = [{"id": f"C-{i:03d}", "type": "evidence", "subject_digest": "b" * 64,
               "payload_digest": "c" * 64} for i in range(count)]
    return tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", claims)


def _policy(level):
    return {**POLICY, "required_level": level}


def _level_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == "level"]


class LevelVectorTest(unittest.TestCase):
    def test_level_vectors(self):
        vectors = _level_vectors()
        self.assertGreaterEqual(len(vectors), 7)
        for vec in vectors:
            case = vec["input"]
            got = tv.decide(case["facts"], case["required_level"],
                            policy_ok=case.get("policy_ok", True))
            self.assertEqual(vec["expected"], got, vec["id"])

    def test_bad_required_level_fails_loudly(self):
        with self.assertRaises(ValueError) as ctx:
            tv.decide(tv.skeleton_facts(True), "T9")
        self.assertIn("修复指引", str(ctx.exception))


class VerifyScenarioTest(unittest.TestCase):
    def test_t0_policy_passes_with_report(self):
        result = tv.verify(_bundle(), _policy("T0"), root=str(ROOT))
        self.assertEqual(0, result["exit_code"])
        report = result["report"]
        self.assertEqual("nf-verify/1", report["schema"])
        self.assertEqual({"required": "T0", "achieved": "T0"}, report["level"])
        self.assertTrue(report["no_scoring"])
        self.assertEqual(["nf:local"], report["trust_roots"]["issuers"])
        self.assertEqual(["tsa:freetsa"], report["trust_roots"]["tsa"])
        self.assertEqual([], report["issues"])
        self.assertEqual([], json_schema.json_schema_check(
            report, tv.load_schema(str(ROOT))))

    def test_t2_policy_is_undecidable_with_missing_codes(self):
        result = tv.verify(_bundle(), _policy("T2"), root=str(ROOT))
        self.assertEqual(2, result["exit_code"])
        codes = [issue["code"] for issue in result["report"]["issues"]]
        self.assertIn("SIGNATURE-MISSING", codes)
        self.assertIn("ANCHOR-MISSING", codes)
        for issue in result["report"]["issues"]:
            self.assertTrue(issue["message"] and issue["fix"])

    def test_tampered_bundle_is_invalid_exit_1(self):
        bad = _bundle()
        bad["claims"][1]["payload_digest"] = "d" * 64
        result = tv.verify(bad, _policy("T0"), root=str(ROOT))
        self.assertEqual(1, result["exit_code"])
        self.assertEqual("none", result["report"]["level"]["achieved"])
        self.assertIn("BUNDLE-INVALID", [i["code"] for i in result["report"]["issues"]])

    def test_invalid_policy_is_policy_invalid_exit_2(self):
        bad = _policy("T9")
        result = tv.verify(_bundle(), bad, root=str(ROOT))
        self.assertEqual(2, result["exit_code"])
        self.assertIn("POLICY-INVALID", [i["code"] for i in result["report"]["issues"]])

    def test_report_cannot_be_built_without_required(self):
        with self.assertRaises(ValueError):
            tv.build_report("bundle", "a" * 64,
                             {"required": "T0", "achieved": "T0", "exit_code": 0,
                              "missing": []}, [], [], {})


class ScriptContractTest(unittest.TestCase):
    def _write(self, tmp, name, payload):
        path = Path(tmp) / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", check=False)

    def test_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory(prefix="nf_verify_t_") as tmp:
            bundle = self._write(tmp, "bundle.json", _bundle())
            t0 = self._write(tmp, "policy0.json", _policy("T0"))
            t2 = self._write(tmp, "policy2.json", _policy("T2"))
            ok = self._run("--bundle", str(bundle), "--policy", str(t0), "--json")
            self.assertEqual(0, ok.returncode, ok.stderr)
            self.assertEqual("nf-verify/1", json.loads(ok.stdout)["schema"])
            again = self._run("--bundle", str(bundle), "--policy", str(t0), "--json")
            self.assertEqual(ok.stdout, again.stdout)
            undecidable = self._run("--bundle", str(bundle), "--policy", str(t2))
            self.assertEqual(2, undecidable.returncode)
            self.assertIn("ANCHOR-MISSING", undecidable.stdout)

    def test_tampered_bundle_exit_1_from_cli(self):
        with tempfile.TemporaryDirectory(prefix="nf_verify_t_") as tmp:
            bad = _bundle()
            bad["claims"][0]["payload_digest"] = "e" * 64
            bundle = self._write(tmp, "bad.json", bad)
            policy = self._write(tmp, "policy.json", _policy("T0"))
            proc = self._run("--bundle", str(bundle), "--policy", str(policy), "--json")
            self.assertEqual(1, proc.returncode)
            self.assertIn("BUNDLE-INVALID", proc.stdout)

    def test_missing_input_is_undecidable_with_guidance(self):
        proc = self._run("--bundle", "/no/such/bundle.json", "--policy", "/no/such/p.json")
        self.assertEqual(2, proc.returncode)
        self.assertIn("不可判定", proc.stderr)
        self.assertIn("修复指引", proc.stderr)

    def test_out_writes_report(self):
        with tempfile.TemporaryDirectory(prefix="nf_verify_t_") as tmp:
            bundle = self._write(tmp, "bundle.json", _bundle())
            policy = self._write(tmp, "policy.json", _policy("T0"))
            out = Path(tmp) / "nf-verify.json"
            proc = self._run("--bundle", str(bundle), "--policy", str(policy),
                             "--out", str(out))
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertTrue(out.is_file())
            self.assertEqual("nf-verify/1",
                             json.loads(out.read_text(encoding="utf-8"))["schema"])


if __name__ == "__main__":
    unittest.main()
