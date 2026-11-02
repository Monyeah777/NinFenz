"""writers_mp4.inject_mp4_xmp 的单元测试（unittest）。

作者：gate（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_mp4 -v

覆盖：XMP uuid 顶层盒往返（metadata.extract 的 mp4.uuid 分支）、mdat 载荷与
ftyp/moov 字节不变、顶层盒结构完整、重复写入只有一份顶层 XMP、XML 转义、
坏文件/坏 JSON 的 ValueError 语义、原子写不留临时件。
"""

import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in __import__("sys").path:
    __import__("sys").path.insert(
        0, os.path.join(sys_path_root, "desktop", "src"))

from core.labeling import metadata as md
from core.labeling import writers_mp4 as wm

PAYLOAD = {"Label": 1, "ContentProducer": "测试提供者",
           "ProduceID": "W-1", "Note": "A&B<C>\"q\""}


def _box(btype: bytes, payload: bytes, large: bool = False) -> bytes:
    """构造一个 MP4 盒（large=True 走 64 位 largesize）。"""
    if large:
        return (struct.pack(">I", 1) + btype
                + struct.pack(">Q", 16 + len(payload)) + payload)
    return struct.pack(">I", 8 + len(payload)) + btype + payload


def _make_clean_mp4(path: str, mdat_payload: bytes = b"") -> None:
    """构造无 XMP 的最小 MP4：ftyp + moov(mvhd) + mdat。"""
    ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512)
                + b"isomiso2mp41")
    moov = _box(b"moov", _box(b"mvhd", b"\x00" * 16))
    data = ftyp + moov + _box(b"mdat", mdat_payload)
    Path(path).write_bytes(data)


def _top(data: bytes):
    return list(md._boxes(data, 0, len(data)))


def _box_of(data: bytes, btype: bytes):
    for t, start, _body, end in _top(data):
        if t == btype:
            return data[start:end]
    return None


def _body_of(data: bytes, btype: bytes):
    for t, _start, body, end in _top(data):
        if t == btype:
            return data[body:end]
    return None


def _xmp_uuids(data: bytes):
    return [b for b in _top(data)
            if b[0] == b"uuid" and data[b[2]:b[2] + 16] == md.XMP_UUID]


def _json_text(payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


class WritersMp4Test(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name: str) -> str:
        return str(self.dir / name)

    # ------------------------------------------------------------ 往返
    def test_roundtrip_on_metadata_fixture(self):
        """metadata.make_mp4_with_xmp 夹具 → 写入 → extract 取回同一 JSON。"""
        path = self.p("a.mp4")
        md.make_mp4_with_xmp(path, "<x:xmpmeta/>")
        text = _json_text(PAYLOAD)
        wm.inject_mp4_xmp(path, text)
        cands = md.extract_json_candidates(path)
        objs = [c["obj"] for c in cands if c.get("obj") is not None]
        self.assertIn(PAYLOAD, objs)
        raws = [c["raw"] for c in cands if c.get("obj") == PAYLOAD]
        self.assertEqual([text], raws)
        items = md.extract(path)
        self.assertTrue(any(i["container"] == "mp4.uuid"
                            and i["kind"] == "xmp" for i in items))

    def test_packet_shape_and_uuid(self):
        """注入盒是顶层 uuid，包体含 xpacket / TC260 ns / TC260:AIGC。"""
        path = self.p("b.mp4")
        _make_clean_mp4(path)
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        data = Path(path).read_bytes()
        boxes = _xmp_uuids(data)
        self.assertEqual(1, len(boxes))
        _t, _s, body, end = boxes[0]
        text = data[body + 16:end].decode("utf-8")
        self.assertTrue(text.startswith(wm.PACKET_BEGIN))
        self.assertTrue(text.endswith(wm.PACKET_END))
        self.assertIn(wm.TC260_NS, text)
        self.assertIn("<TC260:AIGC>", text)
        self.assertEqual(24 + len(text.encode("utf-8")),
                         end - _s)  # size = 8 盒头 + 16 UUID + 包

    # ------------------------------------------------------------ 不变式
    def test_mdat_payload_unchanged(self):
        """mdat 载荷（含 mdat 盒本身）逐字节不变。"""
        path = self.p("c.mp4")
        payload = bytes(range(256)) * 8
        _make_clean_mp4(path, payload)
        before = Path(path).read_bytes()
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        self.assertEqual(payload, _body_of(after, b"mdat"))
        self.assertEqual(_box_of(before, b"mdat"), _box_of(after, b"mdat"))

    def test_ftyp_and_moov_bytes_unchanged(self):
        """ftyp / moov 的盒字节与顺序不变（只允许末尾追加）。"""
        path = self.p("d.mp4")
        _make_clean_mp4(path, b"\x01\x02")
        before = Path(path).read_bytes()
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        for btype in (b"ftyp", b"moov"):
            self.assertEqual(_box_of(before, btype), _box_of(after, btype))
        self.assertEqual(0, after.find(_box_of(before, b"ftyp")))

    def test_top_level_boxes_complete_and_plus_one(self):
        """顶层盒结构完整（_boxes 恰好走完文件），数量 +1。"""
        path = self.p("e.mp4")
        _make_clean_mp4(path)
        before = Path(path).read_bytes()
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        self.assertEqual(len(_top(before)) + 1, len(_top(after)))
        pos = 0
        for _t, _s, _body, end in _top(after):
            self.assertEqual(pos, _s)
            pos = end
        self.assertEqual(len(after), pos)

    def test_64bit_largesize_box_survives(self):
        """含 64 位 largesize 顶层盒的文件：该盒字节原样保留。"""
        path = self.p("f.mp4")
        ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512))
        free = _box(b"free", b"\x00" * 32, large=True)
        data = ftyp + free + _box(b"mdat", b"ok")
        Path(path).write_bytes(data)
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        self.assertEqual(free, _box_of(after, b"free"))
        self.assertEqual(b"ok", _body_of(after, b"mdat"))

    # ------------------------------------------------------------ 替换/幂等
    def test_repeat_inject_keeps_single_top_level_xmp(self):
        """重复写入：顶层 XMP 只有 1 份，内容为最后一次。"""
        path = self.p("g.mp4")
        _make_clean_mp4(path)
        wm.inject_mp4_xmp(path, _json_text({"v": 1}))
        wm.inject_mp4_xmp(path, _json_text({"v": 2}))
        data = Path(path).read_bytes()
        self.assertEqual(1, len(_xmp_uuids(data)))
        self.assertEqual(4, len(_top(data)))
        objs = [c["obj"] for c in md.extract_json_candidates(path)]
        self.assertIn({"v": 2}, objs)
        self.assertNotIn({"v": 1}, objs)

    def test_fixture_nested_xmp_not_touched(self):
        """夹具里 moov/udta 内的 XMP 不删除（硬约束：不动 moov 字节）。"""
        path = self.p("h.mp4")
        md.make_mp4_with_xmp(path, "<x:xmpmeta/>")
        before = Path(path).read_bytes()
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        self.assertEqual(_box_of(before, b"moov"), _box_of(after, b"moov"))
        self.assertEqual(_box_of(before, b"mdat"), _box_of(after, b"mdat"))

    def test_mp4_with_ilst_entries_preserved(self):
        """带 udta/meta/ilst 的文件：原有条目仍可提取，且 moov 不变。"""
        path = self.p("i.mp4")
        md.make_mp4_with_ilst(path, {b"\xa9too": "nf"})
        before = Path(path).read_bytes()
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        after = Path(path).read_bytes()
        self.assertEqual(_box_of(before, b"moov"), _box_of(after, b"moov"))
        keys = {i["key"]: i["text"] for i in md.extract(path)
                if i["container"] == "mp4.ilst"}
        self.assertEqual("nf", keys.get("\xa9too"))

    # ------------------------------------------------------------ 转义
    def test_xml_escaping_roundtrip(self):
        """JSON 里的 & < > 在文件里被转义，读回仍是原 JSON。"""
        path = self.p("j.mp4")
        _make_clean_mp4(path)
        payload = {"s": "<tag> & \"q\" 'a'", "n": 7}
        wm.inject_mp4_xmp(path, _json_text(payload))
        raw = Path(path).read_bytes()
        self.assertIn(b"&lt;tag&gt;", raw)
        self.assertIn(b"&amp;", raw)
        objs = [c["obj"] for c in md.extract_json_candidates(path)]
        self.assertIn(payload, objs)

    # ------------------------------------------------------------ 坏文件
    def test_bad_files_raise_value_error(self):
        cases = {
            "empty": b"",
            "short": b"\x00\x00\x00\x10ftyp",
            "garbage": b"not-an-mp4",
            "zero-size": struct.pack(">I", 0) + b"mdat",
        }
        for name, data in cases.items():
            path = self.p(name + ".mp4")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wm.inject_mp4_xmp(path, _json_text(PAYLOAD))

    def test_bad_json_leaves_file_untouched(self):
        path = self.p("k.mp4")
        _make_clean_mp4(path)
        before = Path(path).read_bytes()
        with self.assertRaises(ValueError):
            wm.inject_mp4_xmp(path, "{not json")
        self.assertEqual(before, Path(path).read_bytes())

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            wm.inject_mp4_xmp(self.p("no-such.mp4"), "{}")

    def test_no_temp_file_left_behind(self):
        path = self.p("l.mp4")
        _make_clean_mp4(path)
        wm.inject_mp4_xmp(path, _json_text(PAYLOAD))
        leftovers = [n for n in os.listdir(self.dir)
                     if n.startswith(".nf-xmp-")]
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
