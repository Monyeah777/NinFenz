#!/usr/bin/env python3
"""trust.keys 判据：issuer registry 结构/语义 + 生命周期解析 + 注册表口径验签。

为什么有它：ADR-009 要求「未知 issuer/keyid/算法一律拒」。本件把注册表体检（唯一性、
时间窗、轮换可寻址、吊销字段）、resolve_keyid 的生命周期矩阵、以及「密码学上签名有效但
key 已吊销/过期/未来生效必须整体拒」逐条置红——这是 WP-21 的验收面。
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
from core.trust import dsse, keys  # noqa: E402

KEY = b"registry-hmac-key-0123456789abcdef"
KEYID = "nf:test:hmac:2026"
ISSUER = "nf:test:issuer"
NOW = "2026-11-14T00:00:00Z"
MATERIAL = {KEYID: {"hex": KEY.hex()}}


def _key(keyid=KEYID, alg="hmac-sha256", status="active",
         not_before="2026-01-01T00:00:00Z", not_after="2027-01-01T00:00:00Z", **extra):
    item = {"keyid": keyid, "alg": alg, "status": status,
            "not_before": not_before, "not_after": not_after}
    item.update(extra)
    return item


def _registry(keys_list=None, issuer_id=ISSUER, kind="service", **issuer_extra):
    issuer = {"id": issuer_id, "kind": kind,
              "keys": [_key()] if keys_list is None else keys_list}
    issuer.update(issuer_extra)
    return {"schema": "nf-issuer-registry/1", "issuers": [issuer]}


def _envelope(keyid=KEYID, key=KEY):
    return dsse.sign_envelope("application/vnd.nf.claim-bundle+json", b'{"schema":"x"}', [
        {"keyid": keyid, "sign": lambda data: dsse.hmac_sign(key, data)},
    ])


class RegistrySchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = keys.load_schema(str(ROOT))

    def test_schema_const(self):
        self.assertEqual("nf-issuer-registry/1",
                         self.schema["properties"]["schema"]["const"])

    def test_valid_registry(self):
        issues, stats = keys.validate_registry(_registry(), self.schema)
        self.assertEqual([], issues)
        self.assertEqual({"issuers": 1, "keys": 1, "active": 1, "retired": 0, "revoked": 0},
                         stats)
        self.assertEqual([], json_schema.json_schema_check(_registry(), self.schema))

    def test_structural_rejections(self):
        bad = _registry()
        bad["unexpected"] = 1
        self.assertTrue(json_schema.json_schema_check(bad, self.schema))
        bad = _registry(keys_list=[])
        self.assertTrue(json_schema.json_schema_check(bad, self.schema))
        bad = _registry(keys_list=[_key(alg="rsa-1024")])
        self.assertTrue(json_schema.json_schema_check(bad, self.schema))
        bad = _registry(keys_list=[_key(status="broken")])
        self.assertTrue(json_schema.json_schema_check(bad, self.schema))
        bad = _registry(keys_list=[_key(not_before="2026-01-01")])
        self.assertTrue(json_schema.json_schema_check(bad, self.schema))

    def test_semantic_rejections(self):
        cases = {
            "duplicate keyid": _registry(keys_list=[_key(), _key()]),
            "duplicate issuer": {"schema": "nf-issuer-registry/1",
                                 "issuers": [_registry()["issuers"][0],
                                             _registry()["issuers"][0]]},
            "time reversed": _registry(keys_list=[_key(not_before="2027-02-01T00:00:00Z")]),
            "retired without rotation": _registry(keys_list=[_key(status="retired")]),
            "rotated ghost": _registry(keys_list=[_key(status="retired",
                                                       rotated_to="nf:test:hmac:9999")]),
            "revoked without fields": _registry(keys_list=[_key(status="revoked")]),
            "active with revocation": _registry(keys_list=[_key(revoked_at=NOW)]),
            "delegated ghost": _registry(delegated_by="nf:test:ghost"),
        }
        for label, doc in cases.items():
            issues, _stats = keys.validate_registry(doc)
            self.assertTrue(issues, f"{label} 未被拒")
        self.assertTrue(any("rotated_to" in i for i in keys.validate_registry(
            _registry(keys_list=[_key(status="retired")]))[0]))

    def test_rotation_chain_passes(self):
        doc = _registry(keys_list=[
            _key(status="retired", rotated_to="nf:test:hmac:2027"),
            _key(keyid="nf:test:hmac:2027"),
        ])
        self.assertEqual([], keys.validate_registry(doc)[0])
        doc2 = _registry(delegated_by="nf:delegator:root")
        doc2["issuers"].append({"id": "nf:delegator:root", "kind": "institution",
                                "keys": [_key(keyid="nf:delegator:hmac:2026")]})
        self.assertEqual([], keys.validate_registry(doc2)[0])


class ResolveTest(unittest.TestCase):
    def test_active_ok(self):
        got = keys.resolve_keyid(_registry(), KEYID, NOW)
        self.assertTrue(got["ok"], got)
        self.assertEqual(ISSUER, got["issuer"])

    def test_lifecycle_matrix(self):
        checks = [
            (_registry(keys_list=[_key(status="revoked", revoked_at=NOW,
                                       revocation_reason="key compromise")]),
             NOW, "KEY-REVOKED"),
            (_registry(), "2027-02-01T00:00:00Z", "KEY-EXPIRED"),
            (_registry(), "2025-01-01T00:00:00Z", "KEY-NOT-YET-VALID"),
            (_registry(keys_list=[_key(keyid="nf:test:hmac:9999")]), NOW, "KEY-UNKNOWN"),
        ]
        for doc, moment, reason in checks:
            got = keys.resolve_keyid(doc, KEYID, moment)
            self.assertFalse(got["ok"], got)
            self.assertEqual(reason, got["reason"])

    def test_retired_is_parseable_but_flagged(self):
        doc = _registry(keys_list=[_key(status="retired", rotated_to="nf:test:hmac:2027"),
                                   _key(keyid="nf:test:hmac:2027")])
        got = keys.resolve_keyid(doc, KEYID, NOW)
        self.assertTrue(got["ok"], got)
        self.assertTrue(got["retired"])


class RegistryVerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = dsse.load_schema(str(ROOT))

    def verify(self, doc, envelope, material=None, now=NOW):
        return keys.verify_envelope(envelope, doc,
                                    MATERIAL if material is None else material,
                                    self.schema, now)

    def test_valid_envelope_with_issuer(self):
        result = self.verify(_registry(), _envelope())
        self.assertTrue(result["valid"], result)
        self.assertEqual({KEYID: ISSUER}, result["issuers"])
        self.assertEqual(b'{"schema":"x"}', result["payload"])

    def test_revoked_key_rejects_despite_valid_signature(self):
        doc = _registry(keys_list=[_key(status="revoked", revoked_at=NOW,
                                       revocation_reason="key compromise")])
        result = self.verify(doc, _envelope())
        self.assertFalse(result["valid"], result)
        self.assertEqual("KEY-REVOKED", result["reason"])

    def test_expired_and_future_reject(self):
        self.assertEqual("KEY-EXPIRED", self.verify(_registry(), _envelope(),
                                                    now="2027-02-01T00:00:00Z")["reason"])
        self.assertEqual("KEY-NOT-YET-VALID", self.verify(_registry(), _envelope(),
                                                         now="2025-01-01T00:00:00Z")["reason"])

    def test_unknown_keyid_rejects(self):
        result = self.verify(_registry(keys_list=[_key(keyid="nf:test:hmac:9999")]),
                             _envelope())
        self.assertEqual("KEY-UNKNOWN", result["reason"])

    def test_material_missing_and_invalid(self):
        self.assertEqual("KEY-MATERIAL-MISSING",
                         self.verify(_registry(), _envelope(), material={})["reason"])
        bad = {KEYID: {"hex": "zz"}}
        self.assertEqual("KEY-MATERIAL-INVALID",
                         self.verify(_registry(), _envelope(), material=bad)["reason"])

    def test_retired_key_still_verifies_history(self):
        doc = _registry(keys_list=[_key(status="retired", rotated_to="nf:test:hmac:2027"),
                                   _key(keyid="nf:test:hmac:2027")])
        result = self.verify(doc, _envelope())
        self.assertTrue(result["valid"], result)
        self.assertEqual([KEYID], result["retired"])

    def test_rotation_new_key_signs(self):
        new_key = b"new-key-0000000000000000000000000"
        doc = _registry(keys_list=[_key(status="retired", rotated_to="nf:test:hmac:2027"),
                                   _key(keyid="nf:test:hmac:2027")])
        material = {KEYID: {"hex": KEY.hex()},
                    "nf:test:hmac:2027": {"hex": new_key.hex()}}
        envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"new", [
            {"keyid": "nf:test:hmac:2027", "sign": lambda data: dsse.hmac_sign(new_key, data)},
        ])
        result = self.verify(doc, envelope, material)
        self.assertTrue(result["valid"], result)
        self.assertEqual([], result["retired"])

    def test_tampered_payload_still_red(self):
        bad = copy.deepcopy(_envelope())
        bad["payload"] = base64.b64encode(b"tampered").decode()
        self.assertEqual("SIGNATURE-INVALID", self.verify(_registry(), bad)["reason"])

    def test_invalid_registry_rejects(self):
        result = self.verify({"schema": "nf-issuer-registry/1", "issuers": []}, _envelope())
        self.assertEqual("REGISTRY-INVALID", result["reason"])


class CliRegistryTest(unittest.TestCase):
    def _files(self, tmp, doc, envelope):
        base = Path(tmp)
        reg = base / "registry.json"
        mat = base / "material.json"
        env = base / "envelope.json"
        reg.write_text(json.dumps(doc), encoding="utf-8")
        mat.write_text(json.dumps(MATERIAL), encoding="utf-8")
        env.write_text(json.dumps(envelope), encoding="utf-8")
        return reg, mat, env

    def _run(self, reg, mat, env):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                               "--envelope", str(env), "--issuer-registry", str(reg),
                               "--key-material", str(mat), "--now", NOW, "--root", str(ROOT)],
                              capture_output=True, text=True, encoding="utf-8")

    def test_cli_valid_and_revoked(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg, mat, env = self._files(tmp, _registry(), _envelope())
            ok = self._run(reg, mat, env)
            self.assertEqual(0, ok.returncode, ok.stderr + ok.stdout)
            self.assertIn("valid envelope", ok.stdout)
            revoked = _registry(keys_list=[_key(status="revoked", revoked_at=NOW,
                                                revocation_reason="compromise")])
            reg, mat, env = self._files(tmp, revoked, _envelope())
            bad = self._run(reg, mat, env)
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("KEY-REVOKED", bad.stdout)


if __name__ == "__main__":
    unittest.main()
