"""JPEG/PDF/MP4 写入 → 体检 的端到端测试（CLI 路径）。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core.labeling import metadata, sm


class TestMediaContainers(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.keys = sm.sm2_keygen()
        with open(os.path.join(self.td, "k.json"), "w") as f:
            json.dump(self.keys, f)
        self.meta = os.path.join(self.td, "m.json")
        with open(self.meta, "w") as f:
            json.dump({"Label": 1, "ContentProducer": "1" * 27,
                       "ProduceID": "NF-MEDIA-1"}, f)

    def _run(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "nf_labeling.py"), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def _sign_check(self, kind, maker):
        p = os.path.join(self.td, "x." + kind)
        maker(p, "<x/>")
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["verdict"], "PASS", rep)
        self.assertEqual(rep["sections"]["C"]["status"], "PASS")
        self.assertEqual(r.returncode, 0)

    def test_jpeg(self):
        self._sign_check("jpeg", metadata.make_jpeg_with_xmp)

    def test_pdf(self):
        self._sign_check("pdf", metadata.make_pdf_with_xmp)

    def test_mp4(self):
        self._sign_check("mp4", metadata.make_mp4_with_xmp)

    def test_jpeg_content_tamper_fails(self):
        p = os.path.join(self.td, "x.jpeg")
        metadata.make_jpeg_with_xmp(p, "<x/>")
        self._run("sign", p, "--meta", self.meta,
                  "--priv", self.keys["private"])
        data = bytearray(open(p, "rb").read())
        eoi = data.rfind(b"\xff\xd9")
        data[eoi - 1] ^= 0xFF          # 改扫描数据末字节（不动段结构）
        with open(p, "wb") as f:
            f.write(data)
        r = self._run("check", p, "--json")
        rep = json.loads(r.stdout)
        self.assertEqual(rep["sections"]["C"]["status"], "FAIL")

    def test_extra_carrier_fixture_factories(self):
        """额外载体夹具工厂（PNG zTXt/iTXt、MP3/WAV/TIFF/GIF/WebP/FLAC/OGG/HEIF）。

        这些夹具由 `test_media_extra_integration` 的端到端用例使用；这里在
        **入仓单测**里显式调用它们，保证「工厂 → 建件 → extract 可解析」这条
        夹具面有常驻判据（dead-code 门禁要求顶层函数必须有真实调用点）。
        """
        makers = (
            ("png-ztxt", lambda p: metadata.make_png_with_ztxt(p, "K", "v")),
            ("png-itxt", lambda p: metadata.make_png_with_itxt(p, "K", "v")),
            ("mp3", lambda p: metadata.make_mp3_with_txxx(p, "AIGC", "{}")),
            ("wav", lambda p: metadata.make_wav_with_info(p, {"ISFT": "nf"})),
            ("tiff", metadata.make_tiff),
            ("gif", metadata.make_gif),
            ("webp", metadata.make_webp),
            ("flac", metadata.make_flac),
            ("ogg", metadata.make_ogg),
            ("heif", metadata.make_heif),
        )
        for suffix, maker in makers:
            path = os.path.join(self.td, "extra-" + suffix)
            maker(path)
            with open(path, "rb") as fh:
                self.assertGreater(len(fh.read()), 0, suffix)
            self.assertIsInstance(metadata.extract(path), list, suffix)
        # sidecar 读写 API 往返（read_sidecar 与 write_sidecar 是成对公开面）
        base = os.path.join(self.td, "extra-sidecar.bin")
        with open(base, "wb") as fh:
            fh.write(b"x")
        wrote = metadata.write_sidecar(base, {"AIGC": {"Label": 1}})
        self.assertTrue(wrote.endswith(".aigc.json"))
        self.assertEqual({"AIGC": {"Label": 1}},
                         metadata.read_sidecar(base))

    def test_sidecar_still_used_for_unknown_container(self):
        p = os.path.join(self.td, "x.bin")
        with open(p, "wb") as f:
            f.write(b"unknown-container")
        r = self._run("sign", p, "--meta", self.meta,
                      "--priv", self.keys["private"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(p + ".aigc.json"))


if __name__ == "__main__":
    unittest.main()
