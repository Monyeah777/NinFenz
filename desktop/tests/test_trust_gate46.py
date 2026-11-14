#!/usr/bin/env python3
"""check46 判据自身判据：真仓全绿 + 变异必红（证明 G2 组合门禁不是同义反复）。

check46 = DSSE + issuer registry + 链头签名 + 锚 的组合判定。本件在**代码层**做变异：
把「摘要绑定」「生命周期 fail-closed」「T4 不许声称」「组合等级」逐个打断，scan 必须红；
另用临时仓验证「冻结 schema 缺失」也会红。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import gate_g2  # noqa: E402


class RealRepoTest(unittest.TestCase):
    def test_clean_and_deterministic(self):
        first = gate_g2.scan(str(ROOT))
        self.assertEqual([], first[0], first[0])
        stats = first[1]
        self.assertEqual(5, stats["schemas"])
        self.assertEqual(1, stats["signature_verified"])
        self.assertEqual("T1", stats["achieved"])
        self.assertEqual(first, gate_g2.scan(str(ROOT)))


class MutationRedTest(unittest.TestCase):
    def test_weak_signature_binding_is_caught(self):
        with mock.patch.object(gate_g2.tsig, "verify_head",
                               lambda *a, **k: {"ok": True}):
            issues, _stats = gate_g2.scan(str(ROOT))
        self.assertTrue(any("错摘要" in i or "吊销" in i for i in issues), issues)

    def test_weak_registry_lifecycle_is_caught(self):
        def fake_verify(*a, **k):
            return {"ok": True, "subject_kind": "bundle", "subject_digest": "d" * 64,
                    "signers": [gate_g2.KEYID], "issuers": {gate_g2.KEYID: gate_g2.ISSUER}}
        with mock.patch.object(gate_g2.tsig, "verify_head", fake_verify):
            issues, _stats = gate_g2.scan(str(ROOT))
        self.assertTrue(any("吊销 key" in i for i in issues), issues)

    def test_t4_public_anchor_claim_is_caught(self):
        real = gate_g2.ta.verify_anchor_set

        def fake(*a, **k):
            result = real(*a, **k)
            result["facts"]["public_anchor"] = "ok"
            return result

        with mock.patch.object(gate_g2.ta, "verify_anchor_set", fake):
            issues, _stats = gate_g2.scan(str(ROOT))
        self.assertTrue(any("T4" in i for i in issues), issues)

    def test_anchor_target_binding_is_caught(self):
        def fake(*a, **k):
            return {"facts": {"time_token": "none", "transparency_sth": "none",
                              "public_anchor": "none"},
                    "details": [{"kind": "git-commit", "status": "ok"}], "issues": []}

        with mock.patch.object(gate_g2.ta, "verify_anchor_set", fake):
            issues, _stats = gate_g2.scan(str(ROOT))
        self.assertTrue(any("错 target" in i for i in issues), issues)

    def test_composition_levels_are_caught(self):
        def fake(*a, **k):
            return {"exit_code": 0, "report": {"level": {"achieved": "T1"}, "issues": []},
                    "decision": {}}

        with mock.patch.object(gate_g2.tv, "verify", fake):
            issues, _stats = gate_g2.scan(str(ROOT))
        self.assertTrue(any("吊销 registry" in i for i in issues), issues)


class MissingSchemaTest(unittest.TestCase):
    def test_missing_chain_head_schema_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "protocol" / "trust").mkdir(parents=True)
            for schema in (ROOT / "protocol" / "trust").glob("*.schema.json"):
                shutil.copy2(schema, base / "protocol" / "trust" / schema.name)
            (base / "protocol/trust/chain-head.schema.json").unlink()
            issues, _stats = gate_g2.scan(str(base))
            self.assertTrue(any("冻结 schema 不全" in i or "缺" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
