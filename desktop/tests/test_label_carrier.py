"""标注载体 v0（PNG iTXt）判据：只证三件事，缺一条就不算载体成立。

1. 写进去能**读回**（同 IR、JSON 语义等价）；
2. 写入**不改像素**（IDAT 逐字节一致）；
3. 写入后文件仍是**结构合法**的 PNG（签名 + 每块 CRC）。
另外：不支持的格式必须带指引拒绝，绝不给「写成了」的假象。
"""
import base64
import hashlib
import io
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


#: 1x1 真实 JPEG（Pillow 生成后固定下来的字节；用 base64 内联是为了零外部文件依赖）
JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsK"
    "CwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQU"
    "FBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAAEAAQDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD8+qKK"
    "K+oPnD//2Q=="
)


def make_jpeg() -> bytes:
    """真实 JPEG 字节（不是手搓外壳）：载体判据必须能处理真文件。"""
    return base64.b64decode(JPEG_B64)


def pytest_importorskip_image():
    """Pillow 在场就返回 Image（用于「解码后像素一致」这条附加判据）；不在场返回 None。"""
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image


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
        out, _info = lc.embed(extra, make_ir(extra))
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


class TestHardening(unittest.TestCase):
    """入库复核（2026-11-06）补的负例：对象绑定 / 空壳 / 畸形块 / 落点 / 深度。"""

    def test_refuses_ir_for_other_object(self):
        png, other = make_png(), make_png(rgb=(1, 2, 3))
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(png, make_ir(other))
        self.assertIn("不符", str(ctx.exception))
        self.assertIn("修复指引", str(ctx.exception))

    def test_refuses_signature_only_shell(self):
        shell = lc.PNG_SIG
        ir = label_ir.build("shell.png", hashlib.sha256(shell).hexdigest(), items=[
            {"face": "explicit", "kind": "text", "where": "start", "value": "AI 生成"},
            {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"}])
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(shell, ir)
        self.assertIn("没有任何块", str(ctx.exception))

    def test_refuses_out_equals_src(self):
        with tempfile.TemporaryDirectory(prefix="nf_carrier3_") as tmp:
            src = str(Path(tmp, "a.png"))
            Path(src).write_bytes(make_png())
            with self.assertRaises(lc.CarrierError) as ctx:
                lc.embed_file(src, make_ir(Path(src).read_bytes()), src)
            self.assertIn("落点不能等于源文件", str(ctx.exception))

    def test_read_malformed_aigc_block_is_invalid(self):
        bad = (lc.PNG_SIG + lc._chunk("IHDR", b"\x00" * 13)
               + lc._chunk("iTXt", b"AIGC") + lc._chunk("IEND", b""))
        res = lc.read(bad)
        self.assertEqual("invalid", res["verdict"])
        self.assertIn("结构不完整", " ".join(res["issues"]))

    def test_read_deep_nesting_is_invalid_not_crash(self):
        deep = "{" * 200 + "0" + "}" * 200
        png = (lc.PNG_SIG + lc._chunk("IHDR", b"\x00" * 13)
               + lc._chunk("iTXt", lc._itxt_body(deep)) + lc._chunk("IEND", b""))
        res = lc.read(png)
        self.assertEqual("invalid", res["verdict"])


class TestCliIrBinary(unittest.TestCase):
    """用户流程判据：nf label ir 必须能吃二进制对象（否则载体 CLI 无法端到端使用）。"""

    def test_ir_accepts_png_object(self):
        items = [{"face": "explicit", "kind": "text", "where": "start", "value": "AI 生成"},
                 {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"}]
        with tempfile.TemporaryDirectory(prefix="nf_carrier4_") as tmp:
            src = Path(tmp, "poster.png")
            src.write_bytes(make_png())
            items_path = Path(tmp, "items.json")
            items_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), "label", "ir", str(src),
                                   "--items", str(items_path), "--json"],
                                  cwd=str(ROOT), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),
                             doc["object"]["digest"])


def make_min_jpeg() -> bytes:
    """最小可解析 JPEG：SOI + APP0 + SOF0 + SOS + 熵数据 + EOI（纯标准库构造）。

    命名避开仓库既有 make_jpeg（那是 Pillow 真图夹具，PIL 解码面判据依赖它）。
    """
    def seg(marker, payload):
        return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload
    app0 = seg(0xE0, b"JFIF\x00")
    sof = seg(0xC0, b"\x08" + struct.pack(">HH", 2, 2) + b"\x01\x01\x11\x00")
    sos = seg(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    return b"\xff\xd8" + app0 + sof + sos + b"\x12\x34\x56\x78\xff\xd9"


class TestJpegHardening(unittest.TestCase):
    """JPEG 分支与 PNG 同等硬化：对象绑定 / SOF 结构闸 / 幂等 / 内容摘要去标签。"""

    def test_rejects_ir_for_other_object(self):
        jpeg = make_jpeg()
        other_ir = make_ir(b"# not this jpeg\n")
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(jpeg, other_ir)
        self.assertIn("不符", str(ctx.exception))
        self.assertIn("修复指引", str(ctx.exception))

    def test_rejects_missing_sof(self):
        shell = b"\xff\xd8" + b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
        ir = label_ir.build("shell.jpg", hashlib.sha256(shell).hexdigest(), items=[
            {"face": "explicit", "kind": "text", "where": "start", "value": "AI"},
            {"face": "implicit", "kind": "metadata", "key": "AIGC", "value": "1"}])
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(shell, ir)
        self.assertIn("SOF", str(ctx.exception))

    def test_round_trip_idempotent_and_scan_untouched(self):
        jpeg = make_jpeg()
        ir = make_ir(jpeg, path="photo.jpg")
        once, info1 = lc.embed(jpeg, ir)
        self.assertEqual("jpeg", info1["format"])
        self.assertEqual(lc.jpeg_scan_digest(jpeg), lc.jpeg_scan_digest(once))
        self.assertEqual("ok", lc.read(once)["verdict"])
        twice, info2 = lc.embed(once, ir)
        self.assertTrue(info2["replaced"])
        self.assertEqual(once, twice)

    def test_content_digest_strips_label(self):
        jpeg = make_jpeg()
        out, _info = lc.embed(jpeg, make_ir(jpeg, path="photo.jpg"))
        self.assertEqual(hashlib.sha256(jpeg).hexdigest(), lc.jpeg_content_digest(out))


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


class TestJpegCarrier(unittest.TestCase):
    """JPEG APP15 载体：承诺与 PNG 同形——读得回、扫描数据不动、段结构合法。"""

    def setUp(self):
        self.jpeg = make_jpeg()

    def test_magic_dispatch(self):
        self.assertEqual("jpeg", lc.embed(self.jpeg, make_ir(self.jpeg))[1]["format"])

    def test_round_trip(self):
        out, info = lc.embed(self.jpeg, make_ir(self.jpeg))
        self.assertFalse(info["replaced"])
        res = lc.read(out)
        self.assertEqual("ok", res["verdict"], res["issues"])
        self.assertEqual("jpeg-app15", res["carrier"])
        self.assertEqual("GB 45438-2025", res["label"]["standard"])

    def test_scan_data_untouched(self):
        out, _info = lc.embed(self.jpeg, make_ir(self.jpeg))
        self.assertEqual(lc.jpeg_scan_digest(self.jpeg), lc.jpeg_scan_digest(out))

    def test_idempotent_and_no_duplicate_segments(self):
        ir = make_ir(self.jpeg)
        once, _i1 = lc.embed(self.jpeg, ir)
        twice, info2 = lc.embed(once, ir)
        self.assertTrue(info2["replaced"])
        self.assertEqual(once, twice, "重复嵌入必须幂等（不得堆积 APP15 段）")

    def test_refuses_truncated_jpeg(self):
        ir = make_ir(self.jpeg)
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(self.jpeg[:len(self.jpeg) // 2], ir)
        self.assertIn("修复指引", str(ctx.exception))

    def test_unsupported_format_rejected(self):
        with self.assertRaises(lc.CarrierError) as ctx:
            lc.embed(b"GIF89a" + b"\x00" * 32, make_ir(self.jpeg))
        self.assertIn("PNG", str(ctx.exception))
        self.assertIn("PDF", str(ctx.exception), "指引里要列全支持的载体")

    def test_pillow_can_still_decode_and_pixels_match(self):
        pil = pytest_importorskip_image()
        if pil is None:
            self.skipTest("环境无 Pillow：跳过解码面判据（结构面已由其它判据覆盖）")
        out, _info = lc.embed(self.jpeg, make_ir(self.jpeg))
        a = pil.open(io.BytesIO(self.jpeg))
        b = pil.open(io.BytesIO(out))
        self.assertEqual(a.size, b.size)
        self.assertEqual(list(a.convert("RGB").getdata()), list(b.convert("RGB").getdata()))


class TestRealPngFixtures(unittest.TestCase):
    """真仓里的真 PNG（图标/OG 图）：载体必须能处理多 IDAT、辅助块等真实结构。"""

    FIXTURES = ("packaging/mcp/assets/icon-400.png", "site/assets/og.png")

    def test_embed_round_trip_on_repo_pngs(self):
        pairs = [(name, (ROOT / name)) for name in self.FIXTURES]
        present = [(n, p) for n, p in pairs if p.is_file()]
        self.assertTrue(present, "仓库里找不到真 PNG 夹具（判据面被缩小）")
        for name, path in present:
            png = path.read_bytes()
            ir = make_ir(png, path.name)
            out, _info = lc.embed(png, ir)
            self.assertEqual(lc.pixel_digest(png), lc.pixel_digest(out), name)
            res = lc.read(out)
            self.assertEqual("ok", res["verdict"], f"{name}: {res['issues']}")
            self.assertEqual(ir["object"]["digest"], res["label"]["object"]["digest"], name)


class AdditionalCarriersTest(unittest.TestCase):
    """WebP / MP4 / PDF 的附加块载体：**前缀字节不变**（WebP 需同步 RIFF 长度字段）。

    这三种的承诺比 PNG/JPEG 更窄：不是「改元数据」，而是「在容器尾部追加可忽略块」——
    因此旧版解码器照样能打开，删除也只要截掉尾部。判据盯两件事：① 媒体字节没被碰；
    ② 读回形状合法（IR 校验过）。
    """

    def _ir(self):
        from core import label_ir
        return label_ir.build("x.bin", "a" * 64, level="minimal", items=[
            {"id": "E1", "face": "explicit", "kind": "text", "where": "start", "value": "AI"},
            {"id": "I2", "face": "implicit", "kind": "metadata", "key": "AIGC", "value": "y"},
        ])

    def test_webp_chunk_round_trip(self):
        import io as _io

        try:
            import numpy as np
            from PIL import Image
        except ModuleNotFoundError as exc:
            self.skipTest("环境缺可选图像依赖（%s）：WebP 往返需 Pillow+numpy" % exc.name)
        img = Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8), "RGB")
        buf = _io.BytesIO()
        img.save(buf, "WEBP", lossless=True)
        src = buf.getvalue()
        out, info = lc.embed(src, self._ir())
        self.assertEqual("webp-chunk", info["carrier"])
        self.assertEqual(src[12:], out[12:len(src)], "媒体块必须逐字节不变")
        self.assertEqual(src[:4], out[:4])
        self.assertTrue(lc.read(out)["ok"])
        self.assertEqual((64, 64), Image.open(_io.BytesIO(out)).size)

    def test_mp4_box_round_trip(self):
        src = (int.to_bytes(24, 4, "big") + b"ftyp" + b"isom" + b"\x00\x00\x02\x00"
               + b"isomiso2")
        out, info = lc.embed(src, self._ir())
        self.assertEqual("mp4-free-box", info["carrier"])
        self.assertEqual(src, out[:len(src)], "原始盒必须逐字节保留")
        self.assertTrue(lc.read(out)["ok"])

    def test_pdf_trailer_round_trip(self):
        src = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        out, info = lc.embed(src, self._ir())
        self.assertEqual("pdf-trailer-comment", info["carrier"])
        self.assertEqual(src, out[:len(src)], "PDF 前缀必须逐字节保留")
        self.assertTrue(lc.read(out)["ok"])

    def test_unlabeled_containers_are_invalid(self):
        for src in (b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 8,
                    int.to_bytes(24, 4, "big") + b"ftypisom" + b"\x00" * 12,
                    b"%PDF-1.4\n%%EOF\n"):
            self.assertFalse(lc.read(src)["ok"], src[:16])


if __name__ == "__main__":
    unittest.main()
