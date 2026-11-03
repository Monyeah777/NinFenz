"""writers_ogg.inject_ogg 的单元测试（OGG Vorbis / Opus）。

作者：gate（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_ogg -v

覆盖：页/段表/包重组、注释页重建（含多页）、后续页 seq 顺延与 CRC 重算、
音频包字节不变、识别页原样、重复写只留 1 份 AIGC、其它注释/vendor 保留、
Opus 变体（无 framing bit）、无音频页（EOS）、幂等（字节级）、坏文件
ValueError、原子写无残留。
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
from core.labeling import writers_ogg as wo

PAYLOAD = {"AIGC": {"Label": 1, "Producer": "测试", "n": 7}}
JSON = json.dumps(PAYLOAD, ensure_ascii=False)
SERIAL = 0x0BADC0DE


# ---------------------------------------------------------------- 独立 CRC
def _crc_table() -> list:
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = (((r << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                 if r & 0x80000000 else (r << 1) & 0xFFFFFFFF)
        table.append(r)
    return table


_TABLE = _crc_table()


def _crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _TABLE[((crc >> 24) & 0xFF) ^ byte]
    return crc


# ---------------------------------------------------------------- 页面构造
def _page(ht: int, granule: int, serial: int, seq: int,
          laces, payload: bytes) -> bytes:
    assert len(payload) == sum(laces)
    head = bytearray(b"OggS" + b"\x00" + bytes([ht]))
    head += struct.pack("<q", granule) + struct.pack("<I", serial)
    head += struct.pack("<I", seq) + b"\x00\x00\x00\x00"
    head += bytes([len(laces)]) + bytes(laces) + payload
    return (bytes(head[:22]) + struct.pack("<I", _crc(bytes(head)))
            + bytes(head[26:]))


def _paginate(packets) -> list:
    """包 → [(header_type, laces, payload)]（每页 ≤255 段）。"""
    laces, payload = [], bytearray()
    for pkt in packets:
        off = 0
        while True:
            n = min(255, len(pkt) - off)
            laces.append(n)
            payload += pkt[off:off + n]
            off += n
            if n < 255:
                break
            if off == len(pkt):
                laces.append(0)
                break
    pages, pos, continued = [], 0, False
    while pos < len(laces):
        take = laces[pos:pos + 255]
        start = sum(laces[:pos])
        end = start + sum(take)
        pages.append((0x01 if continued else 0x00, take,
                      bytes(payload[start:end])))
        continued = take[-1] == 255
        pos += 255
    return pages


def _comment_packet(codec: str, vendor: bytes, comments,
                    framing: bool) -> bytes:
    body = [struct.pack("<I", len(vendor)), vendor,
            struct.pack("<I", len(comments))]
    for item in comments:
        body.append(struct.pack("<I", len(item)))
        body.append(item)
    if framing:
        body.append(b"\x01")
    magic = b"\x03vorbis" if codec == "vorbis" else b"OpusTags"
    return magic + b"".join(body)


def _make_ogg(path: str, codec: str = "vorbis",
              vendor: bytes = b"fixture",
              comments=(b"ARTIST=x", b"TITLE=y"),
              audio=(b"\x00" * 40, b"\x11" * 40),
              extra_pad: int = 0) -> None:
    framing = codec == "vorbis"
    comments = list(comments)
    if extra_pad:
        comments.append(b"PAD=" + b"x" * extra_pad)
    if codec == "vorbis":
        ident = b"\x01vorbis" + b"\x00" * 23
        headers = [_comment_packet(codec, vendor, comments, True),
                   b"\x05vorbis" + b"\x00" * 7]
    else:
        ident = b"OpusHead" + b"\x00" * 11
        headers = [_comment_packet(codec, vendor, comments, False)]
    out = [_page(0x02, 0, SERIAL, 0, _laces_of(ident).__getitem__(0),
                 ident)]
    seq = 1
    for ht, laces, payload in _paginate(headers):
        out.append(_page(ht, 0, SERIAL, seq, laces, payload))
        seq += 1
    if audio:
        for i, pkt in enumerate(audio):
            laces, payload = _laces_of(pkt)
            ht = 0x04 if i == len(audio) - 1 else 0x00
            out.append(_page(ht, 1024 * (i + 1), SERIAL, seq, laces, payload))
            seq += 1
    else:
        last = out[-1]
        raise AssertionError("headers-only 用 _make_headers_only")
    Path(path).write_bytes(b"".join(out))


def _laces_of(pkt: bytes):
    laces = []
    off = 0
    while True:
        n = min(255, len(pkt) - off)
        laces.append(n)
        off += n
        if n < 255:
            return laces, pkt
        if off == len(pkt):
            laces.append(0)
            return laces, pkt


def _make_headers_only(path: str) -> None:
    ident = b"\x01vorbis" + b"\x00" * 23
    headers = [_comment_packet("vorbis", b"v", [b"ARTIST=x"], True),
               b"\x05vorbis" + b"\x00" * 7]
    out = [_page(0x02, 0, SERIAL, 0, *_laces_of(ident))]
    seq = 1
    specs = _paginate(headers)
    for i, (ht, laces, payload) in enumerate(specs):
        if i == len(specs) - 1:
            ht |= 0x04
        out.append(_page(ht, 0, SERIAL, seq, laces, payload))
        seq += 1
    Path(path).write_bytes(b"".join(out))


# ---------------------------------------------------------------- 独立解析
def _parse_pages(data: bytes) -> list:
    pages, pos = [], 0
    while pos < len(data):
        assert data[pos:pos + 4] == b"OggS"
        assert data[pos + 4] == 0
        ht = data[pos + 5]
        granule = struct.unpack("<q", data[pos + 6:pos + 14])[0]
        serial = struct.unpack("<I", data[pos + 14:pos + 18])[0]
        seq = struct.unpack("<I", data[pos + 18:pos + 22])[0]
        crc = struct.unpack("<I", data[pos + 22:pos + 26])[0]
        nseg = data[pos + 26]
        segs = data[pos + 27:pos + 27 + nseg]
        body = pos + 27 + nseg
        plen = sum(segs)
        end = body + plen
        raw = bytearray(data[pos:end])
        raw[22:26] = b"\x00" * 4
        assert _crc(bytes(raw)) == crc, ("CRC 不匹配", seq)
        pages.append({"ht": ht, "granule": granule, "serial": serial,
                      "seq": seq, "laces": list(segs),
                      "payload": data[body:end],
                      "raw": data[pos:end]})
        pos = end
    return pages


def _packets(pages) -> list:
    out, cur = [], bytearray()
    for page in pages:
        off = 0
        for lace in page["laces"]:
            cur += page["payload"][off:off + lace]
            off += lace
            if lace < 255:
                out.append(bytes(cur))
                cur = bytearray()
    assert not cur
    return out


def _comment(packet: bytes):
    magic = (b"\x03vorbis" if packet.startswith(b"\x03vorbis")
             else b"OpusTags")
    body = packet[len(magic):]
    vlen = int.from_bytes(body[0:4], "little")
    vendor = body[4:4 + vlen]
    off = 4 + vlen
    count = int.from_bytes(body[off:off + 4], "little")
    off += 4
    comments = []
    for _ in range(count):
        clen = int.from_bytes(body[off:off + 4], "little")
        comments.append(body[off + 4:off + 4 + clen])
        off += 4 + clen
    framing = None
    if magic == b"\x03vorbis":
        framing = body[off]
        off += 1
    assert off == len(body), (off, len(body))
    return magic, vendor, comments, framing


def _aigc_values(comments) -> list:
    return [c[len(b"AIGC="):] for c in comments
            if c.startswith(b"AIGC=")]


class OggWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name: str) -> str:
        return str(self.dir / name)

    # ============================================================ Vorbis
    def test_vorbis_roundtrip_structure(self):
        path = self.p("a.ogg")
        _make_ogg(path)
        wo.inject_ogg(path, JSON)
        pages = _parse_pages(Path(path).read_bytes())
        packets = _packets(pages)
        magic, vendor, comments, framing = _comment(packets[1])
        self.assertEqual(b"\x03vorbis", magic)
        self.assertEqual(b"fixture", vendor)
        self.assertEqual(1, framing & 0x01)
        self.assertEqual([PAYLOAD], [json.loads(v.decode("utf-8"))
                                     for v in _aigc_values(comments)])

    def test_metadata_roundtrip(self):
        path = self.p("b.ogg")
        _make_ogg(path)
        wo.inject_ogg(path, JSON)
        cands = md.extract_json_candidates(path)
        self.assertIn(PAYLOAD, [c["obj"] for c in cands if c.get("obj")])

    def test_audio_packets_unchanged(self):
        path = self.p("c.ogg")
        _make_ogg(path)
        before = _packets(_parse_pages(Path(path).read_bytes()))
        wo.inject_ogg(path, JSON)
        after = _packets(_parse_pages(Path(path).read_bytes()))
        self.assertEqual(before[3:], after[3:])

    def test_ident_page_unchanged(self):
        path = self.p("d.ogg")
        _make_ogg(path)
        before = _parse_pages(Path(path).read_bytes())
        wo.inject_ogg(path, JSON)
        after = _parse_pages(Path(path).read_bytes())
        self.assertEqual(before[0]["raw"], after[0]["raw"])

    def test_idempotent_bytes(self):
        path = self.p("e.ogg")
        _make_ogg(path)
        wo.inject_ogg(path, JSON)
        first = Path(path).read_bytes()
        wo.inject_ogg(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())

    def test_single_aigc_and_replacement(self):
        path = self.p("f.ogg")
        _make_ogg(path)
        wo.inject_ogg(path, JSON)
        second = json.dumps({"AIGC": {"Label": 2}}, ensure_ascii=False)
        wo.inject_ogg(path, second)
        packets = _packets(_parse_pages(Path(path).read_bytes()))
        _m, _v, comments, _fr = _comment(packets[1])
        values = _aigc_values(comments)
        self.assertEqual(1, len(values))
        self.assertEqual(second.encode("utf-8"), values[0])
        self.assertIn(b"ARTIST=x", comments)

    def test_other_comments_and_vendor_preserved(self):
        path = self.p("g.ogg")
        _make_ogg(path, vendor=b"my vendor",
                  comments=(b"ARTIST=x", b"TITLE=y", b"DATE=2026"))
        wo.inject_ogg(path, JSON)
        packets = _packets(_parse_pages(Path(path).read_bytes()))
        _m, vendor, comments, _fr = _comment(packets[1])
        self.assertEqual(b"my vendor", vendor)
        self.assertEqual([b"ARTIST=x", b"TITLE=y", b"DATE=2026"],
                         [c for c in comments if not c.startswith(b"AIGC=")])

    def test_crc_and_seq_continuous(self):
        path = self.p("h.ogg")
        _make_ogg(path)
        wo.inject_ogg(path, JSON)
        pages = _parse_pages(Path(path).read_bytes())
        self.assertEqual(list(range(len(pages))),
                         [p["seq"] for p in pages])
        self.assertEqual({SERIAL}, {p["serial"] for p in pages})

    def test_audio_seq_shift_when_header_pages_grow(self):
        path = self.p("i.ogg")
        _make_ogg(path)
        before = _parse_pages(Path(path).read_bytes())
        # 用超长 JSON 把注释头挤成多页，后续音频页 seq 必须顺延
        big = json.dumps({"AIGC": {"pad": "y" * 70000}}, ensure_ascii=False)
        wo.inject_ogg(path, big)
        after = _parse_pages(Path(path).read_bytes())
        audio_before = [p for p in before if p["granule"] > 0]
        audio_after = [p for p in after if p["granule"] > 0]
        self.assertEqual(len(audio_before), len(audio_after))
        self.assertGreater(len(after), len(before))
        for b, a in zip(audio_before, audio_after):
            self.assertEqual(b["payload"], a["payload"])
            self.assertEqual(b["granule"], a["granule"])
        self.assertEqual(list(range(len(after))),
                         [p["seq"] for p in after])

    def test_multipage_comment_valid(self):
        path = self.p("j.ogg")
        _make_ogg(path)
        big = json.dumps({"AIGC": {"pad": "z" * 70000}}, ensure_ascii=False)
        wo.inject_ogg(path, big)
        packets = _packets(_parse_pages(Path(path).read_bytes()))
        values = _aigc_values(_comment(packets[1])[2])
        self.assertEqual([json.loads(big)], [json.loads(v) for v in values])

    def test_headers_only_eos(self):
        path = self.p("k.ogg")
        _make_headers_only(path)
        wo.inject_ogg(path, JSON)
        pages = _parse_pages(Path(path).read_bytes())
        self.assertTrue(pages[-1]["ht"] & 0x04)   # 末页 EOS
        packets = _packets(pages)
        self.assertEqual([JSON.encode("utf-8")],
                         _aigc_values(_comment(packets[1])[2]))
        self.assertEqual(list(range(len(pages))),
                         [p["seq"] for p in pages])

    # ============================================================ Opus
    def test_opus_roundtrip_no_framing(self):
        path = self.p("l.ogg")
        _make_ogg(path, codec="opus")
        wo.inject_ogg(path, JSON)
        pages = _parse_pages(Path(path).read_bytes())
        packets = _packets(pages)
        self.assertTrue(packets[0].startswith(b"OpusHead"))
        magic, _vendor, comments, _fr = _comment(packets[1])
        self.assertEqual(b"OpusTags", magic)
        self.assertEqual([JSON.encode("utf-8")], _aigc_values(comments))
        self.assertEqual([PAYLOAD],
                         [c["obj"] for c in md.extract_json_candidates(path)
                          if c.get("obj")])
        self.assertEqual(len(packets), 2 + 2)   # 头部 2 包 + 音频 2 包

    # ============================================================ 坏输入
    def test_bad_files(self):
        good = self.p("good.ogg")
        _make_ogg(good)
        data = Path(good).read_bytes()
        cases = {
            "not-ogg": b"JUNK" + b"\x00" * 64,
            "truncated": data[:40],
            "bad-version": data[:4] + b"\x01" + data[5:],
        }
        for name, blob in cases.items():
            path = self.p("bad-" + name + ".ogg")
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError, msg=name):
                wo.inject_ogg(path, JSON)
        # CRC 损坏（改 payload 不动 CRC）
        pages = _parse_pages(data)
        off = data.find(pages[1]["payload"])
        broken = bytearray(data)
        broken[off] ^= 0xFF
        path = self.p("bad-crc.ogg")
        Path(path).write_bytes(bytes(broken))
        with self.assertRaises(ValueError):
            wo.inject_ogg(path, JSON)
        # serial 不一致
        other = _page(0, 0, SERIAL + 1, len(pages),
                      *_laces_of(b"\x00" * 8))
        path = self.p("bad-serial.ogg")
        Path(path).write_bytes(data + other)
        with self.assertRaises(ValueError):
            wo.inject_ogg(path, JSON)
        # 缺 framing bit
        bad_comment = (b"\x03vorbis" + struct.pack("<I", 1) + b"v"
                       + struct.pack("<I", 0))
        ident = b"\x01vorbis" + b"\x00" * 23
        out = [_page(0x02, 0, SERIAL, 0, *_laces_of(ident))]
        for i, (ht, laces, payload) in enumerate(_paginate([bad_comment])):
            out.append(_page(ht, 0, SERIAL, 1 + i, laces, payload))
        path = self.p("bad-framing.ogg")
        Path(path).write_bytes(b"".join(out))
        with self.assertRaises(ValueError):
            wo.inject_ogg(path, JSON)
        # 注释计数越界
        bad_count = (b"\x03vorbis" + struct.pack("<I", 1) + b"v"
                     + struct.pack("<I", 99) + b"\x01")
        out = [_page(0x02, 0, SERIAL, 0, *_laces_of(ident))]
        for i, (ht, laces, payload) in enumerate(_paginate([bad_count])):
            out.append(_page(ht, 0, SERIAL, 1 + i, laces, payload))
        path = self.p("bad-count.ogg")
        Path(path).write_bytes(b"".join(out))
        with self.assertRaises(ValueError):
            wo.inject_ogg(path, JSON)
        # 音频包与头部包同页
        mixed = _lace_mixed_page()
        path = self.p("bad-mixed.ogg")
        Path(path).write_bytes(mixed)
        with self.assertRaises(ValueError) as ctx:
            wo.inject_ogg(path, JSON)
        self.assertIn("granule", str(ctx.exception))

    def test_invalid_json_leaves_file_untouched(self):
        path = self.p("m.ogg")
        _make_ogg(path)
        before = Path(path).read_bytes()
        with self.assertRaises(ValueError):
            wo.inject_ogg(path, "{not json")
        self.assertEqual(before, Path(path).read_bytes())

    def test_atomic_no_temp_file_and_mode(self):
        path = self.p("n.ogg")
        _make_ogg(path)
        os.chmod(path, 0o640)
        wo.inject_ogg(path, JSON)
        leftovers = [n for n in os.listdir(self.dir)
                     if n.startswith(".nf-ogg-")]
        self.assertEqual([], leftovers)
        self.assertEqual(0o640, os.stat(path).st_mode & 0o7777)


def _lace_mixed_page() -> bytes:
    """识别页 + 一页同时装 comment/setup/audio（音频包不在页起点）。"""
    ident = b"\x01vorbis" + b"\x00" * 23
    comment = _comment_packet("vorbis", b"v", [b"A=x"], True)
    setup = b"\x05vorbis" + b"\x00" * 7
    audio = b"\x00" * 32
    pages = [_page(0x02, 0, SERIAL, 0, *_laces_of(ident))]
    out = []
    for ht, laces, payload in _paginate([comment, setup, audio]):
        out.append((ht, laces, payload))
    seq = 1
    for ht, laces, payload in out:
        pages.append(_page(ht, 0, SERIAL, seq, laces, payload))
        seq += 1
    return b"".join(pages)


if __name__ == "__main__":
    unittest.main()
