"""DSSE v1 PAE, envelope, multi-signature, and tamper tests."""
import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import dsse

KEY_A = b"a" * 32
KEY_B = b"b" * 32
PAYLOAD_TYPE = "application/vnd.in-toto+json"
PAYLOAD = b'{"subject":[{"name":"x","digest":{"sha256":"00"}}]}'
ROOT = Path(__file__).resolve().parents[2]


class PAETest(unittest.TestCase):
    def test_official_vector(self):
        self.assertEqual(
            b"DSSEv1 29 http://example.com/HelloWorld 11 hello world",
            dsse.pae("http://example.com/HelloWorld", b"hello world"),
        )

    def test_length_is_utf8_bytes_not_characters(self):
        self.assertEqual(b"DSSEv1 2 \xce\xbb 1 \x00", dsse.pae("λ", b"\x00"))

    def test_payload_must_already_be_bytes(self):
        with self.assertRaises(dsse.DSSEError):
            dsse.pae(PAYLOAD_TYPE, "text")  # type: ignore[arg-type]


class EnvelopeTest(unittest.TestCase):
    def setUp(self):
        self.env = dsse.sign(PAYLOAD_TYPE, PAYLOAD, KEY_A, "key-a")

    def test_roundtrip_returns_exact_authenticated_bytes(self):
        got = dsse.verify_json(dsse.dumps(self.env), {"key-a": KEY_A},
                               accepted_payload_types={PAYLOAD_TYPE})
        self.assertEqual(PAYLOAD_TYPE, got.payload_type)
        self.assertEqual(PAYLOAD, got.payload)
        self.assertEqual(("key-a",), got.accepted_keyids)

    def test_standard_and_urlsafe_base64_are_both_accepted(self):
        raw_payload = bytes(range(250, 256)) + PAYLOAD
        env = dsse.sign(PAYLOAD_TYPE, raw_payload, KEY_A, "key-a")
        url = copy.deepcopy(env)
        url["payload"] = base64.urlsafe_b64encode(raw_payload).decode("ascii")
        url["signatures"][0]["sig"] = base64.urlsafe_b64encode(
            base64.b64decode(env["signatures"][0]["sig"])).decode("ascii")
        self.assertEqual(raw_payload, dsse.verify_json(dsse.dumps(url), {"key-a": KEY_A}).payload)

    def test_payload_and_payload_type_tamper_rejected(self):
        for field, value in (("payload", dsse.b64encode(b"changed")),
                             ("payloadType", "application/json")):
            bad = copy.deepcopy(self.env)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(dsse.DSSEError):
                dsse.verify_json(dsse.dumps(bad), {"key-a": KEY_A})

    def test_signature_tamper_and_wrong_key_rejected(self):
        bad = copy.deepcopy(self.env)
        raw = bytearray(base64.b64decode(bad["signatures"][0]["sig"]))
        raw[0] ^= 1
        bad["signatures"][0]["sig"] = base64.b64encode(raw).decode("ascii")
        with self.assertRaises(dsse.DSSEError):
            dsse.verify_json(dsse.dumps(bad), {"key-a": KEY_A})
        with self.assertRaises(dsse.DSSEError):
            dsse.verify_json(dsse.dumps(self.env), {"key-a": KEY_B})

    def test_noncanonical_and_mixed_base64_rejected(self):
        for value in ("Zg===", "Zg", "Z g==", "Z+_="):
            with self.subTest(value=value), self.assertRaises(dsse.DSSEError):
                dsse.b64decode(value)

    def test_required_fields_and_types_are_fail_closed(self):
        fixtures = [
            {},
            {"payload": "e30=", "payloadType": PAYLOAD_TYPE, "signatures": "bad"},
            {"payload": "e30=", "payloadType": 1, "signatures": []},
            {"payload": 1, "payloadType": PAYLOAD_TYPE, "signatures": []},
            {"payload": "e30=", "payloadType": PAYLOAD_TYPE, "signatures": [{}]},
        ]
        for doc in fixtures:
            with self.subTest(doc=doc), self.assertRaises(dsse.DSSEError):
                dsse.parse(doc)

    def test_unknown_fields_are_ignored(self):
        doc = copy.deepcopy(self.env)
        doc["future"] = {"ok": True}
        doc["signatures"][0]["future"] = "ignored"
        self.assertEqual(PAYLOAD, dsse.verify_json(dsse.dumps(doc), {"key-a": KEY_A}).payload)

    def test_multi_signature_threshold_counts_unique_keys(self):
        second = dsse.sign(PAYLOAD_TYPE, PAYLOAD, KEY_B, "key-b")["signatures"][0]
        multi = copy.deepcopy(self.env)
        multi["signatures"].append(second)
        got = dsse.verify_json(dsse.dumps(multi), {"key-a": KEY_A, "key-b": KEY_B},
                               threshold=2)
        self.assertEqual(("key-a", "key-b"), got.accepted_keyids)
        duplicated = copy.deepcopy(self.env)
        duplicated["signatures"].append(dict(self.env["signatures"][0], keyid="alias"))
        with self.assertRaises(dsse.DSSEError):
            dsse.verify_json(dsse.dumps(duplicated), {"key-a": KEY_A}, threshold=2)

    def test_keyid_is_a_hint_not_signature_authority(self):
        env = dsse.sign(PAYLOAD_TYPE, PAYLOAD, KEY_A)
        env["signatures"][0]["keyid"] = "untrusted-looking-hint"
        with self.assertRaises(dsse.DSSEError):
            dsse.verify_json(dsse.dumps(env), {"key-a": KEY_A})
        self.assertEqual(PAYLOAD, dsse.verify_json(
            dsse.dumps(env), {"untrusted-looking-hint": KEY_A}).payload)

    def test_unsupported_payload_type_rejected_after_signature(self):
        with self.assertRaises(dsse.DSSEError):
            dsse.verify_json(dsse.dumps(self.env), {"key-a": KEY_A},
                             accepted_payload_types={"application/json"})

    def test_official_reference_envelope_shape_and_signature_size(self):
        envelope = {
            "payload": "aGVsbG8gd29ybGQ=",
            "payloadType": "http://example.com/HelloWorld",
            "signatures": [{"sig":
                "A3JqsQGtVsJ2O2xqrI5IcnXip5GToJ3F+FnZ+O88SjtR6rDAajabZKciJTfUiHqJPcIAriEGAHTVeCUjW2JIZA=="}],
        }
        parsed = dsse.loads(json.dumps(envelope).encode("utf-8"))
        self.assertEqual(b"hello world", parsed.payload)
        self.assertEqual(64, len(parsed.signatures[0].sig))


class CLITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nf_dsse_cli_")
        self.dir = Path(self.tmp.name)
        self.key = self.dir / "key"
        self.key.write_bytes(KEY_A)
        self.payload = self.dir / "payload.json"
        self.payload.write_bytes(PAYLOAD)
        self.envelope = self.dir / "payload.dsse.json"
        self.out = self.dir / "verified.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        return subprocess.run(  # nosec B603 - argv list, fixed local CLI
            [sys.executable, str(ROOT / "scripts" / "nf.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            timeout=60,
            env={**dict(os.environ), "PYTHONUTF8": "1",
                 "PYTHONIOENCODING": "utf-8"})

    def test_sign_and_verify_cli_roundtrip(self):
        signed = self._run("dsse", "sign", "--payload", str(self.payload),
                           "--payload-type", PAYLOAD_TYPE, "--key-file", str(self.key),
                           "--out", str(self.envelope))
        self.assertEqual(0, signed.returncode, signed.stderr)
        verified = self._run("dsse", "verify", "--envelope", str(self.envelope),
                             "--key-file", str(self.key), "--payload-type", PAYLOAD_TYPE,
                             "--out", str(self.out), "--json")
        self.assertEqual(0, verified.returncode, verified.stderr)
        self.assertEqual(PAYLOAD, self.out.read_bytes())
        machine = json.loads(verified.stdout)
        self.assertEqual("dsse-verify", machine["kind"])
        self.assertTrue(machine["ok"])

    def test_cli_rejects_tampered_payload_type(self):
        signed = self._run("dsse", "sign", "--payload", str(self.payload),
                           "--payload-type", PAYLOAD_TYPE, "--key-file", str(self.key),
                           "--out", str(self.envelope))
        self.assertEqual(0, signed.returncode, signed.stderr)
        doc = json.loads(self.envelope.read_text(encoding="utf-8"))
        doc["payloadType"] = "application/json"
        self.envelope.write_text(json.dumps(doc), encoding="utf-8")
        verified = self._run("dsse", "verify", "--envelope", str(self.envelope),
                             "--key-file", str(self.key))
        self.assertEqual(1, verified.returncode)
        self.assertIn("DSSE 失败", verified.stderr)


if __name__ == "__main__":
    unittest.main()
