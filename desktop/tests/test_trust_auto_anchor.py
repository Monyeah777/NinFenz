#!/usr/bin/env python3
"""auto-anchor 编排判据：先验链头 → 组装 nf-anchor/1；错头/空组件/坏组件必须拒。"""
import json
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

KEY = b"auto-anchor-key-0123456789abcdef"
KEYID = "nf:test:hmac:2026"
ISSUER = "nf:test:issuer"
NOW = "2026-11-14T00:00:00Z"


def _bundle():
    return tb.build_bundle("a" * 64, "protocol/trust/claim-bundle.schema.json", [
        {"id": "A1", "type": "evidence", "subject_digest": "b" * 64,
         "payload_digest": "c" * 64}])


def _registry():
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": "service",
                         "keys": [{"keyid": KEYID, "alg": "hmac-sha256",
                                   "status": "active",
                                   "not_before": "2026-01-01T00:00:00Z",
                                   "not_after": "2027-01-01T00:00:00Z"}]}]}


def _material():
    return {KEYID: {"hex": KEY.hex()}}


def _head(digest):
    return tsig.sign_head("bundle", digest,
                          [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(KEY, data)}],
                          root=str(ROOT))


def _components():
    return [{"kind": "git-commit", "repo": ".", "commit": "0" * 40}]


class AutoAnchorTest(unittest.TestCase):
    def test_auto_anchor_with_verified_head(self):
        bundle = _bundle()
        digest = tc.digest_of(bundle)
        doc = ta.auto_anchor(digest, _components(), root=str(ROOT), head=_head(digest),
                             registry=_registry(), material=_material(), now=NOW)
        self.assertEqual(digest, doc["target_digest"])
        self.assertEqual(1, len(doc["anchors"]))
        self.assertEqual([], ta.load_schema(str(ROOT)).get("problems") or [])

    def test_head_mismatch_refused(self):
        bundle = _bundle()
        digest = tc.digest_of(bundle)
        with self.assertRaises(ValueError) as ctx:
            ta.auto_anchor(digest, _components(), root=str(ROOT),
                           head=_head("f" * 64), registry=_registry(),
                           material=_material(), now=NOW)
        self.assertIn("AUTO-ANCHOR-HEAD-INVALID", str(ctx.exception))

    def test_head_without_context_refused(self):
        digest = tc.digest_of(_bundle())
        with self.assertRaises(ValueError) as ctx:
            ta.auto_anchor(digest, _components(), root=str(ROOT), head=_head(digest))
        self.assertIn("AUTO-ANCHOR-HEAD-CONTEXT-MISSING", str(ctx.exception))

    def test_empty_or_invalid_components_refused(self):
        digest = tc.digest_of(_bundle())
        with self.assertRaises(ValueError):
            ta.auto_anchor(digest, [], root=str(ROOT))
        with self.assertRaises(ValueError):
            ta.auto_anchor(digest, [{"kind": "magic"}], root=str(ROOT))

    def test_cli_auto_anchor(self):
        bundle = _bundle()
        digest = tc.digest_of(bundle)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {"head.json": _head(digest), "registry.json": _registry(),
                     "material.json": _material(), "components.json": _components()}
            for name, doc in files.items():
                (base / name).write_text(json.dumps(doc), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "scripts" / "trust_verify.py"),
                   "--auto-anchor", str(base / "anchor.json"),
                   "--subject-digest", digest,
                   "--anchor-components", str(base / "components.json"),
                   "--head-signature", str(base / "head.json"),
                   "--issuer-registry", str(base / "registry.json"),
                   "--key-material", str(base / "material.json"),
                   "--now", NOW, "--root", str(ROOT)]
            ok = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
            doc = json.loads((base / "anchor.json").read_text(encoding="utf-8"))
            self.assertEqual(digest, doc["target_digest"])
            (base / "head.json").write_text(json.dumps(_head("f" * 64)), encoding="utf-8")
            bad = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(2, bad.returncode, bad.stdout + bad.stderr)
            self.assertIn("AUTO-ANCHOR-HEAD-INVALID", bad.stderr)


if __name__ == "__main__":
    unittest.main()
