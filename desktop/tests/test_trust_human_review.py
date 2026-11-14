#!/usr/bin/env python3
"""trust.human_review 判据：签名人类复核 + PENDING≠通过 + registry 生命周期（FR-A4-05）。

主判据：approve 才算通过；reject/escalate 是合法签名但不是批准；缺记录 = PENDING；
reviewer 必须是 human kind；签名有效但 key 吊销/过期 → INVALID（fail-closed）。
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

from core import json_schema  # noqa: E402
from core.trust import human_review as hrev  # noqa: E402

KEY = b"review-hmac-key-0123456789abcdef"
KEYID = "nf:reviewer:alice:2026"
ISSUER = "nf:reviewer:alice"
NOW = "2026-11-14T00:00:00Z"
SUBJECT = "a" * 64


def _registry(kind="human", status="active", **extra):
    key = {"keyid": KEYID, "alg": "hmac-sha256", "status": status,
           "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
    key.update(extra)
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": kind, "keys": [key]}]}


def _material():
    return {KEYID: {"hex": KEY.hex()}}


def _signer():
    from core.trust import dsse
    return [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)}]


def _statement(decision="approve", subject_kind="bundle", digest=SUBJECT):
    return hrev.build_statement(subject_kind, digest, decision, ISSUER, KEYID,
                                "spot-checked evidence and reproduction steps", NOW)


def _envelope(statement=None):
    return hrev.sign_review(statement or _statement(), _signer())


def _verify(envelope, kind="bundle", digest=SUBJECT, registry=None, now=NOW):
    return hrev.verify_review(envelope, kind, digest, registry or _registry(),
                              _material(), now=now)


class StatementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = hrev.load_schema(str(ROOT))

    def test_statement_schema(self):
        statement = _statement()
        self.assertEqual([], json_schema.json_schema_check(statement, self.schema))
        self.assertEqual("human", statement["reviewer"]["kind"])

    def test_statement_rejections(self):
        with self.assertRaises(ValueError):
            hrev.build_statement("bundle", SUBJECT, "pending", ISSUER, KEYID, "x", NOW)
        with self.assertRaises(ValueError):
            hrev.build_statement("planet", SUBJECT, "approve", ISSUER, KEYID, "x", NOW)
        with self.assertRaises(ValueError):
            hrev.build_statement("bundle", "ABC", "approve", ISSUER, KEYID, "x", NOW)


class VerifyTest(unittest.TestCase):
    def test_approve_ok(self):
        result = _verify(_envelope())
        self.assertTrue(result["ok"], result)
        self.assertEqual(hrev.STATE_APPROVED, hrev.review_state(result))
        self.assertEqual(ISSUER, result["reviewer"])

    def test_subject_binding(self):
        self.assertEqual("REVIEW-SUBJECT-MISMATCH",
                         _verify(_envelope(), digest="f" * 64)["reason"])
        self.assertEqual("REVIEW-SUBJECT-MISMATCH",
                         _verify(_envelope(), kind="claim")["reason"])

    def test_reviewer_must_be_human(self):
        result = _verify(_envelope(), registry=_registry(kind="service"))
        self.assertEqual("REVIEWER-NOT-HUMAN", result["reason"])
        self.assertEqual(hrev.STATE_INVALID, hrev.review_state(result))

    def test_lifecycle_fail_closed(self):
        revoked = _registry(status="revoked", revoked_at=NOW,
                            revocation_reason="compromise")
        self.assertEqual("KEY-REVOKED", _verify(_envelope(), registry=revoked)["reason"])
        self.assertEqual("KEY-EXPIRED",
                         _verify(_envelope(), now="2028-01-01T00:00:00Z")["reason"])

    def test_reject_and_escalate_are_not_approval(self):
        rejected = _verify(_envelope(_statement("reject")))
        self.assertFalse(rejected["ok"])
        self.assertEqual("REVIEW-NOT-APPROVED", rejected["reason"])
        self.assertEqual(hrev.STATE_REJECTED, hrev.review_state(rejected))
        escalated = _verify(_envelope(_statement("escalate")))
        self.assertEqual(hrev.STATE_ESCALATED, hrev.review_state(escalated))

    def test_missing_review_is_pending(self):
        self.assertEqual(hrev.STATE_PENDING, hrev.review_state(None))
        self.assertNotEqual(hrev.STATE_APPROVED, hrev.review_state(None))

    def test_payload_type_tamper(self):
        envelope = copy.deepcopy(_envelope())
        envelope["payloadType"] = "application/vnd.nf.other"
        self.assertEqual(hrev.STATE_INVALID, hrev.review_state(_verify(envelope)))

    def test_mutation_shows_decision_check_is_semantic(self):
        """弱化 schema 加出 "pending" 后，语义仍必须判非批准（不是只靠 schema）。"""
        schema = hrev.load_schema(str(ROOT))
        weakened = json.loads(json.dumps(schema))
        weakened["properties"]["decision"]["enum"].append("pending")
        statement = _statement()
        statement["decision"] = "pending"
        self.assertEqual([], json_schema.json_schema_check(statement, weakened))
        result = hrev.verify_review(_envelope(statement), "bundle", SUBJECT,
                                    _registry(), _material(), None, weakened, NOW)
        self.assertFalse(result["ok"])
        self.assertEqual("REVIEW-NOT-APPROVED", result["reason"])

    def test_cli_review_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "registry.json").write_text(json.dumps(_registry()), encoding="utf-8")
            (base / "material.json").write_text(json.dumps(_material()), encoding="utf-8")
            (base / "review.json").write_text(json.dumps(_envelope()), encoding="utf-8")
            base_cmd = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                        "--human-review", str(base / "review.json"),
                        "--subject-kind", "bundle", "--subject-digest", SUBJECT,
                        "--issuer-registry", str(base / "registry.json"),
                        "--key-material", str(base / "material.json"),
                        "--now", NOW, "--root", str(ROOT)]
            ok = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            self.assertIn("APPROVED", ok.stdout)
            (base / "review.json").write_text(
                json.dumps(_envelope(_statement("reject"))), encoding="utf-8")
            bad = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("REJECTED", bad.stdout)
            gate = subprocess.run([sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                                   "--review-gate", "--subject-digest", SUBJECT],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(2, gate.returncode, gate.stdout + gate.stderr)
            self.assertIn("PENDING", gate.stdout)


class VerifyIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.trust import bundle as tb
        cls.bundle = tb.build_bundle("b" * 64, "protocol/trust/claim-bundle.schema.json", [
            {"id": "C1", "type": "evidence", "subject_digest": "b" * 64,
             "payload_digest": "c" * 64}])
        from core.trust import canonical as tc
        cls.digest = tc.digest_of(cls.bundle)

    def _policy(self):
        return {"schema": "nf-trust-policy/1",
                "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
                "algorithms": ["hmac-sha256"], "tsa_roots": [], "required_level": "T0",
                "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}

    def _verify(self, review):
        from core.trust import verify as tv
        return tv.verify(self.bundle, self._policy(), str(ROOT), registry=_registry(),
                         material=_material(), now=NOW, human_review=review)

    def test_approved_review_check(self):
        result = self._verify(_envelope(_statement(digest=self.digest)))
        check = [c for c in result["report"]["checks"] if c["id"] == "A4-human-review"][0]
        self.assertTrue(check["ok"], check)
        self.assertIn("APPROVED", check["detail"])

    def test_pending_is_not_pass(self):
        result = self._verify(None)
        check = [c for c in result["report"]["checks"] if c["id"] == "A4-human-review"][0]
        self.assertFalse(check["ok"])
        self.assertIn("PENDING", check["detail"])

    def test_rejected_review_adds_issue(self):
        result = self._verify(_envelope(_statement("reject", digest=self.digest)))
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("REVIEW-NOT-APPROVED", codes)


if __name__ == "__main__":
    unittest.main()
