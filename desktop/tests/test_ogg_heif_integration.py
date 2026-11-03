"""OGG / HEIF 写入 → 体检 端到端测试（CLI）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core.labeling import metadata, sm


class TestOggHeif(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.keys = sm.sm2_keygen()
        self.meta = os.path.join(self.td, "m.json")
        with open(self.meta, "w", encoding="utf-8") as f:
            json.dump({"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "NF-OH-1"}, f)

    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nf_labeling.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def _sign_check(self, kind, maker):
        p = os.path.join(self.td, "a." + kind)
        maker(p)
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("回退 sidecar", r.stderr + r.stdout)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["verdict"], "PASS", rep)
        return rep

    def test_ogg(self):
        rep = self._sign_check("ogg", metadata.make_ogg)
        self.assertEqual(rep["meta_found_at"], "ogg.comment")

    def test_heif(self):
        rep = self._sign_check("heif", metadata.make_heif)
        self.assertEqual(rep["meta_found_at"], "heif.item")

    def test_ogg_audio_tamper_fails_binding(self):
        p = os.path.join(self.td, "b.ogg")
        metadata.make_ogg(p)
        self._run("sign", p, "--meta", self.meta, "--priv", self.keys["private"])
        data = bytearray(open(p, "rb").read())
        idx = data.find(b"OGG-AUDIO-FRAMES")
        data[idx] ^= 0x01
        with open(p, "wb") as f:
            f.write(data)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")

    def test_heif_primary_tamper_fails_binding(self):
        p = os.path.join(self.td, "b.heif")
        metadata.make_heif(p)
        self._run("sign", p, "--meta", self.meta, "--priv", self.keys["private"])
        data = bytearray(open(p, "rb").read())
        idx = data.find(b"HEIF-PRIMARY-IMAGE")
        data[idx] ^= 0x01
        with open(p, "wb") as f:
            f.write(data)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
