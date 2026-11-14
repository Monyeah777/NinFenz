#!/usr/bin/env python3
"""key_material 判据：HMAC keygen（0600/不覆盖/不跟随符号链接）+ 读入校验。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.trust import dsse  # noqa: E402
from core.trust import key_material as km  # noqa: E402


class GenerateTest(unittest.TestCase):
    def test_generate_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "key.hex"
            meta = km.generate_hmac_key(str(path))
            self.assertEqual("hmac-sha256", meta["alg"])
            self.assertEqual(32, meta["bytes"])
            text = path.read_text(encoding="ascii").strip()
            self.assertEqual(64, len(text))
            self.assertEqual(meta["bytes"], len(km.load_hmac_key(str(path))))

    def test_refuses_overwrite_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key.hex"
            km.generate_hmac_key(str(path))
            with self.assertRaises(ValueError):
                km.generate_hmac_key(str(path))
            link = Path(tmp) / "link.hex"
            try:
                os.symlink(path, link)
            except (OSError, NotImplementedError):
                self.skipTest("平台不支持创建符号链接")
            with self.assertRaises(ValueError):
                km.generate_hmac_key(str(link))
            with self.assertRaises(ValueError):
                km.load_hmac_key(str(link))

    @unittest.skipUnless(os.name == "posix", "POSIX 才可断言 0600 位")
    def test_posix_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key.hex"
            km.generate_hmac_key(str(path))
            self.assertTrue(km.check_permissions(str(path))["ok"])
            os.chmod(str(path), 0o644)
            perms = km.check_permissions(str(path))
            self.assertFalse(perms["ok"])
            self.assertEqual("KEY-PERMISSIONS", perms["reason"])
            with self.assertRaises(ValueError):
                km.load_hmac_key(str(path))

    def test_bad_material_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key.hex"
            path.write_text("zz" * 32 + "\n", encoding="ascii")
            with self.assertRaises(ValueError):
                km.load_hmac_key(str(path))
            path.write_text("00" * 16 + "\n", encoding="ascii")
            with self.assertRaises(ValueError):
                km.load_hmac_key(str(path))
            path.write_text("00" * 5000 + "\n", encoding="ascii")
            with self.assertRaises(ValueError):
                km.load_hmac_key(str(path))

    def test_generated_key_signs_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key.hex"
            km.generate_hmac_key(str(path))
            key = km.load_hmac_key(str(path))
            envelope = dsse.sign_envelope("application/vnd.nf.text+utf8", b"hi", [
                {"keyid": "nf:test:hmac:2026",
                 "sign": lambda data: dsse.hmac_sign(key, data)}])
            result = dsse.verify_envelope(envelope, {"nf:test:hmac:2026": {
                "alg": "hmac-sha256", "verify": dsse.hmac_verifier(key)}})
            self.assertTrue(result["valid"], result)

    def test_cli_keygen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "key.hex"
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "trust_keygen.py"),
                                   "--out", str(path)],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(0, proc.returncode, proc.stderr)
            meta = json.loads(proc.stdout)
            self.assertEqual("hmac-sha256", meta["alg"])
            self.assertEqual(32, len(km.load_hmac_key(str(path))))


if __name__ == "__main__":
    unittest.main()
