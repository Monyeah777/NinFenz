#!/usr/bin/env python3
"""公共锚 live 证据判据：对已提交的 Rekor 真实条目做离线复验（openssl ECDSA SET）。"""
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import public_anchor as pua  # noqa: E402

ENTRY = ROOT / "results" / "trust" / "PUBLIC_ANCHOR_LIVE.json"
PEM = ROOT / "results" / "trust" / "rekor-public-key.pem"
LOG_ID = "c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d"
TARGET = "45c7b11fcbf07dec1694adecd8c5b85770a12a6c8dfdcf2580a2db0c47c31779"
OPENSSL = shutil.which("openssl")
NEED = unittest.skipUnless(OPENSSL, "环境无 openssl：live SET 验签跳过（不冒充已验）")


@NEED
class PublicAnchorLiveTest(unittest.TestCase):
    def test_real_rekor_entry_verifies_offline(self):
        doc = pua.load_public_anchor(str(ENTRY))
        verifier = pua.make_openssl_verifier(str(PEM))
        result = pua.verify_public_anchor(doc, verifier, LOG_ID, TARGET)
        self.assertTrue(result["ok"], result)
        self.assertEqual(TARGET, result["target_digest"])
        self.assertGreaterEqual(result["tree_size"], 1)

    def test_wrong_target_or_log_is_rejected(self):
        doc = pua.load_public_anchor(str(ENTRY))
        verifier = pua.make_openssl_verifier(str(PEM))
        self.assertEqual("PUBLIC-ANCHOR-TARGET-MISMATCH",
                         pua.verify_public_anchor(doc, verifier, LOG_ID, "f" * 64)["reason"])
        self.assertEqual("PUBLIC-ANCHOR-LOG-MISMATCH",
                         pua.verify_public_anchor(doc, verifier, "f" * 64, TARGET)["reason"])


if __name__ == "__main__":
    unittest.main()
