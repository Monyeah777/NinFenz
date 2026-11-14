#!/usr/bin/env python3
"""trust.signature 判据：链头语句绑定 + DSSE 签名 + registry 生命周期 + 端到端 T2。

主判据（WP-23）：
1. subject_kind/subject_digest 绑定：签 A 验 B 必须拒（不是「签名对就算过」）；
2. 签名有效但 issuer key 吊销/过期 → T1 失守（invalid，不降级）；
3. 端到端：真 DSSE(HMAC) + 真 SHA-256 + 本地 openssl TSA → 报告 achieved=T2 / exit 0；
   缺 T3 witness 时 required=T3 必须 exit 2 并给 WITNESS-MISSING。
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

from core import json_schema  # noqa: E402
from core.trust import anchor as ta  # noqa: E402
from core.trust import bundle as tb  # noqa: E402
from core.trust import canonical as tc  # noqa: E402
from core.trust import dsse  # noqa: E402
from core.trust import signature as tsig  # noqa: E402
from core.trust import verify as tv  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：T2 端到端跳过（不冒充已验）")
KEY = b"head-hmac-key-0123456789abcdef"
KEYID = "nf:test:hmac:2026"
ISSUER = "nf:test:issuer"
NOW = "2026-11-14T00:00:00Z"


def _registry(status="active", **extra):
    key = {"keyid": KEYID, "alg": "hmac-sha256", "status": status,
           "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
    key.update(extra)
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": "service", "keys": [key]}]}


def _material():
    return {KEYID: {"hex": KEY.hex()}}


def _signer():
    return [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)}]


def _policy(required="T0", tsa_root=None):
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
            "algorithms": ["hmac-sha256"],
            "tsa_roots": [tsa_root] if tsa_root else [],
            "required_level": required,
            "anchors": {"tsa": bool(tsa_root), "transparency": True,
                        "witness_threshold": 0}}


def _bundle():
    return tb.build_bundle("c" * 64, "protocol/trust/claim-bundle.schema.json", [
        {"id": "C1", "type": "evidence", "subject_digest": "b" * 64,
         "payload_digest": "c" * 64},
    ])


class StatementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tsig.load_schema(str(ROOT))

    def test_statement_roundtrip(self):
        statement = tsig.build_statement("bundle", "a" * 64, schema=self.schema)
        self.assertEqual("nf-chain-head/1", statement["schema"])
        self.assertEqual([], json_schema.json_schema_check(statement, self.schema))
        with self.assertRaises(ValueError):
            tsig.build_statement("planet", "a" * 64, schema=self.schema)
        with self.assertRaises(ValueError):
            tsig.build_statement("bundle", "ABC", schema=self.schema)
        with self.assertRaises(ValueError):
            tsig.build_statement("bundle", "a" * 64, issued_at="2026-01-01",
                                 schema=self.schema)

    def test_schema_unknown_field_rejected(self):
        statement = tsig.build_statement("card", "a" * 64, schema=self.schema)
        statement["unexpected"] = 1
        self.assertTrue(json_schema.json_schema_check(statement, self.schema))

    def test_issued_at_is_explicit_only(self):
        statement = tsig.build_statement("event", "a" * 64, schema=self.schema)
        self.assertNotIn("issued_at", statement)
        with_at = tsig.build_statement("event", "a" * 64, issued_at=NOW,
                                       schema=self.schema)
        self.assertEqual(NOW, with_at["issued_at"])


class SignVerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = tsig.load_schema(str(ROOT))

    def verify(self, envelope, kind="bundle", digest="a" * 64, registry=None,
               now=NOW):
        return tsig.verify_head(envelope, kind, digest, registry or _registry(),
                                _material(), now=now)

    def test_sign_and_verify(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        self.assertEqual(tsig.PAYLOAD_TYPE, envelope["payloadType"])
        result = self.verify(envelope)
        self.assertTrue(result["ok"], result)
        self.assertEqual([KEYID], result["signers"])
        self.assertEqual({KEYID: ISSUER}, result["issuers"])

    def test_all_subject_kinds(self):
        for kind in tsig.KINDS:
            envelope = tsig.sign_head(kind, "b" * 64, _signer(), schema=self.schema)
            self.assertTrue(self.verify(envelope, kind=kind, digest="b" * 64)["ok"], kind)

    def test_digest_and_kind_binding(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        self.assertEqual("SUBJECT-DIGEST-MISMATCH",
                         self.verify(envelope, digest="f" * 64)["reason"])
        self.assertEqual("SUBJECT-KIND-MISMATCH",
                         self.verify(envelope, kind="card")["reason"])

    def test_wrong_payload_type(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        envelope["payloadType"] = "application/vnd.nf.other"
        self.assertEqual("PAYLOAD-TYPE-MISMATCH", self.verify(envelope)["reason"])

    def test_tampered_payload_is_invalid(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        payload = json.loads(base64.b64decode(envelope["payload"]))
        payload["subject_digest"] = "f" * 64
        envelope["payload"] = base64.b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode()
        self.assertIn(self.verify(envelope)["reason"],
                      ("SUBJECT-DIGEST-MISMATCH", "SIGNATURE-INVALID"))

    def test_revoked_key_breaks_t1(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        revoked = _registry(status="revoked", revoked_at=NOW,
                            revocation_reason="key compromise")
        result = tsig.verify_head(envelope, "bundle", "a" * 64, revoked,
                                  _material(), now=NOW)
        self.assertFalse(result["ok"], result)
        self.assertEqual("KEY-REVOKED", result["reason"])

    def test_expired_key_rejected(self):
        envelope = tsig.sign_head("bundle", "a" * 64, _signer(), schema=self.schema)
        result = self.verify(envelope, now="2028-01-01T00:00:00Z")
        self.assertEqual("KEY-EXPIRED", result["reason"])

    def test_cli_verifies_t1(self):
        bundle = _bundle()
        digest = tc.digest_of(bundle)
        envelope = tsig.sign_head("bundle", digest, _signer(), schema=self.schema)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {
                "bundle.json": bundle,
                "policy.json": _policy("T1"),
                "registry.json": _registry(),
                "material.json": _material(),
                "head.json": envelope,
            }
            for name, doc in files.items():
                (base / name).write_text(json.dumps(doc), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--bundle", str(base / "bundle.json"),
                 "--policy", str(base / "policy.json"),
                 "--head-signature", str(base / "head.json"),
                 "--issuer-registry", str(base / "registry.json"),
                 "--key-material", str(base / "material.json"),
                 "--now", NOW, "--root", str(ROOT)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("achieved=T1", proc.stdout)


def _win(p: Path) -> str:
    return str(p).replace("\\", "/")


def _openssl(*args):
    return subprocess.run([OPENSSL, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120,
                          stdin=subprocess.DEVNULL)


def _make_tsa(tmp: Path):
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


def _issue(tmp: Path, data: Path):
    ca, cnf = _make_tsa(tmp)
    query = tmp / "req.tsq"
    token = tmp / "resp.tsr"
    _openssl("ts", "-query", "-data", str(data), "-sha256", "-cert", "-out", str(query))
    _openssl("ts", "-reply", "-config", str(cnf), "-queryfile", str(query), "-out", str(token))
    return ca, query, token


@NEED
class EndToEndT2Test(unittest.TestCase):
    """真签名 + 真摘要 + 真 RFC3161 → T2；缺 T3 witness → exit 2。"""

    @classmethod
    def setUpClass(cls):
        cls.schema = tsig.load_schema(str(ROOT))
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.bundle = _bundle()
        cls.digest = tc.digest_of(cls.bundle)
        cls.data = cls.tmp / "bundle.canonical"
        cls.data.write_bytes(tc.canonical_bytes(cls.bundle))
        cls.ca, cls.query, cls.token = _issue(cls.tmp, cls.data)
        cls.root = {"id": "nf:test:tsa",
                    "digest": hashlib.sha256(cls.ca.read_bytes()).hexdigest()}
        cls.anchor = ta.build_anchor_set(cls.digest, [{
            "kind": "rfc3161", "tsa": "nf:test:tsa",
            "token": base64.b64encode(cls.token.read_bytes()).decode()}])
        cls.envelope = tsig.sign_head("bundle", cls.digest, _signer(), schema=cls.schema)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_verify(self, required):
        verifier = ta.make_timestamp_verifier(str(self.query), str(self.ca),
                                              subject_path=str(self.data))
        return tv.verify(self.bundle, _policy(required, self.root), str(ROOT),
                         anchor=self.anchor, anchor_verifiers={"rfc3161": verifier},
                         head_signature=self.envelope, registry=_registry(),
                         material=_material(), now=NOW)

    def test_reaches_t2(self):
        result = self.run_verify("T2")
        self.assertEqual(0, result["exit_code"], result)
        self.assertEqual("T2", result["report"]["level"]["achieved"], result)

    def test_t3_still_undecidable(self):
        result = self.run_verify("T3")
        self.assertEqual(2, result["exit_code"], result)
        self.assertEqual("T2", result["report"]["level"]["achieved"], result)
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("WITNESS-MISSING", codes)

    def test_revoked_registry_breaks_t2(self):
        revoked = _registry(status="revoked", revoked_at=NOW,
                            revocation_reason="key compromise")
        verifier = ta.make_timestamp_verifier(str(self.query), str(self.ca),
                                              subject_path=str(self.data))
        result = tv.verify(self.bundle, _policy("T2", self.root), str(ROOT),
                           anchor=self.anchor, anchor_verifiers={"rfc3161": verifier},
                           head_signature=self.envelope, registry=revoked,
                           material=_material(), now=NOW)
        self.assertEqual(1, result["exit_code"], result)


if __name__ == "__main__":
    unittest.main()
