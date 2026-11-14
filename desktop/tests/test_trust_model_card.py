#!/usr/bin/env python3
"""trust.model_card 判据：模型卡 pinned 语义 + AI 证据绑定 + 模型替换/评测变更失效。

主判据（claim #19）：
1. 卡必须 pinned 为真（pre_registered / score_forbidden 必须 true），不能只靠 schema const；
2. AI 证据必须引用卡且摘要一致（CARD-REF-MISSING / CARD-REF-MISMATCH）；
3. 当前卡模型摘要变 → MODEL-REPLACED；同模型评测协议变 → EVAL-PROTOCOL-CHANGED；
   同模型同协议仅元数据变化 → 仍有效 + CARD-REISSUED 警告（不把重发卡当换模型）。
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import canonical as tc  # noqa: E402
from core.trust import model_card as tmc  # noqa: E402


def _card(model_digest="a" * 64, protocol_digest="c" * 64, **overrides):
    card = {"schema": "nf-model-card/1", "model_id": "nf-reasoner-7b",
            "model_digest": model_digest, "provider": "NF Lab",
            "prompt_context_digest": "b" * 64,
            "eval_protocol": {"protocol_id": "eval-v1",
                              "protocol_digest": protocol_digest,
                              "pre_registered": True, "score_forbidden": True},
            "issued_at": "2026-11-14T00:00:00Z"}
    card.update(overrides)
    return card


def _evidence(card, type_id="ai-evidence", refs=None):
    entity = {"schema": "nf-entity/1", "type": type_id,
              "subject": {"kind": "claim", "ref": "ai-1", "digest": "d" * 64},
              "issuer": "nf:test:issuer", "issued_at": "2026-11-14T00:00:00Z",
              "payload_digest": "e" * 64}
    if refs is None:
        refs = [{"kind": "card", "digest": tmc.card_digest(card)}]
    if refs:
        entity["refs"] = refs
    return entity


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tmc.load_schema(str(ROOT))

    def test_valid_card_and_digest(self):
        card = _card()
        self.assertEqual([], tmc.validate_card(card, self.schema))
        self.assertEqual(tc.digest_of(card), tmc.card_digest(card))
        self.assertEqual(tmc.card_digest(card), tmc.card_digest(copy.deepcopy(card)))

    def test_pinned_semantics(self):
        card = _card()
        card["eval_protocol"]["pre_registered"] = False
        self.assertTrue(any("pre_registered" in i for i in tmc.validate_card(card, self.schema)))
        card = _card()
        card["eval_protocol"]["score_forbidden"] = False
        self.assertTrue(any("score_forbidden" in i for i in tmc.validate_card(card, self.schema)))

    def test_structural_rejections(self):
        card = _card()
        card["model_digest"] = "ABC"
        self.assertTrue(tmc.validate_card(card, self.schema))
        card = _card()
        card["unexpected"] = 1
        self.assertTrue(tmc.validate_card(card, self.schema))
        card = _card()
        card.pop("eval_protocol")
        self.assertTrue(tmc.validate_card(card, self.schema))

    def test_mutation_shows_pinned_check_is_needed(self):
        """弱化 schema 的 const 后，语义检查仍必须拦住 false（证明不是只靠 schema）。"""
        weakened = json.loads(json.dumps(self.schema))
        weakened["properties"]["eval_protocol"]["properties"]["pre_registered"].pop("const")
        card = _card()
        card["eval_protocol"]["pre_registered"] = False
        self.assertEqual([], __import__("core.json_schema", fromlist=["x"]).json_schema_check(
            card, weakened))
        self.assertTrue(any("pre_registered" in i
                            for i in tmc.validate_card(card, weakened)))


class BindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tmc.load_schema(str(ROOT))

    def test_binding_ok(self):
        card = _card()
        result = tmc.check_binding(_evidence(card), card, schema=self.schema)
        self.assertTrue(result["ok"], result)
        self.assertEqual(tmc.card_digest(card), result["bound_digest"])
        self.assertNotIn("warning", result)

    def test_type_and_refs(self):
        card = _card()
        self.assertEqual("TYPE-MISMATCH",
                         tmc.check_binding(_evidence(card, type_id="claim"), card,
                                           schema=self.schema)["reason"])
        self.assertEqual("CARD-REF-MISSING",
                         tmc.check_binding(_evidence(card, refs=[]), card,
                                           schema=self.schema)["reason"])
        wrong = [{"kind": "card", "digest": "f" * 64}]
        self.assertEqual("CARD-REF-MISMATCH",
                         tmc.check_binding(_evidence(card, refs=wrong), card,
                                           schema=self.schema)["reason"])

    def test_invalid_cards(self):
        card = _card()
        bad = _card()
        bad["eval_protocol"]["score_forbidden"] = False
        self.assertEqual("CARD-INVALID",
                         tmc.check_binding(_evidence(card), bad, schema=self.schema)["reason"])
        self.assertEqual("CURRENT-CARD-INVALID",
                         tmc.check_binding(_evidence(card), card, bad,
                                           schema=self.schema)["reason"])

    def test_model_replaced(self):
        bound = _card()
        current = _card(model_digest="f" * 64)
        result = tmc.check_binding(_evidence(bound), bound, current, schema=self.schema)
        self.assertFalse(result["ok"])
        self.assertEqual("MODEL-REPLACED", result["reason"])

    def test_eval_protocol_changed(self):
        bound = _card()
        current = _card(protocol_digest="9" * 64)
        result = tmc.check_binding(_evidence(bound), bound, current, schema=self.schema)
        self.assertEqual("EVAL-PROTOCOL-CHANGED", result["reason"])

    def test_card_reissued_same_model_and_protocol(self):
        bound = _card()
        current = _card(notes="reissued with metadata update")
        result = tmc.check_binding(_evidence(bound), bound, current, schema=self.schema)
        self.assertTrue(result["ok"], result)
        self.assertEqual("CARD-REISSUED", result["warning"])

    def test_cli_binding(self):
        bound = _card()
        current = _card(model_digest="f" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {"evidence.json": _evidence(bound), "bound.json": bound,
                     "current.json": current}
            for name, doc in files.items():
                (base / name).write_text(json.dumps(doc), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                   "--ai-evidence", str(base / "evidence.json"),
                   "--model-card", str(base / "bound.json"), "--root", str(ROOT)]
            ok = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            self.assertIn("valid model-card binding", ok.stdout)
            bad = subprocess.run(cmd + ["--current-card", str(base / "current.json")],
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("MODEL-REPLACED", bad.stdout)


if __name__ == "__main__":
    unittest.main()
