#!/usr/bin/env python3
"""trust.dsse 判据：pae 向量逐条 + 信封签名/验签 + 篡改矩阵 + 算法白名单。

为什么有它：FR-A3-01 的验收是「PAE + 至少 1 个有效签名 + keyid 可解析」。本件用冻结向量钉
PAE 口径，用固定 key 跑端到端签/验，并把「坏载荷/坏签名/未知 key/算法越界/算法不符」逐条置红。
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

from core import json_schema  # noqa: E402
from core.trust import dsse  # noqa: E402

VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"
KEY = b"vector-hmac-key-0123456789abcdef"
KEYID = "nf:test:hmac:2026"


def _pae_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    return [v for v in doc["vectors"] if v["family"] == "pae"]


def _keys():
    return {KEYID: {"alg": "hmac-sha256", "verify": dsse.hmac_verifier(KEY)}}


def _signed(payload_type="application/vnd.nf.claim-bundle+json",
            payload=b'{"schema":"nf-claim-bundle/1"}'):
    return dsse.sign_envelope(payload_type, payload, [
        {"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)},
    ])


class PaeVectorTest(unittest.TestCase):
    def test_pae_vectors(self):
        vectors = _pae_vectors()
        self.assertGreaterEqual(len(vectors), 4)
        for vec in vectors:
            ptype = vec["input"]["payload_type_utf8"].encode()
            payload = base64.b64decode(vec["input"]["payload_b64"])
            if vec["expected"].get("valid"):
                raw = dsse.pae(ptype, payload)
                self.assertEqual(vec["expected"]["pae_b64"], base64.b64encode(raw).decode(),
                                 vec["id"])
            else:
                with self.assertRaises(ValueError) as ctx:
                    dsse.pae(ptype, payload)
                self.assertIn("PAE-EMPTY-TYPE", str(ctx.exception), vec["id"])

    def test_length_is_bytes_not_chars(self):
        raw = dsse.pae(b"application/vnd.nf.text+utf8", "中文".encode())
        self.assertIn(" 6 中文".encode(), raw)
        self.assertNotIn(" 2 中文".encode(), raw)


class EnvelopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = dsse.load_schema(str(ROOT))

    def test_roundtrip_and_schema(self):
        envelope = _signed()
        self.assertEqual([], json_schema.json_schema_check(envelope, self.schema))
        result = dsse.verify_envelope(envelope, _keys(), self.schema)
        self.assertTrue(result["valid"], result)
        self.assertEqual([KEYID], result["signers"])
        self.assertEqual(b'{"schema":"nf-claim-bundle/1"}', result["payload"])

    def test_determined_signature(self):
        self.assertEqual(_signed(), _signed())

    def test_two_signers(self):
        other = "nf:test:hmac:2027"
        key2 = b"second-key-0000000000000000000000"
        envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"hi", [
            {"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)},
            {"keyid": other, "sign": lambda data: dsse.hmac_sign(key2, data)},
        ])
        keys = _keys()
        keys[other] = {"alg": "hmac-sha256", "verify": dsse.hmac_verifier(key2)}
        result = dsse.verify_envelope(envelope, keys, self.schema)
        self.assertTrue(result["valid"], result)
        self.assertEqual([KEYID, other], result["signers"])

    def test_alg_pluggable_without_third_party(self):
        """ed25519/ecdsa-p256 只作为可插拔回调：core 不引第三方库。"""
        envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"x", [
            {"keyid": "nf:test:ed25519", "alg": "ed25519",
             "sign": lambda data: b"fake-sig-" + data[-8:]},
        ])
        keys = {"nf:test:ed25519": {"alg": "ed25519",
                                    "verify": lambda data, sig: sig == b"fake-sig-" + data[-8:]}}
        self.assertTrue(dsse.verify_envelope(envelope, keys, self.schema)["valid"])


class TamperMatrixTest(unittest.TestCase):
    def assertReason(self, reason, envelope, keys=None):
        result = dsse.verify_envelope(envelope, keys if keys is not None else _keys())
        self.assertFalse(result["valid"], result)
        self.assertEqual(reason, result["reason"], result)

    def test_tampered_payload(self):
        bad = copy.deepcopy(_signed())
        bad["payload"] = base64.b64encode(b'{"schema":"nf-claim-bundle/2"}').decode()
        self.assertReason("SIGNATURE-INVALID", bad)

    def test_tampered_signature(self):
        bad = copy.deepcopy(_signed())
        raw = bytearray(base64.b64decode(bad["signatures"][0]["sig"]))
        raw[0] ^= 0xFF
        bad["signatures"][0]["sig"] = base64.b64encode(bytes(raw)).decode()
        self.assertReason("SIGNATURE-INVALID", bad)

    def test_bad_payload_base64(self):
        bad = copy.deepcopy(_signed())
        bad["payload"] = "not base64!!"
        self.assertReason("PAYLOAD-B64-INVALID", bad)

    def test_missing_signatures(self):
        bad = copy.deepcopy(_signed())
        bad["signatures"] = []
        self.assertReason("SIGNATURES-MISSING", bad)

    def test_unknown_key_only(self):
        envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"x", [
            {"keyid": "nf:unknown", "sign": lambda data: b"sig"},
        ])
        self.assertReason("NO-VALID-SIGNATURE", envelope)

    def test_unsupported_alg(self):
        envelope = copy.deepcopy(_signed())
        envelope["signatures"][0]["alg"] = "rsa-1024"
        keys = {KEYID: {"alg": "rsa-1024", "verify": lambda data, sig: True}}
        self.assertReason("ALG-UNSUPPORTED", envelope, keys)

    def test_alg_mismatch(self):
        envelope = copy.deepcopy(_signed())
        envelope["signatures"][0]["alg"] = "ed25519"
        self.assertReason("ALG-MISMATCH", envelope)

    def test_trusted_bad_signature_is_fail_closed(self):
        envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"x", [
            {"keyid": KEYID, "sign": lambda data: b"wrong-signature"},
        ])
        self.assertReason("SIGNATURE-INVALID", envelope)

    def test_unknown_key_is_ignored_but_not_a_pass(self):
        envelope = copy.deepcopy(_signed())
        envelope["signatures"].append({"keyid": "nf:unknown", "sig": "AAAA"})
        result = dsse.verify_envelope(envelope, _keys())
        self.assertTrue(result["valid"], result)
        self.assertEqual(["nf:unknown"], result["untrusted"])

    def test_verifier_exception_is_failure(self):
        envelope = _signed()
        keys = {KEYID: {"alg": "hmac-sha256",
                        "verify": lambda data, sig: (_ for _ in ()).throw(RuntimeError("boom"))}}
        self.assertReason("SIGNATURE-INVALID", envelope, keys)

    def test_schema_is_the_structural_gate(self):
        envelope = copy.deepcopy(_signed())
        envelope["unexpected_extension"] = 1
        self.assertTrue(dsse.verify_envelope(envelope, _keys())["valid"])
        self.assertEqual("SCHEMA-INVALID",
                         dsse.verify_envelope(envelope, _keys(),
                                              dsse.load_schema(str(ROOT)))["reason"])


class CliEnvelopeTest(unittest.TestCase):
    """生产接线判据：离线入口 scripts/trust_verify.py 能用 hmac 验同一信封（非测试专用实现）。"""

    def test_cli_verifies_and_rejects(self):
        envelope = _signed()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "envelope.json"
            path.write_text(json.dumps(envelope), encoding="utf-8")
            base = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                    "--envelope", str(path), "--keyid", KEYID,
                    "--hmac-key-hex", KEY.hex(), "--root", str(ROOT)]
            ok = subprocess.run(base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stderr)
            self.assertIn("valid envelope", ok.stdout)
            bad = copy.deepcopy(envelope)
            bad["payload"] = base64.b64encode(b"tampered").decode()
            path.write_text(json.dumps(bad), encoding="utf-8")
            rejected = subprocess.run(base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, rejected.returncode, rejected.stdout + rejected.stderr)
            self.assertIn("SIGNATURE-INVALID", rejected.stdout)


class BuildGuardTest(unittest.TestCase):
    def test_build_requires_signature(self):
        with self.assertRaises(ValueError) as ctx:
            dsse.build_envelope("application/vnd.nf.text+utf8", b"x", [])
        self.assertIn("修复指引", str(ctx.exception))

    def test_signer_must_return_bytes(self):
        with self.assertRaises(ValueError):
            dsse.sign_envelope("application/vnd.nf.text+utf8", b"x", [
                {"keyid": "k", "sign": lambda data: "string"},
            ])

    def test_signer_alg_whitelist(self):
        with self.assertRaises(ValueError) as ctx:
            dsse.sign_envelope("application/vnd.nf.text+utf8", b"x", [
                {"keyid": "k", "alg": "rsa-1024", "sign": lambda data: b"sig"},
            ])
        self.assertIn("修复指引", str(ctx.exception))

    def test_missing_schema_root_raises_with_guidance(self):
        with self.assertRaises(ValueError) as ctx:
            dsse.load_schema(str(ROOT / "no_such_root_for_dsse"))
        self.assertIn("修复指引", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
