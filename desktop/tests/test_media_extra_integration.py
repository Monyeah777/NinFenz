"""TIFF/GIF/WebP/WAV/MP3/FLAC 写入 → 体检 端到端测试（CLI）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core.labeling import metadata, sm


class TestMediaExtra(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.keys = sm.sm2_keygen()
        self.meta = os.path.join(self.td, "m.json")
        with open(self.meta, "w", encoding="utf-8") as f:
            json.dump({"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "NF-MX-1"}, f)

    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nf_labeling.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def _sign_check(self, kind, maker):
        p = os.path.join(self.td, "a." + kind)
        maker(p)
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["verdict"], "PASS", rep)
        return rep

    def test_tiff(self):
        rep = self._sign_check("tiff", metadata.make_tiff)
        self.assertEqual(rep["meta_found_at"], "tiff.IFD0")

    def test_gif(self):
        rep = self._sign_check("gif", metadata.make_gif)
        self.assertEqual(rep["meta_found_at"], "gif.XMP")

    def test_webp(self):
        rep = self._sign_check("webp", metadata.make_webp)
        self.assertEqual(rep["meta_found_at"], "webp.XMP")

    def test_wav(self):
        rep = self._sign_check(
            "wav", lambda p: metadata.make_wav_with_info(p, {"ISFT": "nf"}))
        self.assertEqual(rep["meta_found_at"], "wav.AIGC")

    def test_mp3(self):
        rep = self._sign_check(
            "mp3", lambda p: metadata.make_mp3_with_txxx(p, "x", "y"))
        self.assertEqual(rep["meta_found_at"], "mp3.id3.TXXX")

    def test_flac(self):
        rep = self._sign_check("flac", metadata.make_flac)
        self.assertEqual(rep["meta_found_at"], "flac.VORBIS")

    def test_tiff_strip_tamper_fails_binding(self):
        p = os.path.join(self.td, "b.tiff")
        metadata.make_tiff(p)
        self._run("sign", p, "--meta", self.meta, "--priv", self.keys["private"])
        data = bytearray(open(p, "rb").read())
        idx = data.find(b"TIFF-IMAGE-DATA")
        data[idx] ^= 0x01
        with open(p, "wb") as f:
            f.write(data)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
