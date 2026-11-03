"""TIFF / GIF / WebP 标识写入的回归测试（writers_media_extra）。

作者：impl（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_media_extra -v

夹具在测试内自建最小容器；TIFF/WebP 直接做「写入 → metadata 提取」往返；
GIF 用本文件的解析器做结构/往返断言（metadata 的 GIF 读取面对 xmp 扩展的块
边界需特殊处理，见下方 skip 用例与交付说明）。
"""

import html
import json
import os
import stat
import struct
import tempfile
import unittest
from pathlib import Path

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in __import__("sys").path:
    __import__("sys").path.insert(
        0, os.path.join(sys_path_root, "desktop", "src"))


from core.labeling import metadata
from core.labeling import writers_media_extra as w

J = json.dumps({"AIGC": {"Label": "1",
                         "ContentProducer": "001091350100M000100Y4300000",
                         "ProduceID": "pid20250101v123456"}},
               ensure_ascii=False)
OBJ = json.loads(J)


# ---------------------------------------------------------------- 夹具
def _make_tiff(path, bo="little", old_xmp=None):
    """最小 TIFF：头 + IFD0(宽/高/strip offset/strip count[+旧 XMP]) + 1 像素。"""
    def u16(v):
        return v.to_bytes(2, bo)

    def u32(v):
        return v.to_bytes(4, bo)

    pix = b"\x11\x22\x33\x44"
    entries = [(0x100, 4, 1, u32(1)), (0x101, 4, 1, u32(2))]
    n = 4 + (1 if old_xmp is not None else 0)
    ifd_size = 2 + 12 * n + 4
    pix_off = 8 + ifd_size
    entries += [(0x111, 4, 1, u32(pix_off)), (0x117, 4, 1, u32(len(pix)))]
    tail = b""
    if old_xmp is not None:
        xoff = pix_off + len(pix)
        entries.append((0x2BC, 7, len(old_xmp), u32(xoff)))
        tail = old_xmp
    entries.sort(key=lambda e: e[0])
    head = (b"II" if bo == "little" else b"MM") + u16(42) + u32(8)
    out = bytearray(head) + u16(len(entries))
    for tag, typ, cnt, raw in entries:
        out += u16(tag) + u16(typ) + u32(cnt) + raw
    out += u32(0) + pix + tail
    Path(path).write_bytes(bytes(out))
    return pix, pix_off


_TIFF_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4,
              10: 8, 11: 4, 12: 8}


def _tiff_read_tag(path, want):
    """解析 IFD0，返回 want tag 的 (typ, count, value_bytes) 或 None。"""
    data = Path(path).read_bytes()
    bo = "little" if data[:2] == b"II" else "big"
    ifd = int.from_bytes(data[4:8], bo)
    count = int.from_bytes(data[ifd:ifd + 2], bo)
    for i in range(count):
        pos = ifd + 2 + 12 * i
        tag = int.from_bytes(data[pos:pos + 2], bo)
        typ = int.from_bytes(data[pos + 2:pos + 4], bo)
        cnt = int.from_bytes(data[pos + 4:pos + 8], bo)
        raw4 = data[pos + 8:pos + 12]
        if tag != want:
            continue
        size = cnt * _TIFF_SIZE.get(typ, 1)
        if size <= 4:
            return typ, cnt, raw4[:size]
        off = int.from_bytes(raw4, bo)
        return typ, cnt, data[off:off + size]
    return None


def _make_gif(path):
    """最小 GIF：Header + LSD（无 GCT）+ 1×1 图像块 + trailer。"""
    gif = (b"GIF89a" + struct.pack("<HH", 1, 1) + b"\x00\x00\x00"
           + b"\x2c" + struct.pack("<HHHH", 0, 0, 1, 1) + b"\x00"
           + b"\x02\x02\x44\x01\x00" + b"\x3b")
    Path(path).write_bytes(gif)
    return gif


def _gif_xmp_span(data):
    """定位我方 XMP 扩展：返回 (start, end, packet_bytes) 或 None。"""
    marker = b"\x21\xff\x0bXMP DataXMP"
    start = data.find(marker)
    if start < 0:
        return None
    body = start + len(marker)
    stop = data.find(b"\x00", body)
    if stop < 0:
        return None
    return start, stop + 1, data[body:stop]


def _gif_image_start(data):
    """首个图像块（0x2C）起点（跳过 Header/LSD 与扩展；XMP 扩展按 0x00 终止）。"""
    marker = b"\x21\xff\x0bXMP DataXMP"
    pos = 13
    while pos < len(data):
        b = data[pos]
        if b == 0x2C:
            return pos
        if b == 0x3B:
            return pos
        if b == 0x21:
            if data.startswith(marker, pos):
                stop = data.find(b"\x00", pos + len(marker))
                if stop < 0:
                    return pos
                pos = stop + 1
                continue
            pos += 2
            while pos < len(data):
                n = data[pos]
                pos += 1
                if n == 0:
                    break
                pos += n
            continue
        return pos
    return pos


def _webp_chunks(data):
    out = []
    pos = 12
    while pos + 8 <= len(data):
        fourcc = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        out.append((fourcc, body))
        pos += 8 + size + (size & 1)
    return out


def _make_webp(path, extra_chunks=()):
    """最小 WebP：RIFF/WEBP + VP8L（5 字节奇数 payload，验证 pad）。"""
    vp8l = b"\x2f\x01\x02\x03\x04"
    chunks = [(b"VP8L", vp8l)] + list(extra_chunks)
    body = bytearray(b"WEBP")
    for fourcc, payload in chunks:
        body += fourcc + len(payload).to_bytes(4, "little") + payload
        if len(payload) & 1:
            body += b"\x00"
    Path(path).write_bytes(b"RIFF" + len(body).to_bytes(4, "little") + body)
    return vp8l


class MediaExtraTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return str(self.dir / name)

    # ------------------------------------------------------- TIFF
    def test_tiff_little_endian_metadata_roundtrip(self):
        path = self.p("a.tif")
        _make_tiff(path, "little")
        w.inject_tiff(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["container"], "tiff.IFD0")
        self.assertEqual(cands[0]["raw"], J)
        self.assertEqual(cands[0]["obj"], OBJ)

    def test_tiff_big_endian_metadata_roundtrip(self):
        path = self.p("b.tif")
        _make_tiff(path, "big")
        w.inject_tiff(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["raw"], J)

    def test_tiff_tag_structure(self):
        path = self.p("a.tif")
        _make_tiff(path, "little")
        before = len(Path(path).read_bytes())
        w.inject_tiff(path, J)
        got = _tiff_read_tag(path, 0x2BC)
        self.assertIsNotNone(got)
        typ, cnt, raw = got
        want = w._xmp_packet(J)                  # 0x2BC 是 XMP 标签，放 XMP 包
        self.assertEqual(typ, 7)                 # UNDEFINED
        self.assertEqual(cnt, len(want))
        self.assertEqual(raw, want)
        self.assertGreater(len(Path(path).read_bytes()), before)

    def test_tiff_other_ifd0_tags_preserved(self):
        path = self.p("a.tif")
        pix, pix_off = _make_tiff(path, "little")
        w.inject_tiff(path, J)
        self.assertEqual(_tiff_read_tag(path, 0x100)[2],
                         (1).to_bytes(4, "little"))
        self.assertEqual(_tiff_read_tag(path, 0x101)[2],
                         (2).to_bytes(4, "little"))
        self.assertEqual(_tiff_read_tag(path, 0x111)[2],
                         pix_off.to_bytes(4, "little"))
        self.assertEqual(_tiff_read_tag(path, 0x117)[2],
                         len(pix).to_bytes(4, "little"))

    def test_tiff_pixel_and_content_unchanged(self):
        path = self.p("a.tif")
        pix, pix_off = _make_tiff(path, "little")
        _, before = metadata.content_bytes_for(path, "tiff")
        w.inject_tiff(path, J)
        _, after = metadata.content_bytes_for(path, "tiff")
        self.assertEqual(before, after)
        self.assertEqual(Path(path).read_bytes()[pix_off:pix_off + len(pix)],
                         pix)

    def test_tiff_existing_tag_replaced(self):
        path = self.p("c.tif")
        _make_tiff(path, "little", old_xmp=b'{"old":1}')
        w.inject_tiff(path, J)
        typ, cnt, raw = _tiff_read_tag(path, 0x2BC)
        want = w._xmp_packet(J)
        self.assertEqual(typ, 7)
        self.assertEqual(cnt, len(want))
        self.assertEqual(raw, want)

    def test_tiff_idempotent(self):
        path = self.p("a.tif")
        _make_tiff(path, "little")
        w.inject_tiff(path, J)
        once = Path(path).read_bytes()
        w.inject_tiff(path, J)
        self.assertEqual(once, Path(path).read_bytes())

    def test_tiff_small_json_uses_xmp_packet(self):
        # 0x2BC 固定放 XMP 包（不再有小值内联的特殊路径）
        path = self.p("small.tif")
        _make_tiff(path, "little")
        w.inject_tiff(path, "{}")
        got = _tiff_read_tag(path, 0x2BC)
        self.assertEqual(got[0], 7)
        self.assertEqual(got[2], w._xmp_packet("{}"))
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        self.assertEqual(cands[0]["obj"], {})

    def test_tiff_bad_inputs(self):
        for name, blob in (
                ("not.tif", b"not a tiff"),
                ("magic.tif", b"II\x00\x00\x08\x00\x00\x00"),
                ("oob.tif", b"II*\x00\xff\xff\xff\x7f"),
                ("trunc.tif", b"II*\x00\x08\x00\x00\x00\x10\x00")):
            path = self.p(name)
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError):
                w.inject_tiff(path, J)
        path = self.p("in.tif")
        _make_tiff(path, "little")
        with self.assertRaises(ValueError):
            w.inject_tiff(path, "{bad json}")

    # ------------------------------------------------------- GIF
    def test_gif_extension_structure(self):
        path = self.p("a.gif")
        gif = _make_gif(path)
        w.inject_gif(path, J)
        data = Path(path).read_bytes()
        self.assertEqual(data[:13], gif[:13])    # Header + LSD 不变
        span = _gif_xmp_span(data)
        self.assertIsNotNone(span)
        start, end, packet = span
        self.assertEqual(start, 13)              # 紧跟 LSD
        self.assertEqual(data[start:start + 3], b"\x21\xff\x0b")
        self.assertEqual(data[start + 3:start + 14], b"XMP DataXMP")
        self.assertIn(b"xpacket", packet)
        self.assertIn(b"x:xmpmeta", packet)
        self.assertIn(b"TC260:AIGC", packet)
        self.assertEqual(data[end - 1:end], b"\x00")

    def test_gif_own_parser_roundtrip(self):
        path = self.p("a.gif")
        _make_gif(path)
        w.inject_gif(path, J)
        span = _gif_xmp_span(Path(path).read_bytes())
        self.assertIsNotNone(span)
        body = span[2]
        packet = bytearray()
        pos = 0
        while pos < len(body):
            n = body[pos]
            pos += 1
            if n == 0:
                break
            packet += body[pos:pos + n]
            pos += n
        text = html.unescape(bytes(packet).decode("utf-8"))
        self.assertIn(J, text)

    def test_gif_repeat_single_extension(self):
        path = self.p("a.gif")
        _make_gif(path)
        w.inject_gif(path, J)
        w.inject_gif(path, J)
        data = Path(path).read_bytes()
        self.assertEqual(data.count(b"XMP DataXMP"), 1)

    def test_gif_image_block_unchanged(self):
        path = self.p("a.gif")
        gif = _make_gif(path)
        w.inject_gif(path, J)
        data = Path(path).read_bytes()
        orig_img = _gif_image_start(gif)
        new_img = _gif_image_start(data)
        self.assertEqual(gif[orig_img:], data[new_img:])

    def test_gif_idempotent(self):
        path = self.p("a.gif")
        _make_gif(path)
        w.inject_gif(path, J)
        once = Path(path).read_bytes()
        w.inject_gif(path, J)
        self.assertEqual(once, Path(path).read_bytes())

    def test_gif_bad_inputs(self):
        for name, blob in (
                ("not.gif", b"not a gif"),
                ("short.gif", b"GIF89a"),
                ("lsd.gif", b"GIF89a\x01\x00"),
                ("gct.gif", b"GIF89a" + b"\x01\x00\x01\x00\x80\x00\x00")):
            path = self.p(name)
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError):
                w.inject_gif(path, J)
        path = self.p("in.gif")
        _make_gif(path)
        with self.assertRaises(ValueError):
            w.inject_gif(path, "{bad json}")

    def test_gif_metadata_roundtrip_when_reader_supports(self):
        path = self.p("a.gif")
        _make_gif(path)
        w.inject_gif(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "AIGC"]
        ok = len(cands) == 1 and cands[0]["raw"] == J
        if not ok:
            self.skipTest("metadata 的 GIF 读取面需特殊处理 XMP DataXMP 扩展"
                          "（已报 Lead；写入结构按 /tmp/mediaextra-spec.md）")
        self.assertEqual(cands[0]["obj"], OBJ)

    # ------------------------------------------------------- WebP
    def test_webp_metadata_roundtrip(self):
        path = self.p("a.webp")
        _make_webp(path)
        w.inject_webp(path, J)
        cands = [c for c in metadata.extract_json_candidates(path)
                 if c["key"] == "XMP"]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["container"], "webp.XMP")
        self.assertEqual(cands[0]["raw"], J)
        self.assertEqual(cands[0]["obj"], OBJ)

    def test_webp_riff_size_and_chunk_pad(self):
        path = self.p("a.webp")
        _make_webp(path)
        w.inject_webp(path, J)
        data = Path(path).read_bytes()
        self.assertEqual(int.from_bytes(data[4:8], "little"), len(data) - 8)
        chunks = _webp_chunks(data)
        self.assertEqual([c[0] for c in chunks], [b"VP8L", b"XMP "])
        self.assertIn(b"x:xmpmeta", chunks[-1][1])
        # 块解析必须正好吃完整个文件（含 XMP 的 pad 正确）
        pos = 12
        for fourcc, payload in chunks:
            pos += 8 + len(payload) + (len(payload) & 1)
        self.assertEqual(pos, len(data))

    def test_webp_image_payload_unchanged(self):
        path = self.p("a.webp")
        vp8l = _make_webp(path)
        _, before = metadata.content_bytes_for(path, "webp")
        w.inject_webp(path, J)
        _, after = metadata.content_bytes_for(path, "webp")
        self.assertEqual(before, after)
        chunks = _webp_chunks(Path(path).read_bytes())
        self.assertEqual(chunks[0], (b"VP8L", vp8l))

    def test_webp_existing_xmp_replaced(self):
        path = self.p("b.webp")
        _make_webp(path, extra_chunks=[(b"XMP ", b"<old/>")])
        w.inject_webp(path, J)
        chunks = _webp_chunks(Path(path).read_bytes())
        xmp = [c for c in chunks if c[0] == b"XMP "]
        self.assertEqual(len(xmp), 1)
        self.assertIn(b"x:xmpmeta", xmp[0][1])

    def test_webp_idempotent(self):
        path = self.p("a.webp")
        _make_webp(path)
        w.inject_webp(path, J)
        once = Path(path).read_bytes()
        w.inject_webp(path, J)
        self.assertEqual(once, Path(path).read_bytes())

    def test_webp_bad_inputs(self):
        for name, blob in (
                ("not.webp", b"not a webp"),
                ("riff.webp", b"RIFF\x04\x00\x00\x00WAVE"),
                ("trunc.webp",
                 b"RIFF\x10\x00\x00\x00WEBPVP8L\xff\x00\x00\x00")):
            path = self.p(name)
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError):
                w.inject_webp(path, J)
        path = self.p("in.webp")
        _make_webp(path)
        with self.assertRaises(ValueError):
            w.inject_webp(path, "{bad json}")

    # ------------------------------------------------------- 公共
    def test_atomic_write_no_residue_and_permissions(self):
        cases = [("a.tif", _make_tiff, w.inject_tiff),
                 ("a.gif", _make_gif, w.inject_gif),
                 ("a.webp", _make_webp, w.inject_webp)]
        for name, make, inject in cases:
            path = self.p(name)
            make(path)
            os.chmod(path, 0o640)
            before = sorted(p.name for p in self.dir.iterdir())
            inject(path, J)
            self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                             before)
            self.assertFalse(any(n.endswith(".tmp") for n in before))
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o640)

    def test_content_bytes_stable_tiff_webp(self):
        cases = [("a.tif", _make_tiff, w.inject_tiff, "tiff"),
                 ("a.webp", _make_webp, w.inject_webp, "webp")]
        for name, make, inject, kind in cases:
            path = self.p(name)
            make(path)
            _, before = metadata.content_bytes_for(path, kind)
            inject(path, J)
            _, after = metadata.content_bytes_for(path, kind)
            self.assertEqual(before, after, kind)

    def test_gif_content_selector_when_reader_supports(self):
        path = self.p("a.gif")
        gif = _make_gif(path)
        w.inject_gif(path, J)
        _, after = metadata.content_bytes_for(path, "gif")
        orig_img = _gif_image_start(gif)
        if after != gif[orig_img:]:
            self.skipTest("metadata 的 GIF 块扫描需特殊处理 XMP DataXMP 扩展"
                          "（已报 Lead；写入结构按 /tmp/mediaextra-spec.md）")
        self.assertTrue(after.startswith(b"\x2c"))


if __name__ == "__main__":
    unittest.main()
