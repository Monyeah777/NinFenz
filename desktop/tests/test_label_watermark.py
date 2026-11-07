"""水印层判据：写进去能读回、扛裁剪与重存、**不**扛 JPEG（写成期望行为，不是缺陷）。"""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import label_watermark  # noqa: E402

try:
    import numpy as np
    from PIL import Image
except ImportError:                                  # pragma: no cover - 环境缺 Pillow
    Image = None


def _png(width=200, height=200, seed=7) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "PNG")
    return buf.getvalue()


@unittest.skipUnless(Image is not None, "环境无 Pillow：水印面跳过（不冒充已验）")
class WatermarkRoundTripTest(unittest.TestCase):
    PAYLOAD = b'{"v":1,"schema":"nf-label/1","items":["E1","I2"],"level":"minimal"}'

    def test_embed_then_extract_round_trip(self):
        src = _png()
        out, info = label_watermark.embed(src, self.PAYLOAD)
        self.assertGreater(info["redundancy"], 1, "必须多块冗余，否则裁一刀就没了")
        res = label_watermark.extract(out)
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(self.PAYLOAD, res["payload"])
        self.assertGreater(res["confidence"], 0.9)

    def test_survives_lossless_resave(self):
        out, _info = label_watermark.embed(_png(), self.PAYLOAD)
        resaved = io.BytesIO()
        Image.open(io.BytesIO(out)).save(resaved, "PNG")
        self.assertEqual(self.PAYLOAD, label_watermark.extract(resaved.getvalue())["payload"])

    def test_survives_crop(self):
        out, _info = label_watermark.embed(_png(), self.PAYLOAD)
        cropped = io.BytesIO()
        Image.open(io.BytesIO(out)).crop((64, 64, 192, 192)).save(cropped, "PNG")
        res = label_watermark.extract(cropped.getvalue())
        self.assertTrue(res["ok"], res["issues"])
        self.assertEqual(self.PAYLOAD, res["payload"])

    def test_does_not_survive_jpeg_transcode(self):
        """**期望行为**：低位水印扛不住有损转码——这是物理边界，不是我们的 bug。"""
        out, _info = label_watermark.embed(_png(), self.PAYLOAD)
        jpeg = io.BytesIO()
        Image.open(io.BytesIO(out)).convert("RGB").save(jpeg, "JPEG", quality=95)
        again = io.BytesIO()
        Image.open(jpeg).save(again, "PNG")
        res = label_watermark.extract(again.getvalue())
        self.assertFalse(res["ok"])

    def test_image_without_watermark_reports_invalid(self):
        self.assertFalse(label_watermark.extract(_png(seed=11))["ok"])

    def test_too_small_image_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            label_watermark.embed(_png(width=32, height=32), self.PAYLOAD)
        self.assertIn("修复指引", str(ctx.exception))

    def test_oversized_payload_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            label_watermark.embed(_png(), b"x" * 5000)
        self.assertIn("修复指引", str(ctx.exception))


@unittest.skipUnless(Image is not None, "环境无 Pillow：水印面跳过（不冒充已验）")
class WatermarkFrameTest(unittest.TestCase):
    def test_frame_carries_ir_summary(self):
        ir = {"schema": "nf-label/1", "standard": "GB 45438-2025", "level": "minimal",
              "object": {"digest": "a" * 64},
              "explicit": [{"id": "E1", "kind": "text"}],
              "implicit": [{"id": "I2", "kind": "metadata"}]}
        payload = label_watermark._frame_for_ir(ir)
        self.assertLessEqual(len(payload), label_watermark.FRAME_MAX)
        text = payload.decode()
        self.assertIn("E1", text)
        self.assertIn("I2", text)
        self.assertIn("GB 45438-2025", text)


@unittest.skipUnless(Image is not None, "环境无 Pillow：水印面跳过（不冒充已验）")
class WatermarkCliTest(unittest.TestCase):
    def test_cli_embed_and_extract(self):
        import json
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "x.png"
            png.write_bytes(_png())
            items = Path(tmp) / "items.json"
            items.write_text(json.dumps([
                {"id": "E1", "face": "explicit", "kind": "text", "where": "start", "value": "AI"},
                {"id": "I2", "face": "implicit", "kind": "metadata", "key": "AIGC", "value": "y"},
            ], ensure_ascii=False), encoding="utf-8")
            ir = Path(tmp) / "ir.json"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"), "label", "ir",
                            str(png), "--items", str(items), "--out", str(ir)],
                           check=True, capture_output=True, timeout=120)
            out = Path(tmp) / "x.wm.png"
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"), "label",
                                   "embed", "--object", str(png), "--ir", str(ir),
                                   "--mode", "watermark", "--out", str(out)],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-400:])
            read = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"), "label",
                                   "extract", str(out), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            doc = json.loads(read.stdout)
            self.assertEqual("ok", doc["verdict"])
            self.assertEqual("watermark", doc["source"])
            self.assertIn("E1", doc["watermark_payload"])


if __name__ == "__main__":
    unittest.main()
