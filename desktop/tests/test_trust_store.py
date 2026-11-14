#!/usr/bin/env python3
"""trust_store 判据：policy × issuer registry × type registry 装配一致性。"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import trust_store as tstore  # noqa: E402

ISSUER = "nf:test:issuer"
KEYID = "nf:test:hmac:2026"
NOW = "2026-11-14T00:00:00Z"


def _policy(alg="hmac-sha256", types=("claim",)):
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": alg,
                         "types": list(types)}],
            "algorithms": ["hmac-sha256"], "tsa_roots": [], "required_level": "T0",
            "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}


def _registry(kind="service", alg="hmac-sha256", keyid=KEYID, issuer=ISSUER):
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": issuer, "kind": kind,
                         "keys": [{"keyid": keyid, "alg": alg, "status": "active",
                                   "not_before": "2026-01-01T00:00:00Z",
                                   "not_after": "2027-01-01T00:00:00Z"}]}]}


def _types(kind=("service", "institution")):
    return {"schema": "nf-type-registry/1", "types": [
        {"id": "claim", "allowed_issuer_kinds": list(kind),
         "allowed_ref_kinds": ["evidence"], "compose_with": [], "max_refs": 4}]}


class BuildStoreTest(unittest.TestCase):
    def test_valid_store(self):
        store = tstore.build_store(_policy(), _registry(), _types())
        self.assertEqual([ISSUER], list(store["issuers"]))
        self.assertEqual(KEYID, store["issuers"][ISSUER]["keyid"])
        self.assertIn("claim", store["types"])
        self.assertEqual([], tstore.build_store_issues(_policy(), _registry(), _types()))

    def test_registration_mismatches(self):
        cases = {
            "issuer-missing": (_policy(), _registry(issuer="nf:other:issuer"), _types()),
            "keyid-missing": (_policy(), _registry(keyid="nf:test:hmac:1999"), _types()),
            "alg-mismatch": (_policy("hmac-sha256"), _registry(alg="ed25519"), _types()),
            "alg-not-whitelisted": (_policy("ed25519"), _registry(alg="ed25519"), _types()),
            "type-unregistered": (_policy(types=("planet",)), _registry(), _types()),
            "kind-not-allowed": (_policy(), _registry(kind="ai-agent"), _types(kind=("service",))),
        }
        for label, (policy, registry, types) in cases.items():
            self.assertTrue(tstore.build_store_issues(policy, registry, types),
                            f"{label} 未被拒")
            with self.assertRaises(ValueError):
                tstore.build_store(policy, registry, types)

    def test_lookup_keyid(self):
        store = tstore.build_store(_policy(), _registry(), _types())
        got = tstore.lookup_keyid(store, KEYID, NOW, _registry())
        self.assertTrue(got["ok"], got)
        self.assertEqual(ISSUER, got["issuer_id"])
        self.assertEqual("KEY-UNKNOWN",
                         tstore.lookup_keyid(store, "nf:test:hmac:1999", NOW,
                                             _registry())["reason"])
        self.assertEqual("REGISTRY-REQUIRED",
                         tstore.lookup_keyid(store, KEYID)["reason"])
        self.assertEqual("KEY-NOT-IN-STORE",
                         tstore.lookup_keyid({"keyids": {}}, KEYID, NOW,
                                             _registry())["reason"])

    def test_cli_trust_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {"policy.json": _policy(), "issuers.json": _registry(),
                     "types.json": _types()}
            for name, doc in files.items():
                (base / name).write_text(json.dumps(doc), encoding="utf-8")
            base_cmd = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                        "--trust-store", "--policy", str(base / "policy.json"),
                        "--issuer-registry", str(base / "issuers.json"),
                        "--type-registry", str(base / "types.json"),
                        "--root", str(ROOT)]
            ok = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            self.assertIn("valid trust store", ok.stdout)
            (base / "policy.json").write_text(
                json.dumps(_policy(types=("planet",))), encoding="utf-8")
            bad = subprocess.run(base_cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(1, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("invalid trust store", bad.stdout)


if __name__ == "__main__":
    unittest.main()
