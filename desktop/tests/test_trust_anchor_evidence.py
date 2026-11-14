#!/usr/bin/env python3
"""trust.anchor 判据：nf-anchor/1 构建 + 四类锚核验 + 事实投影 + verify 接线。

不依赖外网：RFC3161 用**本地 openssl TSA**（自签 CA + TS 证书）签真 token、离线验；
witness/STH 用 hmac 回调；git-commit 用本仓 HEAD。缺 openssl 时该组跳过（不冒充已验）。
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
from core.trust import verify as tv  # noqa: E402

OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：RFC3161 锚面跳过（不冒充已验）")
LOG_ID = "nf:test:log"
TARGET = hashlib.sha256(b"chain-head-payload").hexdigest()


def _win(p: Path) -> str:
    return str(p).replace("\\", "/")


def _openssl(*args, cwd=None):
    return subprocess.run([OPENSSL, *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120,
                          stdin=subprocess.DEVNULL)


def _make_tsa(tmp: Path) -> tuple[Path, Path]:
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


def _issue(tmp: Path, data: Path) -> tuple[Path, Path]:
    ca, cnf = _make_tsa(tmp)
    query = tmp / "req.tsq"
    token = tmp / "resp.tsr"
    _openssl("ts", "-query", "-data", str(data), "-sha256", "-cert", "-out", str(query))
    _openssl("ts", "-reply", "-config", str(cnf), "-queryfile", str(query), "-out", str(token))
    return query, token


def _policy(tsa_root=None, witness_threshold=0, required="T0"):
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": "nf:test:issuer", "keyid": "nf:test:hmac:2026",
                         "alg": "hmac-sha256"}],
            "algorithms": ["hmac-sha256"],
            "tsa_roots": [tsa_root] if tsa_root else [],
            "required_level": required,
            "anchors": {"tsa": bool(tsa_root), "transparency": True,
                        "witness_threshold": witness_threshold}}


def _hmac_checker(key):
    def check(message, signature):
        return dsse.hmac_sign(key, message.encode()) == signature
    return check


def _witness_anchor(keyid, witness_id, key, digest=TARGET):
    message = ta.witness_statement(digest, witness_id, keyid)
    return {"kind": "witness", "witness_id": witness_id, "keyid": keyid,
            "sig": base64.b64encode(dsse.hmac_sign(key, message.encode())).decode()}


def _sth_anchor(key, log_id=LOG_ID, root=TARGET):
    sth = {"kind": "transparency-sth", "log_id": log_id, "tree_size": 7, "root": root}
    statement = ta.sth_statement(sth)
    sth["signature"] = base64.b64encode(dsse.hmac_sign(key, statement.encode())).decode()
    return sth


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ta.load_schema(str(ROOT))

    def test_build_all_four_kinds(self):
        anchors = [
            {"kind": "rfc3161", "tsa": "nf:test:tsa", "token": "AAAA"},
            _sth_anchor(b"k"),
            _witness_anchor("nf:test:w1", "w1", b"k"),
            {"kind": "git-commit", "repo": "NinFenz", "commit": "0" * 40},
        ]
        doc = ta.build_anchor_set(TARGET, anchors, self.schema)
        self.assertEqual([], json_schema.json_schema_check(doc, self.schema))
        self.assertEqual(TARGET, doc["target_digest"])

    def test_unknown_kind_and_bad_digest_rejected(self):
        with self.assertRaises(ValueError):
            ta.build_anchor_set(TARGET, [{"kind": "magic", "x": 1}], self.schema)
        with self.assertRaises(ValueError):
            ta.build_anchor_set("ABC", [{"kind": "git-commit", "repo": "r",
                                         "commit": "0" * 40}], self.schema)
        with self.assertRaises(ValueError):
            ta.build_anchor_set(TARGET, [], self.schema)

    def test_schema_requires_min_one_anchor(self):
        weakened = json.loads(json.dumps(self.schema))
        weakened["properties"]["anchors"].pop("minItems")
        doc = {"schema": "nf-anchor/1", "target_digest": TARGET, "anchors": []}
        self.assertTrue(json_schema.json_schema_check(doc, self.schema))
        self.assertEqual([], json_schema.json_schema_check(doc, weakened))

    def test_target_mismatch_is_invalid(self):
        doc = ta.build_anchor_set(TARGET, [{"kind": "git-commit", "repo": "r",
                                            "commit": "0" * 40}], self.schema)
        result = ta.verify_anchor_set(doc, "f" * 64, _policy(), {}, self.schema)
        self.assertEqual("invalid", result["facts"]["time_token"])
        self.assertTrue(any(i["code"] == "ANCHOR-TARGET-MISMATCH"
                            for i in result["issues"]))

    def test_missing_verifier_is_none_not_ok(self):
        doc = ta.build_anchor_set(TARGET, [{"kind": "git-commit", "repo": "r",
                                            "commit": "0" * 40}], self.schema)
        result = ta.verify_anchor_set(doc, TARGET, _policy(), {}, self.schema)
        self.assertEqual("none", result["facts"]["time_token"])
        self.assertEqual("none", result["details"][0]["status"])

    def test_unknown_tsa_root_is_none(self):
        doc = ta.build_anchor_set(TARGET, [{"kind": "rfc3161", "tsa": "nf:unknown",
                                            "token": "AAAA"}], self.schema)
        verifier = {"rfc3161": lambda i, d: {"ok": True}}
        result = ta.verify_anchor_set(doc, TARGET, _policy(), verifier, self.schema)
        self.assertEqual("none", result["facts"]["time_token"])
        self.assertEqual("TSA-ROOT-MISSING", result["details"][0]["reason"])


@NEED
class TimestampAnchorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.data = self.tmp / "head.bin"
        self.data.write_bytes(b"chain-head-payload")
        self.digest = hashlib.sha256(self.data.read_bytes()).hexdigest()
        self.query, self.token = _issue(self.tmp, self.data)
        self.ca = self.tmp / "ca.crt"
        self.root = {"id": "nf:test:tsa",
                     "digest": hashlib.sha256(self.ca.read_bytes()).hexdigest()}

    def tearDown(self):
        self._tmp.cleanup()

    def _anchors(self):
        return [{"kind": "rfc3161", "tsa": "nf:test:tsa",
                 "token": base64.b64encode(self.token.read_bytes()).decode()}]

    def _verifier(self, **kwargs):
        return ta.make_timestamp_verifier(str(self.query), str(self.ca),
                                          subject_path=str(self.data), **kwargs)

    def test_real_local_tsa_verifies_t2(self):
        doc = ta.build_anchor_set(self.digest, self._anchors())
        result = ta.verify_anchor_set(doc, self.digest, _policy(self.root),
                                      {"rfc3161": self._verifier()})
        self.assertEqual("ok", result["facts"]["time_token"], result)
        self.assertTrue(result["details"][0].get("gen_time"))

    def test_tampered_token_is_invalid(self):
        raw = bytearray(self.token.read_bytes())
        raw[-1] ^= 0xFF
        anchors = [{"kind": "rfc3161", "tsa": "nf:test:tsa",
                    "token": base64.b64encode(bytes(raw)).decode()}]
        doc = ta.build_anchor_set(self.digest, anchors)
        result = ta.verify_anchor_set(doc, self.digest, _policy(self.root),
                                      {"rfc3161": self._verifier()})
        self.assertEqual("invalid", result["facts"]["time_token"])

    def test_wrong_policy_root_digest_rejects(self):
        bad_root = {"id": "nf:test:tsa", "digest": "0" * 64}
        doc = ta.build_anchor_set(self.digest, self._anchors())
        verifier = self._verifier(policy_root_digest=bad_root["digest"])
        result = ta.verify_anchor_set(doc, self.digest, _policy(bad_root),
                                      {"rfc3161": verifier})
        self.assertEqual("invalid", result["facts"]["time_token"])
        self.assertEqual("TSA-ROOT-MISMATCH", result["details"][0]["reason"])

    def test_subject_digest_mismatch_rejects(self):
        doc = ta.build_anchor_set(self.digest, self._anchors())
        other = self.tmp / "other.bin"
        other.write_bytes(b"other")
        verifier = ta.make_timestamp_verifier(str(self.query), str(self.ca),
                                              subject_path=str(other))
        result = ta.verify_anchor_set(doc, self.digest, _policy(self.root),
                                      {"rfc3161": verifier})
        self.assertEqual("invalid", result["facts"]["time_token"])
        self.assertEqual("SUBJECT-DIGEST-MISMATCH", result["details"][0]["reason"])


class WitnessSthTest(unittest.TestCase):
    def test_transparency_with_witness_threshold(self):
        key = b"sth-key"
        w1, w2 = b"w1-key", b"w2-key"
        anchors = [_sth_anchor(key), _witness_anchor("nf:test:w1", "w1", w1),
                   _witness_anchor("nf:test:w2", "w2", w2)]
        doc = ta.build_anchor_set(TARGET, anchors)
        verifiers = {"transparency-sth": ta.make_sth_verifier({LOG_ID: _hmac_checker(key)}),
                     "witness": ta.make_witness_verifier({"nf:test:w1": _hmac_checker(w1),
                                                          "nf:test:w2": _hmac_checker(w2)})}
        ok = ta.verify_anchor_set(doc, TARGET, _policy(witness_threshold=2), verifiers)
        self.assertEqual("ok", ok["facts"]["transparency_sth"], ok)
        one = ta.verify_anchor_set(doc, TARGET, _policy(witness_threshold=1), verifiers)
        self.assertEqual("ok", one["facts"]["transparency_sth"])
        bad = ta.verify_anchor_set(doc, TARGET, _policy(witness_threshold=3), verifiers)
        self.assertEqual("none", bad["facts"]["transparency_sth"])
        self.assertTrue(any(i["code"] == "WITNESS-THRESHOLD-NOT-MET" for i in bad["issues"]))

    def test_bad_witness_or_sth_signature_is_invalid(self):
        key = b"sth-key"
        anchors = [_sth_anchor(key), _witness_anchor("nf:test:w1", "w1", b"wrong")]
        doc = ta.build_anchor_set(TARGET, anchors)
        verifiers = {"transparency-sth": ta.make_sth_verifier({LOG_ID: _hmac_checker(key)}),
                     "witness": ta.make_witness_verifier(
                         {"nf:test:w1": _hmac_checker(b"other")})}
        result = ta.verify_anchor_set(doc, TARGET, _policy(witness_threshold=1), verifiers)
        self.assertEqual("invalid", result["facts"]["transparency_sth"])

    def test_git_commit_exists_in_repo(self):
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              encoding="utf-8").stdout.strip()
        anchors = [{"kind": "git-commit", "repo": str(ROOT), "commit": head}]
        doc = ta.build_anchor_set(TARGET, anchors)
        result = ta.verify_anchor_set(doc, TARGET, _policy(),
                                      {"git-commit": ta.make_git_commit_verifier(str(ROOT))})
        self.assertEqual("ok", result["details"][0]["status"])
        self.assertEqual("none", result["facts"]["public_anchor"])


class VerifyIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", [
            {"id": "C1", "type": "evidence", "subject_digest": "b" * 64,
             "payload_digest": "c" * 64},
        ])

    def test_anchor_fact_checks_appear(self):
        anchor = ta.build_anchor_set(tc.digest_of(self.bundle),
                                     [{"kind": "git-commit", "repo": str(ROOT),
                                       "commit": "0" * 40}])
        result = tv.verify(self.bundle, _policy(), str(ROOT), anchor=anchor,
                           anchor_verifiers={"git-commit": lambda i, d: {"ok": True}})
        ids = [c["id"] for c in result["report"]["checks"]]
        self.assertIn("A2-anchor-facts", ids)
        detail = " ".join(c["detail"] for c in result["report"]["checks"])
        self.assertIn("time_token=none", detail)
        self.assertEqual(0, result["exit_code"], result)

    def test_anchor_target_mismatch_exits_invalid(self):
        anchor = ta.build_anchor_set("f" * 64, [{"kind": "git-commit", "repo": str(ROOT),
                                                 "commit": "0" * 40}])
        result = tv.verify(self.bundle, _policy(), str(ROOT), anchor=anchor,
                           anchor_verifiers={"git-commit": lambda i, d: {"ok": True}})
        self.assertEqual(1, result["exit_code"], result)
        self.assertTrue(any(i["code"] == "ANCHOR-TARGET-MISMATCH"
                            for i in result["report"]["issues"]))

    def test_missing_signature_still_blocks_t2(self):
        anchor = ta.build_anchor_set(tc.digest_of(self.bundle),
                                     [{"kind": "git-commit", "repo": str(ROOT),
                                       "commit": "0" * 40}])
        result = tv.verify(self.bundle, _policy(required="T2"), str(ROOT), anchor=anchor,
                           anchor_verifiers={"git-commit": lambda i, d: {"ok": True}})
        self.assertEqual(2, result["exit_code"], result)
        codes = [i["code"] for i in result["report"]["issues"]]
        self.assertIn("SIGNATURE-MISSING", codes)


class CliAnchorTest(unittest.TestCase):
    def test_build_and_verify_with_git_commit(self):
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              encoding="utf-8").stdout.strip()
        bundle = tb.build_bundle("b" * 64, "protocol/trust/claim-bundle.schema.json", [
            {"id": "C1", "type": "evidence", "subject_digest": "b" * 64,
             "payload_digest": "c" * 64},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bundle_path = base / "bundle.json"
            policy_path = base / "policy.json"
            anchors_path = base / "anchors.json"
            anchor_path = base / "anchor.json"
            bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
            policy_path.write_text(json.dumps(_policy()), encoding="utf-8")
            anchors_path.write_text(json.dumps([{"kind": "git-commit", "repo": str(ROOT),
                                                 "commit": head}]), encoding="utf-8")
            build = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--anchor-build", str(anchor_path),
                 "--anchor-target", tc.digest_of(bundle),
                 "--anchor-anchors", str(anchors_path)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, build.returncode, build.stderr + build.stdout)
            verify = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                 "--bundle", str(bundle_path), "--policy", str(policy_path),
                 "--anchor", str(anchor_path), "--git-repo", str(ROOT),
                 "--root", str(ROOT)],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
            self.assertIn("A2-anchor-details", verify.stdout)


if __name__ == "__main__":
    unittest.main()
