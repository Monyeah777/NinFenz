#!/usr/bin/env python3
"""trust.context_lineage 判据：prompt/context 血缘链 + 三方绑定（claim #34 / FR-A4-04）。

主判据：上下文替换、前缀篡改、段重排、跨会话复用必须可检测；AI 证据必须同时绑定
模型卡摘要与血缘摘要；只存摘要不存原文。
"""
import base64
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import context_lineage as tcl  # noqa: E402
from core.trust import model_card as tmc  # noqa: E402

CARD_DIGEST = "a" * 64


def _card(prompt_digest=""):
    card = {"schema": "nf-model-card/1", "model_id": "nf-reasoner-7b",
            "model_digest": "a" * 64, "provider": "NF Lab",
            "eval_protocol": {"protocol_id": "eval-v1", "protocol_digest": "c" * 64,
                              "pre_registered": True, "score_forbidden": True},
            "issued_at": "2026-11-14T00:00:00Z"}
    if prompt_digest:
        card["prompt_context_digest"] = prompt_digest
    return card


def _lineage(card_digest=CARD_DIGEST, contents=None):
    return tcl.build_lineage(card_digest, contents or [
        ("system", b"You are NF."), ("user", b"Prove it."), ("assistant", b"Done.")])


def _evidence(card, lineage, refs=None):
    if refs is None:
        refs = [{"kind": "card", "digest": tmc.card_digest(card)},
                {"kind": "context", "digest": lineage["lineage_digest"]}]
    entity = {"schema": "nf-entity/1", "type": "ai-evidence",
              "subject": {"kind": "claim", "ref": "ai-1", "digest": "d" * 64},
              "issuer": "nf:test:issuer", "issued_at": "2026-11-14T00:00:00Z",
              "payload_digest": "e" * 64}
    if refs:
        entity["refs"] = refs
    return entity


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tcl.load_schema(str(ROOT))

    def test_build_and_determinism(self):
        first = _lineage()
        self.assertEqual(first, _lineage())
        self.assertEqual(3, len(first["segments"]))
        self.assertEqual(tcl.ZERO_DIGEST, first["segments"][0]["prev"])
        self.assertEqual(first["segments"][-1]["digest"], first["head"])
        self.assertEqual([], tcl.verify_lineage(first, schema=self.schema)["issues"])

    def test_build_rejections(self):
        with self.assertRaises(ValueError):
            tcl.build_lineage(CARD_DIGEST, [])
        with self.assertRaises(ValueError):
            tcl.build_lineage(CARD_DIGEST, [("admin", b"x")])
        with self.assertRaises(ValueError):
            tcl.build_lineage("ABC", [("system", b"x")])


class VerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tcl.load_schema(str(ROOT))

    def verify(self, lineage, card=None):
        return tcl.verify_lineage(lineage, card, schema=self.schema)

    def test_content_swap_is_detected(self):
        original = _lineage()
        swapped = _lineage(contents=[("system", b"You are NF."),
                                     ("user", b"Other."),
                                     ("assistant", b"Done.")])
        self.assertNotEqual(original["lineage_digest"], swapped["lineage_digest"])
        self.assertNotEqual(original["head"], swapped["head"])

    def test_prefix_tamper_detected(self):
        doc = copy.deepcopy(_lineage())
        doc["segments"][0]["content_digest"] = "f" * 64
        result = self.verify(doc)
        self.assertFalse(result["ok"])
        self.assertIn("digest", result["issues"][0]["message"])

    def test_reorder_detected(self):
        doc = copy.deepcopy(_lineage())
        doc["segments"][0], doc["segments"][1] = doc["segments"][1], doc["segments"][0]
        self.assertFalse(self.verify(doc)["ok"])

    def test_seq_and_head_and_digest_bindings(self):
        doc = copy.deepcopy(_lineage())
        doc["segments"][1]["seq"] = 5
        self.assertFalse(self.verify(doc)["ok"])
        doc = copy.deepcopy(_lineage())
        doc["head"] = "f" * 64
        self.assertFalse(self.verify(doc)["ok"])
        doc = copy.deepcopy(_lineage())
        doc["lineage_digest"] = "f" * 64
        self.assertFalse(self.verify(doc)["ok"])

    def test_model_card_binding(self):
        card = _card()
        lineage = _lineage(card_digest=tmc.identity_digest(card))
        card["prompt_context_digest"] = lineage["head"]
        self.assertTrue(self.verify(lineage, card)["ok"])
        other = _card()
        other["model_digest"] = "9" * 64
        self.assertEqual("MODEL-CARD-MISMATCH", self.verify(lineage, other)["issues"][0]["code"])
        mismatched_prompt = _card(prompt_digest="8" * 64)
        self.assertEqual("CONTEXT-DIGEST-MISMATCH",
                         self.verify(lineage, mismatched_prompt)["issues"][0]["code"])

    def test_cross_session_reuse_detected(self):
        lineage_a = _lineage(card_digest="a" * 64)
        lineage_b = _lineage(card_digest="b" * 64)
        self.assertNotEqual(lineage_a["lineage_digest"], lineage_b["lineage_digest"])
        card_b = _card()
        card_b["model_digest"] = "b" * 64
        self.assertEqual("MODEL-CARD-MISMATCH",
                         self.verify(lineage_a, card_b)["issues"][0]["code"])


class IdentityTest(unittest.TestCase):
    def test_identity_excludes_prompt_and_notes(self):
        card = _card()
        before = tmc.identity_digest(card)
        card["prompt_context_digest"] = "f" * 64
        card["notes"] = "metadata change"
        self.assertEqual(before, tmc.identity_digest(card))
        card["model_digest"] = "9" * 64
        self.assertNotEqual(before, tmc.identity_digest(card))


class BindingTest(unittest.TestCase):
    def test_three_way_binding(self):
        card = _card()
        lineage = _lineage(card_digest=tmc.identity_digest(card))
        card["prompt_context_digest"] = lineage["head"]
        result = tcl.check_context_binding(_evidence(card, lineage), card, lineage,
                                           root=str(ROOT))
        self.assertTrue(result["ok"], result)
        self.assertEqual(lineage["lineage_digest"], result["lineage_digest"])

    def test_missing_and_mismatched_refs(self):
        card = _card()
        lineage = _lineage(card_digest=tmc.identity_digest(card))
        card["prompt_context_digest"] = lineage["head"]
        only_card = [{"kind": "card", "digest": tmc.card_digest(card)}]
        self.assertEqual("CONTEXT-REF-MISSING",
                         tcl.check_context_binding(_evidence(card, lineage, only_card),
                                                   card, lineage)["reason"])
        wrong = [{"kind": "card", "digest": tmc.card_digest(card)},
                 {"kind": "context", "digest": "f" * 64}]
        self.assertEqual("CONTEXT-REF-MISMATCH",
                         tcl.check_context_binding(_evidence(card, lineage, wrong),
                                                   card, lineage)["reason"])
        self.assertEqual("CARD-REF-MISMATCH",
                         tcl.check_context_binding(
                             _evidence(card, lineage,
                                       [{"kind": "card", "digest": "f" * 64},
                                        {"kind": "context",
                                         "digest": lineage["lineage_digest"]}]),
                             card, lineage)["reason"])

    def test_cli_lineage_build_and_binding(self):
        card = _card()
        contexts = [{"role": "system", "content_b64": base64.b64encode(b"You are NF.").decode()},
                    {"role": "user", "content_b64": base64.b64encode(b"Prove it.").decode()},
                    {"role": "assistant",
                     "content_b64": base64.b64encode(b"Done.").decode()}]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "card.json").write_text(json.dumps(card), encoding="utf-8")
            (base / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
            build = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--lineage-build", str(base / "lineage.json"),
                 "--model-card", str(base / "card.json"),
                 "--contexts", str(base / "contexts.json")],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            built = tcl.load_lineage(str(base / "lineage.json"))
            self.assertTrue(tcl.verify_lineage(built)["ok"])
            evidence = _evidence(card, built,
                                 [{"kind": "card", "digest": tmc.card_digest(card)},
                                  {"kind": "context", "digest": built["lineage_digest"]}])
            (base / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            ok = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--ai-evidence", str(base / "evidence.json"),
                 "--model-card", str(base / "card.json"),
                 "--context-lineage", str(base / "lineage.json"),
                 "--root", str(ROOT)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            self.assertIn("context-lineage", ok.stdout)
            tampered = copy.deepcopy(built)
            tampered["segments"][0]["content_digest"] = "f" * 64
            (base / "lineage.json").write_text(json.dumps(tampered), encoding="utf-8")
            bad = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--ai-evidence", str(base / "evidence.json"),
                 "--model-card", str(base / "card.json"),
                 "--context-lineage", str(base / "lineage.json"),
                 "--root", str(ROOT)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("LINEAGE-INVALID", bad.stdout)


if __name__ == "__main__":
    unittest.main()
