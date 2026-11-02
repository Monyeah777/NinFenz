"""writers_mp4.inject_mp4_meta（GB 20257A 标准位置）的单元测试。

作者：gate（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_mp4_meta -v

覆盖：moov.udta.meta keys/ilst 往返（metadata.extract 解析 mdta 键名）、
mdat 载荷不变、stco/co64 偏移修正、顶层结构完整、moof/largesize/size=0 拒绝、
幂等、旧 udta/未知 moov 盒保留、旧顶层 XMP uuid 移除、既有 key 索引复用、
moov 在 mdat 之后的 delta=0 分支、坏文件 ValueError。
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

CONTAINERS = {
    b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf",
    b"mvex", b"udta", b"meta", b"moof", b"traf",
}
JSON_OBJ = {"AIGC": {"Label": 1, "ContentProducer": "1" * 27}}
JSON = json.dumps(JSON_OBJ, ensure_ascii=False)


# ---------------------------------------------------------------- 读盒工具
def _box(btype: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + btype + payload


def _children(data: bytes, start: int, end: int):
    """独立解析盒（不复用 writers 的解析器）：→ (type, box_start, body, end)。"""
    out = []
    off = start
    while off < end:
        if off + 8 > end:
            raise AssertionError("盒头越界：%d" % off)
        size = int.from_bytes(data[off:off + 4], "big")
        btype = data[off + 4:off + 8]
        assert size >= 8 and off + size <= end, (off, size, end)
        out.append((btype, off, off + 8, off + size))
        off += size
    return out


def _top(data: bytes):
    return _children(data, 0, len(data))


def _find(data: bytes, start: int, end: int, btype: bytes):
    return [b for b in _children(data, start, end) if b[0] == btype]


def _mdat_payload(data: bytes) -> bytes:
    box = [b for b in _top(data) if b[0] == b"mdat"][0]
    return data[box[2]:box[3]]


def _mdat_start(data: bytes) -> int:
    return [b for b in _top(data) if b[0] == b"mdat"][0][1]


def _stco(data: bytes):
    """收集 moov 内所有 stco/co64 → [(类型, [条目值])]。"""
    res = []

    def walk(start, end):
        for btype, _s, body, bend in _children(data, start, end):
            if btype in (b"stco", b"co64"):
                width = 4 if btype == b"stco" else 8
                size = bend - body
                std = int.from_bytes(data[body + 4:body + 8], "big")
                if size == 8 + std * width:
                    count, off = std, body + 8
                else:
                    count = int.from_bytes(data[body:body + 4], "big")
                    assert size == 4 + count * width, (btype, size, count)
                    off = body + 4
                vals = [int.from_bytes(
                    data[off + i * width:off + (i + 1) * width], "big")
                    for i in range(count)]
                res.append((btype, vals))
            elif btype == b"meta":
                walk(body + 4, bend)
            elif btype in CONTAINERS:
                walk(body, bend)

    for btype, _s, body, bend in _top(data):
        if btype == b"moov":
            walk(body, bend)
    return res


def _moov_child(data: bytes, types):
    m = [b for b in _top(data) if b[0] == b"moov"][0]
    return [b for b in _children(data, m[2], m[3]) if b[0] in types]


def _meta(data: bytes):
    udta = _moov_child(data, {b"udta"})[0]
    return _find(data, udta[2], udta[3], b"meta")[0]


# ---------------------------------------------------------------- 本地夹具
def _make_local(path: str, payload: bytes = b"PAYLOAD",
                extra_moov: bytes = b"", udta_extra: bytes = b"",
                meta: bytes = b"", moov_after_mdat: bool = False,
                standard_stco: bool = False) -> None:
    """按夹具同构构造 MP4；可附加 moov 未知盒 / 旧 udta / 旧 meta。"""
    ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512)
                + b"isomiso2mp41")
    mdat = _box(b"mdat", payload)

    def build(off: int, moov_len: int = 0) -> bytes:
        if standard_stco:      # ISO 标准：version/flags + entry_count + 条目
            stco = _box(b"stco", struct.pack(">III", 0, 1, off))
        else:                  # 简化布局（与 metadata 夹具一致）
            stco = _box(b"stco", struct.pack(">II", 1, off))
        stbl = _box(b"stbl", stco)
        minf = _box(b"minf", stbl)
        mdia = _box(b"mdia", minf)
        trak = _box(b"trak", mdia)
        mvhd = _box(b"mvhd", b"\x00" * 8)
        udta = _box(b"udta", udta_extra + meta) if (
            udta_extra or meta) else b""
        return _box(b"moov", mvhd + trak + extra_moov + udta)

    if moov_after_mdat:
        moov0 = build(0)
        off = len(ftyp) + 8
        Path(path).write_bytes(ftyp + mdat + build(off))
        return
    moov = build(0)
    payload_off = len(ftyp) + len(moov) + 8
    moov = build(payload_off)
    Path(path).write_bytes(ftyp + moov + mdat)


def _keys_box(names) -> bytes:
    entries = b"".join(struct.pack(">I", 8 + len(n)) + b"mdta" + n
                       for n in names)
    return _box(b"keys", struct.pack(">II", 0, len(names)) + entries)


def _hdlr_box() -> bytes:
    return _box(b"hdlr", struct.pack(">II", 0, 0) + b"mdir" + b"\x00" * 12)


class Mp4MetaWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name: str) -> str:
        return str(self.dir / name)

    # ------------------------------------------------------------ 往返
    def test_roundtrip_standard_meta(self):
        path = self.p("a.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        cands = md.extract_json_candidates(path)
        objs = [c["obj"] for c in cands if c.get("obj") is not None]
        self.assertIn(JSON_OBJ, objs, cands)
        items = md.extract(path)
        self.assertTrue(any(i["container"] == "mp4.ilst"
                            and i["key"] == "AIGC" for i in items), items)

    def test_mdat_payload_unchanged(self):
        path = self.p("b.mp4")
        md.make_mp4_with_stco(path)
        before = Path(path).read_bytes()
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        self.assertEqual(_mdat_payload(before), _mdat_payload(after))
        self.assertEqual(b"NF-MEDIA-PAYLOAD", _mdat_payload(after))

    # ------------------------------------------------------------ 偏移
    def test_stco_offset_shifted(self):
        path = self.p("c.mp4")
        md.make_mp4_with_stco(path)
        before = Path(path).read_bytes()
        old_stco = _stco(before)[0][1][0]
        old_mdat = _mdat_start(before)
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        new_stco = _stco(after)[0][1][0]
        new_mdat = _mdat_start(after)
        self.assertGreater(new_mdat, old_mdat)      # moov 变长、mdat 后移
        self.assertEqual(new_stco - old_stco, new_mdat - old_mdat)
        self.assertEqual(new_stco - new_mdat, old_stco - old_mdat)
        self.assertIn(new_stco, range(new_mdat, new_mdat + 8 + 16))

    def test_co64_offset_also_shifted(self):
        path = self.p("d.mp4")
        payload = b"X" * 32
        ftyp = _box(b"ftyp", b"isom")
        mdat = _box(b"mdat", payload)

        def build(off: int) -> bytes:
            stco = _box(b"co64", struct.pack(">IQ", 1, off))
            stbl = _box(b"stbl", stco)
            trak = _box(b"trak", _box(b"mdia", _box(b"minf", stbl)))
            return _box(b"moov", _box(b"mvhd", b"\x00" * 8) + trak)

        moov = build(0)
        off = len(ftyp) + len(moov) + 8
        Path(path).write_bytes(ftyp + build(off) + mdat)
        before = Path(path).read_bytes()
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        self.assertEqual(
            _stco(after)[0][1][0] - _stco(before)[0][1][0],
            _mdat_start(after) - _mdat_start(before))

    def test_moov_after_mdat_delta_zero(self):
        path = self.p("e.mp4")
        _make_local(path, moov_after_mdat=True)
        before = Path(path).read_bytes()
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        self.assertEqual(_stco(before), _stco(after))   # 偏移不变
        self.assertEqual(_mdat_start(before), _mdat_start(after))
        self.assertEqual([b[0] for b in _top(after)],
                         [b"ftyp", b"mdat", b"moov"])

    # ------------------------------------------------------------ 结构
    def test_top_level_complete(self):
        path = self.p("f.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        data = Path(path).read_bytes()
        types = [b[0] for b in _top(data)]
        self.assertEqual([b"ftyp", b"moov", b"mdat"], types)
        self.assertEqual(len(data), sum(b[3] - b[1] for b in _top(data)))

    def test_meta_structure(self):
        path = self.p("g.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        data = Path(path).read_bytes()
        meta = _meta(data)
        # meta 是 fullbox：前 4 字节版本/标志
        self.assertEqual(b"\x00\x00\x00\x00", data[meta[2]:meta[2] + 4])
        kids = _children(data, meta[2] + 4, meta[3])
        by_type = {k[0]: k for k in kids}
        for need in (b"hdlr", b"keys", b"ilst"):
            self.assertIn(need, by_type)
        hdlr = data[by_type[b"hdlr"][2]:by_type[b"hdlr"][3]]
        self.assertEqual(b"mdir", hdlr[8:12])  # payload: 4+4 后是 handler
        keys_body = data[by_type[b"keys"][2]:by_type[b"keys"][3]]
        self.assertEqual(1, int.from_bytes(keys_body[4:8], "big"))
        entry = keys_body[8:]
        self.assertEqual(8 + 4, int.from_bytes(entry[0:4], "big"))
        self.assertEqual(b"mdta", entry[4:8])
        self.assertEqual(b"AIGC", entry[8:8 + 4])
        ilst = _children(data, by_type[b"ilst"][2], by_type[b"ilst"][3])
        self.assertEqual(1, len(ilst))
        self.assertEqual(b"\x00\x00\x00\x01", ilst[0][0])
        inner = _children(data, ilst[0][2], ilst[0][3])
        self.assertEqual(b"data", inner[0][0])
        payload = data[inner[0][2]:inner[0][3]]
        self.assertEqual(1, int.from_bytes(payload[0:4], "big"))
        self.assertEqual(0, int.from_bytes(payload[4:8], "big"))
        self.assertEqual(JSON.encode("utf-8"), payload[8:])

    # ------------------------------------------------------------ 幂等/替换
    def test_idempotent_same_json(self):
        path = self.p("h.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        first = Path(path).read_bytes()
        wm.inject_mp4_meta(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())

    def test_rewrite_updates_single_entry(self):
        path = self.p("i.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        second = '{"AIGC": {"Label": 2}}'
        wm.inject_mp4_meta(path, second)
        objs = [c["obj"] for c in md.extract_json_candidates(path)]
        self.assertEqual([{"AIGC": {"Label": 2}}], objs)
        data = Path(path).read_bytes()
        meta = _meta(data)
        kids = _children(data, meta[2] + 4, meta[3])
        by_type = {k[0]: k for k in kids}
        keys_body = data[by_type[b"keys"][2]:by_type[b"keys"][3]]
        self.assertEqual(1, int.from_bytes(keys_body[4:8], "big"))
        ilst = _children(data, by_type[b"ilst"][2], by_type[b"ilst"][3])
        self.assertEqual(1, len(ilst))

    def test_removes_old_top_level_xmp_uuid(self):
        path = self.p("j.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_xmp(path, '{"old": 1}')
        self.assertIn(b"uuid", [b[0] for b in _top(Path(path).read_bytes())])
        wm.inject_mp4_meta(path, JSON)
        types = [b[0] for b in _top(Path(path).read_bytes())]
        self.assertNotIn(b"uuid", types)
        self.assertEqual([JSON_OBJ],
                         [c["obj"] for c in md.extract_json_candidates(path)])

    # ------------------------------------------------------------ 保留
    def test_preserves_unknown_moov_children(self):
        path = self.p("k.mp4")
        free = _box(b"free", b"\x11" * 8)
        _make_local(path, extra_moov=free)
        before = Path(path).read_bytes()
        moov0 = [b for b in _top(before) if b[0] == b"moov"][0]
        old_mvhd = _find(before, moov0[2], moov0[3], b"mvhd")[0]
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        moov = [b for b in _top(after) if b[0] == b"moov"][0]
        types = [b[0] for b in _children(after, moov[2], moov[3])]
        self.assertEqual([b"mvhd", b"trak", b"free", b"udta"], types)
        new_free = _find(after, moov[2], moov[3], b"free")[0]
        self.assertEqual(free, after[new_free[1]:new_free[3]])
        new_mvhd = _find(after, moov[2], moov[3], b"mvhd")[0]
        self.assertEqual(before[old_mvhd[1]:old_mvhd[3]],
                         after[new_mvhd[1]:new_mvhd[3]])

    def test_preserves_existing_udta_children(self):
        path = self.p("l.mp4")
        cprt = _box(b"cprt", b"\x00" * 4)
        _make_local(path, udta_extra=cprt)
        wm.inject_mp4_meta(path, JSON)
        data = Path(path).read_bytes()
        udta = _moov_child(data, {b"udta"})[0]
        kids = _children(data, udta[2], udta[3])
        self.assertEqual(b"cprt", kids[0][0])
        self.assertEqual(cprt, data[kids[0][1]:kids[0][3]])
        self.assertEqual(b"meta", kids[-1][0])

    def test_reuses_existing_key_index(self):
        path = self.p("m.mp4")
        meta = _box(b"meta", struct.pack(">I", 0) + _hdlr_box()
                    + _keys_box([b"FOO", b"AIGC"]))
        _make_local(path, meta=meta)
        wm.inject_mp4_meta(path, JSON)
        data = Path(path).read_bytes()
        m = _meta(data)
        kids = _children(data, m[2] + 4, m[3])
        by_type = {k[0]: k for k in kids}
        keys_body = data[by_type[b"keys"][2]:by_type[b"keys"][3]]
        self.assertEqual(2, int.from_bytes(keys_body[4:8], "big"))
        ilst = _children(data, by_type[b"ilst"][2], by_type[b"ilst"][3])
        self.assertEqual(1, len(ilst))
        self.assertEqual(struct.pack(">I", 2), ilst[0][0])   # AIGC 的索引
        self.assertEqual([JSON_OBJ],
                         [c["obj"] for c in md.extract_json_candidates(path)])

    def test_standard_stco_layout_patched(self):
        """ISO 标准 stco（version/flags + count + 条目）也能被识别并修正。"""
        path = self.p("s.mp4")
        _make_local(path, standard_stco=True)
        before = Path(path).read_bytes()
        wm.inject_mp4_meta(path, JSON)
        after = Path(path).read_bytes()
        self.assertEqual(
            _stco(after)[0][1][0] - _stco(before)[0][1][0],
            _mdat_start(after) - _mdat_start(before))
        self.assertIn(JSON_OBJ,
                      [c["obj"] for c in md.extract_json_candidates(path)])

    def test_removes_nested_udta_xmp_uuid(self):
        """兼容载体嵌在 moov/udta 内时同样被清除（一份标识）。"""
        path = self.p("t.mp4")
        md.make_mp4_with_xmp(path, "<x:xmpmeta/>")
        self.assertTrue(any(i["container"] == "mp4.uuid"
                            for i in md.extract(path)))
        wm.inject_mp4_meta(path, JSON)
        items = md.extract(path)
        self.assertFalse(any(i["container"] == "mp4.uuid" for i in items))
        self.assertEqual([JSON_OBJ],
                         [c["obj"] for c in md.extract_json_candidates(path)])

    # ------------------------------------------------------------ 拒绝
    def test_moof_rejected(self):
        path = self.p("n.mp4")
        md.make_mp4_with_stco(path)
        data = Path(path).read_bytes()
        top = _top(data)
        moof = _box(b"moof", b"")
        Path(path).write_bytes(data + moof)   # 尾追 moof 也属分片面
        with self.assertRaises(ValueError) as ctx:
            wm.inject_mp4_meta(path, JSON)
        self.assertIn("moof", str(ctx.exception))

    def test_largesize_rejected(self):
        path = self.p("o.mp4")
        ftyp = _box(b"ftyp", b"isom")
        large = (struct.pack(">I", 1) + b"free"
                 + struct.pack(">Q", 16 + 8) + b"\x00" * 8)
        Path(path).write_bytes(ftyp + large)
        with self.assertRaises(ValueError) as ctx:
            wm.inject_mp4_meta(path, JSON)
        self.assertIn("largesize", str(ctx.exception))

    def test_size_zero_rejected(self):
        path = self.p("p.mp4")
        Path(path).write_bytes(struct.pack(">I", 0) + b"mdat")
        with self.assertRaises(ValueError) as ctx:
            wm.inject_mp4_meta(path, JSON)
        self.assertIn("size=0", str(ctx.exception))

    def test_bad_files_raise_value_error(self):
        cases = {
            "empty": b"",
            "short": b"\x00\x00\x00\x10ftyp",
            "garbage": b"not-an-mp4",
            "no-moov": _box(b"ftyp", b"isom") + _box(b"mdat", b"x"),
        }
        for name, data in cases.items():
            path = self.p(name + ".mp4")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wm.inject_mp4_meta(path, JSON)

    def test_bad_json_leaves_file_untouched(self):
        path = self.p("q.mp4")
        md.make_mp4_with_stco(path)
        before = Path(path).read_bytes()
        with self.assertRaises(ValueError):
            wm.inject_mp4_meta(path, "{not json")
        self.assertEqual(before, Path(path).read_bytes())

    def test_no_temp_file_left_behind(self):
        path = self.p("r.mp4")
        md.make_mp4_with_stco(path)
        wm.inject_mp4_meta(path, JSON)
        leftovers = [n for n in os.listdir(self.dir)
                     if n.startswith(".nf-xmp-")]
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
