#!/usr/bin/env python3
"""public_anchor 判据：Rekor 风格 inclusion + SET 签名 + 目标绑定；离线验、显式联网抓取。"""
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import receipts  # noqa: E402
from core.trust import anchor as ta  # noqa: E402
from core.trust import bundle as tb  # noqa: E402
from core.trust import canonical as tc  # noqa: E402
from core.trust import dsse  # noqa: E402
from core.trust import public_anchor as pua  # noqa: E402
from core.trust import signature as tsig  # noqa: E402
from core.trust import verify as tv  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：ECDSA SET 面跳过（不冒充已验）")
KEY = b"public-anchor-key-0123456789abcdef"
KEYID = "nf:test:hmac:2026"
ISSUER = "nf:test:issuer"
LOG_ID = "c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224c76f77a0a1c8"
TARGET = "a" * 64
NOW = "2026-11-14T00:00:00Z"


def _body(target=TARGET):
    return json.dumps({"apiVersion": "0.0.1", "kind": "hashedrekord",
                       "spec": {"data": {"hash": {"algorithm": "sha256",
                                                  "value": target}}}},
                      separators=(",", ":"), sort_keys=True).encode()


def _entry(target=TARGET, bodies=None):
    bodies = bodies or [_body(target)]
    leaves = [bytes.fromhex(pua.leaf_hash(b)) for b in bodies]
    root = receipts.merkle_root(leaves).hex()
    index = 0
    proof = [item["hash"] for item in receipts.inclusion_proof(leaves, index)]
    doc = {"schema": "nf-public-anchor/1", "kind": "rekor-entry",
           "log_id": LOG_ID, "log_index": index, "tree_size": len(leaves),
           "root_hash": root, "body_b64": base64.b64encode(bodies[index]).decode(),
           "integrated_time": 1700000000,
           "inclusion_proof": proof}
    payload = pua.set_payload(doc)
    doc["signed_entry_timestamp"] = base64.b64encode(
        dsse.hmac_sign(KEY, payload)).decode()
    return doc


def _verifier():
    return lambda data, sig: dsse.hmac_sign(KEY, data) == sig


class VerifyTest(unittest.TestCase):
    def test_valid_entry_with_hashedrekord_target(self):
        result = pua.verify_public_anchor(_entry(), _verifier(), LOG_ID, TARGET)
        self.assertTrue(result["ok"], result)
        self.assertEqual(TARGET, result["target_digest"])

    def test_explicit_target_digest_field(self):
        doc = _entry()
        doc["target_digest"] = TARGET
        self.assertTrue(pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["ok"])

    def test_log_must_be_pinned(self):
        self.assertEqual("PUBLIC-ANCHOR-LOG-UNPINNED",
                         pua.verify_public_anchor(_entry(), _verifier(), "", TARGET)["reason"])
        self.assertEqual("PUBLIC-ANCHOR-LOG-MISMATCH",
                         pua.verify_public_anchor(_entry(), _verifier(), "f" * 64,
                                                  TARGET)["reason"])

    def test_inclusion_tamper(self):
        doc = _entry()
        doc["root_hash"] = "f" * 64
        self.assertEqual("PUBLIC-ANCHOR-INCLUSION-INVALID",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])
        doc = _entry()
        doc["log_index"] = 0
        doc["tree_size"] = 2
        self.assertEqual("PUBLIC-ANCHOR-INCLUSION-INVALID",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])

    def test_set_signature_tamper(self):
        doc = _entry()
        doc["signed_entry_timestamp"] = base64.b64encode(b"bad").decode()
        self.assertEqual("PUBLIC-ANCHOR-SET-INVALID",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])

    def test_target_binding(self):
        doc = _entry(target="b" * 64)
        self.assertEqual("PUBLIC-ANCHOR-TARGET-MISMATCH",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])
        body = json.dumps({"apiVersion": "0.0.1", "kind": "other"}).encode()
        doc = _entry(target=TARGET, bodies=[body])
        self.assertEqual("PUBLIC-ANCHOR-TARGET-UNBOUND",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])

    def test_schema_invalid(self):
        doc = _entry()
        doc["kind"] = "public-tsa"
        self.assertEqual("PUBLIC-ANCHOR-SCHEMA-INVALID",
                         pua.verify_public_anchor(doc, _verifier(), LOG_ID, TARGET)["reason"])

    @NEED
    def test_openssl_ecdsa_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            key = base / "ec.pem"
            subprocess.run(["openssl", "ecparam", "-genkey", "-name", "prime256v1",
                            "-noout", "-out", str(key)], check=True,
                           capture_output=True, timeout=60)
            data = b"set-payload"
            (base / "data").write_bytes(data)
            (base / "sig").write_bytes(
                subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(key),
                                str(base / "data")], check=True, capture_output=True,
                               timeout=60).stdout)
            verifier = pua.make_openssl_verifier(str(key))
            self.assertTrue(verifier(data, (base / "sig").read_bytes()))
            self.assertFalse(verifier(b"other", (base / "sig").read_bytes()))


class FetchTest(unittest.TestCase):
    def test_fetch_parsing(self):
        body = base64.b64encode(_body()).decode()
        fake = {"uuid-1": {"body": body, "integratedTime": 1700000000,
                           "logID": LOG_ID, "logIndex": 0,
                           "verification": {
                               "inclusionProof": {"logIndex": 0, "treeSize": 1,
                                                  "rootHash": pua.leaf_hash(_body()),
                                                  "hashes": []},
                               "signedEntryTimestamp": "c2ln"}}}
        with mock.patch("urllib.request.urlopen") as opened:
            opened.return_value.__enter__.return_value.read.return_value = (
                json.dumps(fake).encode())
            doc = pua.fetch_rekor_entry("uuid-1")
        self.assertEqual(LOG_ID, doc["log_id"])
        self.assertEqual(TARGET, doc.get("target_digest"))
        self.assertEqual(pua.leaf_hash(_body()), doc["root_hash"])

    def test_fetch_public_key(self):
        with mock.patch("urllib.request.urlopen") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b"PEM"
            self.assertEqual("PEM", pua.fetch_rekor_public_key())


def _bundle_and_policy(required="T4"):
    bundle = tb.build_bundle("d" * 64, "protocol/trust/claim-bundle.schema.json", [
        {"id": "P1", "type": "evidence", "subject_digest": "b" * 64,
         "payload_digest": "c" * 64}])
    policy = {"schema": "nf-trust-policy/1",
              "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
              "algorithms": ["hmac-sha256"],
              "tsa_roots": [{"id": "nf:tsa:test", "digest": "0" * 64}],
              "required_level": required,
              "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}
    return bundle, policy


def _anchors(digest):
    import base64 as b64
    sth = {"kind": "transparency-sth", "log_id": "nf:log:test", "tree_size": 7,
           "root": digest}
    sth["signature"] = b64.b64encode(
        dsse.hmac_sign(KEY, ta.sth_statement(sth).encode())).decode()
    witness = {"kind": "witness", "witness_id": "w1", "keyid": KEYID,
               "sig": b64.b64encode(dsse.hmac_sign(
                   KEY, ta.witness_statement(digest, "w1", KEYID).encode())).decode()}
    return [{"kind": "rfc3161", "tsa": "nf:tsa:test", "token": "AAAA"}, sth, witness]


class T4IntegrationTest(unittest.TestCase):
    def _checker(self, message, signature):
        return dsse.hmac_sign(KEY, message.encode()) == signature

    def run_verify(self, with_public=True):
        bundle, policy = _bundle_and_policy("T4")
        digest = tc.digest_of(bundle)
        head = tsig.sign_head("bundle", digest,
                              [{"keyid": KEYID,
                                "sign": lambda data: dsse.hmac_sign(KEY, data)}],
                              root=str(ROOT))
        anchor_doc = ta.build_anchor_set(digest, _anchors(digest), root=str(ROOT))
        verifiers = {"rfc3161": lambda item, d: {"ok": True, "gen_time": NOW},
                     "transparency-sth": ta.make_sth_verifier({"nf:log:test": self._checker}),
                     "witness": ta.make_witness_verifier({KEYID: self._checker})}
        public = _entry(target=digest) if with_public else None
        return tv.verify(bundle, policy, str(ROOT), anchor=anchor_doc,
                         anchor_verifiers=verifiers, head_signature=head,
                         registry={"schema": "nf-issuer-registry/1",
                                   "issuers": [{"id": ISSUER, "kind": "service",
                                                "keys": [{"keyid": KEYID,
                                                          "alg": "hmac-sha256",
                                                          "status": "active",
                                                          "not_before": "2026-01-01T00:00:00Z",
                                                          "not_after": "2027-01-01T00:00:00Z"}]}]},
                         material={KEYID: {"hex": KEY.hex()}}, now=NOW,
                         public_anchor=public, public_anchor_verifier=_verifier(),
                         public_log_id=LOG_ID)

    def test_t4_achieved_with_public_anchor(self):
        result = self.run_verify(True)
        self.assertEqual(0, result["exit_code"], result)
        self.assertEqual("T4", result["report"]["level"]["achieved"], result)

    def test_t4_missing_public_anchor(self):
        result = self.run_verify(False)
        self.assertEqual(2, result["exit_code"], result)
        self.assertEqual("T3", result["report"]["level"]["achieved"])
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("PUBLIC-ANCHOR-MISSING", codes)


if __name__ == "__main__":
    unittest.main()
