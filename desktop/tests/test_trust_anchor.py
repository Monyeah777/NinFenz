"""信任锚判据：根 → 委派链 → 吊销 feed 的公钥归属。

要挡的攻击很具体：**换一把公钥重签 feed**，验证方如果只验签名就会被骗。判据必须证明
「未被信任根覆盖的公钥一律不认」，以及「委派有界、有过期、签名被改就不认」。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ed25519, revocations, trust_anchor  # noqa: E402

ROOT_SEED = bytes(range(32))
MID_SEED = bytes(range(32, 64))
ORG_SEED = bytes(range(64, 96))
STRANGER_SEED = bytes(range(96, 128))
FUTURE = "2027-01-01T00:00:00Z"
PAST = "2026-01-01T00:00:00Z"


def _pub(seed: bytes) -> bytes:
    return ed25519.public_key(seed)


def _delegation(issuer_seed: bytes, subject_seed: bytes, expires_at: str = FUTURE):
    item, err = trust_anchor.make_delegation(issuer_seed, _pub(subject_seed), expires_at)
    assert not err, err
    return item


class ManifestShapeTest(unittest.TestCase):
    def test_bad_schema_is_rejected(self):
        res = trust_anchor.anchor({"schema": "nope", "roots": []}, _pub(ORG_SEED))
        self.assertFalse(res["ok"])
        self.assertIn("schema", res["issues"][0])

    def test_manifest_without_roots_cannot_anchor(self):
        res = trust_anchor.anchor({"schema": trust_anchor.SCHEMA, "roots": [],
                                   "delegations": []}, _pub(ROOT_SEED))
        self.assertFalse(res["ok"])
        self.assertIn("roots", res["issues"][0])


class AnchorChainTest(unittest.TestCase):
    def test_root_anchors_itself(self):
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)])
        res = trust_anchor.anchor(manifest, _pub(ROOT_SEED))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual("root-1", res["root"])
        self.assertEqual(["root-1"], res["path"])

    def test_one_hop_delegation(self):
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)], [_delegation(ROOT_SEED, ORG_SEED)])
        res = trust_anchor.anchor(manifest, _pub(ORG_SEED))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(2, len(res["path"]))

    def test_two_hop_delegation_is_allowed(self):
        manifest = trust_anchor.make_manifest(
            [_pub(ROOT_SEED)],
            [_delegation(ROOT_SEED, MID_SEED), _delegation(MID_SEED, ORG_SEED)])
        res = trust_anchor.anchor(manifest, _pub(ORG_SEED))
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(3, len(res["path"]))

    def test_chain_beyond_depth_is_rejected(self):
        manifest = trust_anchor.make_manifest(
            [_pub(ROOT_SEED)],
            [_delegation(ROOT_SEED, MID_SEED), _delegation(MID_SEED, _pub(ORG_SEED) and ORG_SEED),
             _delegation(ORG_SEED, STRANGER_SEED)])
        res = trust_anchor.anchor(manifest, _pub(STRANGER_SEED))
        self.assertFalse(res["ok"], "深度上限 3 必须真的挡住")

    def test_unanchored_key_is_rejected_with_guide(self):
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)])
        res = trust_anchor.anchor(manifest, _pub(STRANGER_SEED))
        self.assertFalse(res["ok"])
        self.assertIn("修复指引", " ".join(res["issues"]))

    def test_expired_delegation_is_rejected(self):
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)],
                                              [_delegation(ROOT_SEED, ORG_SEED, PAST)])
        res = trust_anchor.anchor(manifest, _pub(ORG_SEED), at="2026-06-01T00:00:00Z")
        self.assertFalse(res["ok"])
        self.assertTrue(any("过期" in i for i in res["issues"]), res["issues"])

    def test_tampered_delegation_signature_is_rejected(self):
        item = _delegation(ROOT_SEED, ORG_SEED)
        bad = dict(item)
        bad["subject"] = _pub(STRANGER_SEED).hex()
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)], [bad])
        res = trust_anchor.anchor(manifest, _pub(STRANGER_SEED))
        self.assertFalse(res["ok"])
        self.assertTrue(any("委派签名不匹配" in i for i in res["issues"]), res["issues"])

    def test_wrong_scope_is_rejected(self):
        item = _delegation(ROOT_SEED, ORG_SEED)
        item["scope"] = "documents"
        manifest = trust_anchor.make_manifest([_pub(ROOT_SEED)], [item])
        res = trust_anchor.anchor(manifest, _pub(ORG_SEED))
        self.assertFalse(res["ok"])

    def test_delegation_requires_expiry(self):
        _item, err = trust_anchor.make_delegation(ROOT_SEED, _pub(ORG_SEED), "")
        self.assertIn("修复指引", err)


class FeedTrustTest(unittest.TestCase):
    """吊销 feed 的信任面：签名自洽 + 公钥归属，两件事都必须成立。"""

    def _feed(self):
        table = revocations.make_table([{"digest": "a" * 64, "reason": "demo"}])
        return revocations.sign(table, ORG_SEED, issuer="org-a", seq=1,
                                scheme=revocations.ALG_ED25519,
                                issued_at="2026-11-07T00:00:00Z")

    def test_feed_verifies_and_reports_root_when_trusted(self):
        trust = trust_anchor.make_manifest([_pub(ROOT_SEED)], [_delegation(ROOT_SEED, ORG_SEED)])
        res = revocations.verify(self._feed(), key=_pub(ORG_SEED), trust=trust)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual("root-1", res["trust_root"])
        self.assertEqual(2, len(res["trust_path"]))

    def test_untrusted_key_is_invalid(self):
        trust = trust_anchor.make_manifest([_pub(ROOT_SEED)])
        res = revocations.verify(self._feed(), key=_pub(ORG_SEED), trust=trust)
        self.assertFalse(res["ok"])
        self.assertTrue(any("信任根" in i for i in res["issues"]), res["issues"])

    def test_requires_trust_when_asked(self):
        res = revocations.verify(self._feed(), key=_pub(ORG_SEED), require_trust=True)
        self.assertFalse(res["ok"])
        self.assertIn("信任锚", res["issues"][0])

    def test_honest_warning_without_trust(self):
        res = revocations.verify(self._feed(), key=_pub(ORG_SEED))
        self.assertTrue(res["ok"])
        self.assertTrue(any("不证明这把公钥属于谁" in w for w in res["warnings"]))


class TrustCliTest(unittest.TestCase):
    def test_grant_then_verify_with_trust(self):
        import json
        import subprocess
        import tempfile

        nf = sys.executable, str(ROOT / "scripts" / "nf.py")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "root.seed").write_bytes(ROOT_SEED)
            (tmp / "org.seed").write_bytes(ORG_SEED)
            (tmp / "org.pub").write_bytes(_pub(ORG_SEED))
            table = revocations.make_table([{"digest": "a" * 64}])
            (tmp / "table.json").write_text(json.dumps(table), encoding="utf-8")
            grant = subprocess.run([*nf, "evidence", "revocations", "trust", "grant",
                                    str(tmp / "root.seed"), "--subject-pub",
                                    _pub(ORG_SEED).hex(), "--expires-at", FUTURE, "--root",
                                    "--trust", str(tmp / "trust.json"),
                                    "--out", str(tmp / "trust.json")],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=180)
            self.assertEqual(0, grant.returncode, grant.stderr[-400:])
            sign = subprocess.run([*nf, "evidence", "revocations", "sign", "--table",
                                   str(tmp / "table.json"), "--key-file", str(tmp / "org.seed"),
                                   "--scheme", "ed25519", "--seq", "1",
                                   "--out", str(tmp / "feed.json")],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, sign.returncode, sign.stderr[-400:])
            verify = subprocess.run([*nf, "evidence", "revocations", "verify",
                                     str(tmp / "feed.json"), "--key-file", str(tmp / "org.pub"),
                                     "--trust", str(tmp / "trust.json"), "--json"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=180)
            self.assertEqual(0, verify.returncode, verify.stderr[-400:])
            doc = json.loads(verify.stdout)
            self.assertTrue(doc["ok"])
            self.assertEqual("root-1", doc["trust_root"])


if __name__ == "__main__":
    unittest.main()
