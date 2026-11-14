#!/usr/bin/env python3
"""端到端 T3 判据（G4）：真 DSSE 签名 + 真 RFC3161（本地 openssl TSA）+ STH + witness 阈值。

判据：
- T3 要求签名/时间戳/STH/witness 阈值同时成立 → achieved=T3 / exit 0；
- witness 阈值不足 → 不得达 T3（exit 2，缺 WITNESS-MISSING）；
- required=T4 → exit 2 + PUBLIC-ANCHOR-MISSING（公共锚未建，不得声称 T4）；
- STH/TSA 篡改 → exit 1（fail-closed）。
"""
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import anchor as ta  # noqa: E402
from core.trust import bundle as tb  # noqa: E402
from core.trust import canonical as tc  # noqa: E402
from core.trust import dsse  # noqa: E402
from core.trust import signature as tsig  # noqa: E402
from core.trust import verify as tv  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：端到端 T3 跳过（不冒充已验）")
KEY = b"t3-hmac-key-0123456789abcdef"
KEYID = "nf:t3:hmac:2026"
ISSUER = "nf:t3:issuer"
TSA_ID = "nf:t3:tsa"
LOG_ID = "nf:t3:log"
NOW = "2026-11-14T00:00:00Z"


def _win(p):
    return str(p).replace("\\", "/")


def _openssl(*args):
    return subprocess.run([OPENSSL, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120,
                          stdin=subprocess.DEVNULL)


def _make_tsa(tmp):
    (tmp / "tsa.cnf").write_text(
        "[ req ]\ndistinguished_name = dn\nprompt = no\n"
        "[ dn ]\nCN = NF Test TSA CA\nO = NF Test\n"
        "[ tsa ]\ndefault_tsa = tsa_config\n"
        "[ tsa_config ]\n"
        f"serial = {_win(tmp)}/tsaserial\ncrypto_device = builtin\n"
        f"signer_cert = {_win(tmp)}/tsa.crt\ncerts = {_win(tmp)}/ca.crt\n"
        f"signer_key = {_win(tmp)}/tsa.key\nsigner_digest = sha256\n"
        "default_policy = 1.2.3.4.1\nother_policies = 1.2.3.4.2\n"
        "digests = sha256, sha384, sha512\naccuracy = secs:1\nordering = yes\n"
        "tsa_name = yes\ness_cert_id_chain = no\ness_cert_id_alg = sha256\n",
        encoding="utf-8")
    (tmp / "tsa.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,nonRepudiation\n"
        "extendedKeyUsage=critical,timeStamping\n", encoding="utf-8")
    _openssl("req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(tmp / "ca.key"), "-out", str(tmp / "ca.crt"), "-days", "3650",
             "-config", str(tmp / "tsa.cnf"),
             "-addext", "basicConstraints=critical,CA:TRUE",
             "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    _openssl("req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(tmp / "tsa.key"), "-out", str(tmp / "tsa.csr"),
             "-config", str(tmp / "tsa.cnf"))
    _openssl("x509", "-req", "-in", str(tmp / "tsa.csr"), "-CA", str(tmp / "ca.crt"),
             "-CAkey", str(tmp / "ca.key"), "-CAcreateserial", "-out", str(tmp / "tsa.crt"),
             "-days", "3650", "-extfile", str(tmp / "tsa.ext"))
    (tmp / "tsaserial").write_text("01", encoding="utf-8")
    return tmp / "ca.crt", tmp / "tsa.cnf"


def _issue(tmp, data):
    ca, cnf = _make_tsa(tmp)
    query = tmp / "req.tsq"
    token = tmp / "resp.tsr"
    _openssl("ts", "-query", "-data", str(data), "-sha256", "-cert", "-out", str(query))
    _openssl("ts", "-reply", "-config", str(cnf), "-queryfile", str(query), "-out", str(token))
    return ca, query, token


def _checker(key):
    def check(message, signature):
        return dsse.hmac_sign(key, message.encode()) == signature
    return check


def _policy(required="T3", threshold=1):
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
            "algorithms": ["hmac-sha256"],
            "tsa_roots": [{"id": TSA_ID, "digest": "0" * 64}],
            "required_level": required,
            "anchors": {"tsa": True, "transparency": True,
                        "witness_threshold": threshold}}


def _registry():
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": "service",
                         "keys": [{"keyid": KEYID, "alg": "hmac-sha256",
                                   "status": "active",
                                   "not_before": "2026-01-01T00:00:00Z",
                                   "not_after": "2027-01-01T00:00:00Z"}]}]}


def _material():
    return {KEYID: {"hex": KEY.hex()}}


@NEED
class EndToEndT3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tv.load_schema(str(ROOT))
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.bundle = tb.build_bundle("f" * 64, "protocol/trust/claim-bundle.schema.json", [
            {"id": "T3-1", "type": "evidence", "subject_digest": "b" * 64,
             "payload_digest": "c" * 64}])
        cls.digest = tc.digest_of(cls.bundle)
        cls.data = cls.tmp / "bundle.canonical"
        cls.data.write_bytes(tc.canonical_bytes(cls.bundle))
        cls.ca, cls.query, cls.token = _issue(cls.tmp, cls.data)
        cls.ca_digest = hashlib.sha256(cls.ca.read_bytes()).hexdigest()
        cls.envelope = tsig.sign_head(
            "bundle", cls.digest,
            [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)}], root=str(ROOT))
        cls.anchor = cls._anchors()

    @classmethod
    def _anchors(cls, sth_sig_key=KEY):
        import base64
        sth = {"kind": "transparency-sth", "log_id": LOG_ID, "tree_size": 7,
               "root": cls.digest}
        sth["signature"] = base64.b64encode(
            dsse.hmac_sign(sth_sig_key, ta.sth_statement(sth).encode())).decode()
        witness = {"kind": "witness", "witness_id": "w1", "keyid": KEYID,
                   "sig": base64.b64encode(dsse.hmac_sign(
                       KEY, ta.witness_statement(cls.digest, "w1", KEYID).encode())).decode()}
        token = base64.b64encode(cls.token.read_bytes()).decode()
        return ta.build_anchor_set(cls.digest, [
            {"kind": "rfc3161", "tsa": TSA_ID, "token": token}, sth, witness])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def policy(self, required="T3", threshold=1):
        policy = _policy(required, threshold)
        policy["tsa_roots"] = [{"id": TSA_ID, "digest": self.ca_digest}]
        return policy

    def verifiers(self, sth_key=KEY):
        return {"rfc3161": ta.make_timestamp_verifier(
                    str(self.query), str(self.ca), subject_path=str(self.data)),
                "transparency-sth": ta.make_sth_verifier({LOG_ID: _checker(sth_key)}),
                "witness": ta.make_witness_verifier({KEYID: _checker(KEY)})}

    def run_verify(self, required="T3", threshold=1, anchor=None, verifiers=None):
        return tv.verify(self.bundle, self.policy(required, threshold), str(ROOT),
                         anchor=anchor or self.anchor,
                         anchor_verifiers=verifiers or self.verifiers(),
                         head_signature=self.envelope, registry=_registry(),
                         material=_material(), now=NOW)

    def test_t3_achieved(self):
        result = self.run_verify()
        self.assertEqual(0, result["exit_code"], result)
        self.assertEqual("T3", result["report"]["level"]["achieved"], result)

    def test_t4_not_claimed(self):
        result = self.run_verify("T4")
        self.assertEqual(2, result["exit_code"], result)
        self.assertEqual("T3", result["report"]["level"]["achieved"])
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("PUBLIC-ANCHOR-MISSING", codes)

    def test_threshold_not_met(self):
        result = self.run_verify("T3", threshold=2)
        self.assertEqual(2, result["exit_code"], result)
        self.assertEqual("T2", result["report"]["level"]["achieved"], result)
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("WITNESS-MISSING", codes)

    def test_bad_sth_signature_invalid(self):
        result = self.run_verify(verifiers=self.verifiers(sth_key=b"other-key"))
        self.assertEqual(1, result["exit_code"], result)

    def test_tampered_tsa_token_invalid(self):
        anchor = json.loads(json.dumps(self.anchor))
        raw = bytearray(base64.b64decode(anchor["anchors"][0]["token"]))
        raw[-1] ^= 0xFF
        anchor["anchors"][0]["token"] = base64.b64encode(bytes(raw)).decode()
        result = self.run_verify(anchor=anchor)
        self.assertEqual(1, result["exit_code"], result)


if __name__ == "__main__":
    unittest.main()
