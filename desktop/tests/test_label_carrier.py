"""标注载体 v0（PNG iTXt）判据：只证三件事，缺一条就不算载体成立。

1. 写进去能**读回**（同 IR、JSON 语义等价）；
2. 写入**不改像素**（IDAT 逐字节一致）；
3. 写入后文件仍是**结构合法**的 PNG（签名 + 每块 CRC）。
另外：不支持的格式必须带指引拒绝，绝不给「写成了」的假象。
"""
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import label_carrier as lc  # noqa: E402
from core import label_ir  # noqa: E402

SCRIPT = ROOT / "scripts" / "nf.py"


def make_png(width: int = 2, height: int = 2, rgb: tuple = (10, 20, 30)) -> bytes:
    """最小合法 PNG（纯标准库构造，便于判据自证）。"""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (lc.PNG_SIG + lc._chunk("IHDR", ihdr)
            + lc._chunk("IDAT", zlib.compress(raw, 9)) + lc._chunk("IEND", b""))


def make_ir(png: bytes, path: str = "poster.png") -> dict:
    return label_ir.build(path, hashlib.sha256(png).hexdigest(), items=[
        {"face": "explicit", "kind": "text", "where": "start", "value": "AI 生成"},
        {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"},
    ])


class TestEmbedRead(unittest.TestCase):
    def test_round_trip(self):
        png = make_png()
        out, info = lc.embed(png, make_ir(png))
        self.assertEqual("AIGC", info["keyword"])
        res = lc.read(out)
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertTrue(res["embedded"])
        self.assertEqual("GB 45438-2025", res["label"]["standard"])

    def test_pixels_untouched(self):
        png = make_png(rgb=(200, 100, 50))
        out, info = lc.embed(png, make_ir(png))
        self.assertEqual(lc.pixel_digest(png), lc.pixel_digest(out))
        self.assertEqual(info["pixel_digest"], lc.pixel_digest(out))

    def test_structure_still_valid(self):
        png = make_png()
        out, _info = lc.embed(png, make_ir(png))
        # _iter_chunks 自带 CRC 校验：能拆完即结构合法
        types = [t for t, _b in lc._iter_chunks(out)]
        self.assertEqual("IHDR", types[0])
        self.assertEqual("IEND", types[-1])
        self.assertIn("iTXt", types)

    def test_embed_is_idempotent(self):
        png = make_png()
        ir = make_ir(png)
        once, _i1 = lc.embed(png, ir)
        twice, info2 = lc.embed(once, ir)
        self.assertTrue(info2["replaced"])
        self.assertEqual(once, twice)

    def test_other_itxt_blocks_kept(self):
        png = make_png()
        ihdr = lc._iter_chunks(png)[0][1]
        idat = lc._iter_chunks(png)[1][1]
        comment = b"Comment" + b"\x00" * 5 + b"hello"
        extra = (lc.PNG_SIG + lc._chunk("IHDR", ihdr) + lc._chunk("iTXt", comment)
                 + lc._chunk("IDAT", idat) + lc._chunk("IEND", b""))
        out, _info = lc.embed(extra, make_ir(png))
        blocks = [b for t, b in lc._iter_chunks(out) if t == "iTXt"]
        self.assertEqual(2, len(blocks), "别人的 iTXt 块必须原样保留")
        self.assertTrue(any(b.startswith(b"Comment") for b in blocks))
        self.assertEqual("ok", lc.read(out)["verdict"])

    def test_refuses_non_png_with_guidance(self):
        png = make_png()
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(b"GIF89a not png", make_ir(png))
        self.assertIn("PNG", str(ctx.exception))
        self.assertIn("修复指引", str(ctx.exception))

    def test_refuses_broken_crc(self):
        png = bytearray(make_png())
        ir = make_ir(bytes(png))
        png[-5] ^= 0xFF
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(bytes(png), ir)
        self.assertIn("CRC", str(ctx.exception))

    def test_refuses_invalid_ir(self):
        png = make_png()
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(png, {"schema": "nope"})
        self.assertIn("IR 不合法", str(ctx.exception))

    def test_missing_label_is_invalid_with_guidance(self):
        res = lc.read(make_png())
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("从未写入", " ".join(res["issues"]))


class TestCli(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "label", *args], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")

    def test_embed_then_extract(self):
        with tempfile.TemporaryDirectory(prefix="nf_carrier_") as tmp:
            src = Path(tmp, "poster.png")
            src.write_bytes(make_png())
            ir_path = Path(tmp, "ir.json")
            ir_path.write_text(json.dumps(make_ir(src.read_bytes()), ensure_ascii=False),
                               encoding="utf-8")
            out = Path(tmp, "out.png")
            proc = self._run("embed", "--object", str(src), "--ir", str(ir_path),
                             "--out", str(out), "--json")
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual("AIGC", doc["keyword"])
            self.assertTrue(out.is_file())
            proc = self._run("extract", str(out), "--json")
            self.assertEqual(0, proc.returncode)
            self.assertEqual("ok", json.loads(proc.stdout)["verdict"])

    def test_extract_unlabeled_exits_1(self):
        with tempfile.TemporaryDirectory(prefix="nf_carrier2_") as tmp:
            src = Path(tmp, "plain.png")
            src.write_bytes(make_png())
            proc = self._run("extract", str(src), "--json")
            self.assertEqual(1, proc.returncode)
            self.assertEqual("invalid", json.loads(proc.stdout)["verdict"])


if __name__ == "__main__":
    unittest.main()
