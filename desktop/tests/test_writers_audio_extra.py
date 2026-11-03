"""writers_audio_extra 的单元测试（WAV / MP3 / FLAC）。

作者：gate（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_audio_extra -v

覆盖：三种容器的结构往返、fmt/data 与音频帧不变、重复写只留一份、
无 ID3 时新建、其它注释/帧保留、pad 与 syncsafe 正确、幂等（字节级）、
坏文件 ValueError、原子写无残留。
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
from core.labeling import writers_audio_extra as wa

PAYLOAD = {"AIGC": {"Label": 1, "Producer": "测试", "n": 7}}
JSON = json.dumps(PAYLOAD, ensure_ascii=False)
#: 保证字节长度是奇数（9 字节），用来验 RIFF pad。
ODD_JSON = '{"a":"x"}'


# ---------------------------------------------------------------- WAV 夹具
def _wav(path: str, data_payload: bytes = b"\x80\x81" * 8,
         extra=()) -> None:
    fmt = struct.pack("<HHIIHH", 1, 1, 8000, 16000, 2, 16)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if extra:
        for cid, payload in extra:
            body += cid + struct.pack("<I", len(payload)) + payload
            if len(payload) & 1:
                body += b"\x00"
    body += b"data" + struct.pack("<I", len(data_payload)) + data_payload
    if len(data_payload) & 1:
        body += b"\x00"
    Path(path).write_bytes(
        b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body)


def _wav_chunks(data: bytes):
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    pos, out = 12, []
    while pos < len(data):
        cid = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        ds = pos + 8
        out.append((cid, data[ds:ds + size], size))
        pos = ds + size + (size & 1)
    return out


def _riff_size_ok(data: bytes) -> bool:
    declared = int.from_bytes(data[4:8], "little")
    return declared == len(data) - 8


# ---------------------------------------------------------------- MP3 夹具
def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F,
                  (n >> 7) & 0x7F, n & 0x7F])


def _frame(fid: bytes, payload: bytes, version: int = 3) -> bytes:
    if version >= 4:
        size = _syncsafe(len(payload))
    else:
        size = struct.pack(">I", len(payload))
    return fid + size + b"\x00\x00" + payload


def _txxx(desc: str, value: str) -> bytes:
    return (b"\x03" + desc.encode("utf-8") + b"\x00"
            + value.encode("utf-8"))


def _id3(frames, version: int = 3, padding: bytes = b"") -> bytes:
    body = b"".join(frames) + padding
    return (b"ID3" + bytes([version, 0, 0]) + _syncsafe(len(body)) + body)


def _parse_id3(data: bytes):
    assert data[:3] == b"ID3"
    version = data[3]
    size = (((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F))
    end = 10 + size
    frames, pos = [], 10
    while pos + 10 <= end:
        fid = data[pos:pos + 4]
        if fid == b"\x00\x00\x00\x00":
            break
        if version >= 4:
            fsize = (((data[pos + 4] & 0x7F) << 21)
                     | ((data[pos + 5] & 0x7F) << 14)
                     | ((data[pos + 6] & 0x7F) << 7)
                     | (data[pos + 7] & 0x7F))
        else:
            fsize = int.from_bytes(data[pos + 4:pos + 8], "big")
        payload = data[pos + 10:pos + 10 + fsize]
        frames.append((fid, payload))
        pos += 10 + fsize
    return version, size, frames, data[end:]


def _txxx_pairs(payload: bytes):
    assert payload[:1] == b"\x03"
    rest = payload[1:]
    idx = rest.find(b"\x00")
    return rest[:idx].decode("utf-8"), rest[idx + 1:].decode("utf-8")


# ---------------------------------------------------------------- FLAC 夹具
def _block(btype: int, payload: bytes, last: bool = False) -> bytes:
    head = btype | (0x80 if last else 0)
    return bytes([head]) + len(payload).to_bytes(3, "big") + payload


def _streaminfo() -> bytes:
    return b"\x00" * 34


def _vorbis(vendor: bytes = b"fixture", comments=()) -> bytes:
    out = [struct.pack("<I", len(vendor)), vendor,
           struct.pack("<I", len(comments))]
    for c in comments:
        out.append(struct.pack("<I", len(c)))
        out.append(c)
    return b"".join(out)


def _flac(path: str, blocks, audio: bytes = b"\xff\xf8" + b"\x00" * 96):
    out = [b"fLaC"]
    for i, (btype, payload) in enumerate(blocks):
        out.append(_block(btype, payload, last=(i == len(blocks) - 1)))
    out.append(audio)
    Path(path).write_bytes(b"".join(out))


def _parse_flac(data: bytes):
    assert data[:4] == b"fLaC"
    pos, blocks = 4, []
    while True:
        head = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 4], "big")
        blocks.append((head & 0x7F, data[pos + 4:pos + 4 + size],
                       bool(head & 0x80)))
        pos += 4 + size
        if head & 0x80:
            break
    return blocks, data[pos:]


def _vorbis_comments(payload: bytes):
    vlen = int.from_bytes(payload[0:4], "little")
    vendor = payload[4:4 + vlen]
    off = 4 + vlen
    count = int.from_bytes(payload[off:off + 4], "little")
    off += 4
    comments = []
    for _ in range(count):
        clen = int.from_bytes(payload[off:off + 4], "little")
        comments.append(payload[off + 4:off + 4 + clen])
        off += 4 + clen
    return vendor, comments


class AudioWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name: str) -> str:
        return str(self.dir / name)

    # ============================================================ WAV
    def test_wav_roundtrip(self):
        path = self.p("a.wav")
        _wav(path)
        wa.inject_wav(path, JSON)
        data = Path(path).read_bytes()
        chunks = _wav_chunks(data)
        aigc = [c for c in chunks if c[0] == wa.WAV_CHUNK_ID]
        self.assertEqual(1, len(aigc))
        self.assertEqual(JSON.encode("utf-8"), aigc[0][1])
        self.assertTrue(_riff_size_ok(data))

    def test_wav_fmt_and_data_unchanged(self):
        path = self.p("b.wav")
        _wav(path, data_payload=b"\x11\x22\x33")
        before = _wav_chunks(Path(path).read_bytes())
        wa.inject_wav(path, JSON)
        after = _wav_chunks(Path(path).read_bytes())
        before_map = {c[0]: c[1] for c in before}
        after_map = {c[0]: c[1] for c in after}
        self.assertEqual(before_map[b"fmt "], after_map[b"fmt "])
        self.assertEqual(before_map[b"data"], after_map[b"data"])

    def test_wav_pad_for_odd_payload(self):
        path = self.p("c.wav")
        _wav(path)
        wa.inject_wav(path, ODD_JSON)
        data = Path(path).read_bytes()
        aigc = [c for c in _wav_chunks(data)
                if c[0] == wa.WAV_CHUNK_ID][0]
        self.assertEqual(len(ODD_JSON), aigc[2])
        self.assertEqual(1, len(ODD_JSON) % 2)
        self.assertEqual(0, len(data) % 2)      # 有 pad，整体偶数
        self.assertEqual(b"\x00", data[-1:])
        self.assertTrue(_riff_size_ok(data))

    def test_wav_repeat_single_and_bytes_stable(self):
        path = self.p("d.wav")
        _wav(path)
        wa.inject_wav(path, JSON)
        first = Path(path).read_bytes()
        wa.inject_wav(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())
        self.assertEqual(1, len([c for c in _wav_chunks(first)
                                 if c[0] == wa.WAV_CHUNK_ID]))

    def test_wav_replace_value(self):
        path = self.p("e.wav")
        _wav(path)
        wa.inject_wav(path, JSON)
        second = json.dumps({"AIGC": {"Label": 2}}, ensure_ascii=False)
        wa.inject_wav(path, second)
        chunks = _wav_chunks(Path(path).read_bytes())
        aigc = [c for c in chunks if c[0] == wa.WAV_CHUNK_ID]
        self.assertEqual(1, len(aigc))
        self.assertEqual(second.encode("utf-8"), aigc[0][1])
        self.assertTrue(_riff_size_ok(Path(path).read_bytes()))

    def test_wav_existing_aigc_middle_removed(self):
        path = self.p("f.wav")
        old = b"OLD"
        _wav(path, extra=[(wa.WAV_CHUNK_ID, old)])
        wa.inject_wav(path, JSON)
        chunks = _wav_chunks(Path(path).read_bytes())
        aigc = [c for c in chunks if c[0] == wa.WAV_CHUNK_ID]
        self.assertEqual(1, len(aigc))
        self.assertEqual(JSON.encode("utf-8"), aigc[0][1])
        self.assertEqual(b"data", chunks[-2][0])    # AIGC 追加在末尾
        self.assertEqual(wa.WAV_CHUNK_ID, chunks[-1][0])

    def test_wav_bad_files(self):
        cases = {
            "empty": b"",
            "not-riff": b"JUNK" + b"\x00" * 16,
            "truncated": (b"RIFF" + struct.pack("<I", 100) + b"WAVE"
                          + b"fmt " + struct.pack("<I", 16) + b"\x00"),
        }
        for name, data in cases.items():
            path = self.p(name + ".wav")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wa.inject_wav(path, JSON)

    # ============================================================ MP3
    def test_mp3_creates_id3_when_absent(self):
        path = self.p("a.mp3")
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 200
        Path(path).write_bytes(audio)
        wa.inject_mp3(path, JSON)
        data = Path(path).read_bytes()
        version, size, frames, rest = _parse_id3(data)
        self.assertEqual(3, version)
        self.assertEqual(audio, rest)
        self.assertEqual(size, len(data) - 10 - len(rest))
        txxx = [f for f in frames if f[0] == b"TXXX"]
        self.assertEqual(1, len(txxx))
        desc, value = _txxx_pairs(txxx[0][1])
        self.assertEqual("AIGC", desc)
        self.assertEqual(JSON, value)

    def test_mp3_roundtrip_via_metadata(self):
        path = self.p("b.mp3")
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 200
        Path(path).write_bytes(audio)
        wa.inject_mp3(path, JSON)
        cands = md.extract_json_candidates(path)
        self.assertIn(PAYLOAD, [c["obj"] for c in cands if c.get("obj")])

    def test_mp3_existing_frames_preserved(self):
        path = self.p("c.mp3")
        tit2 = _frame(b"TIT2", b"\x03title")
        other = _frame(b"TXXX", _txxx("OTHER", "keep"))
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 64
        Path(path).write_bytes(_id3([tit2, other]) + audio)
        wa.inject_mp3(path, JSON)
        data = Path(path).read_bytes()
        version, size, frames, rest = _parse_id3(data)
        self.assertEqual(audio, rest)
        raw = b"".join(fid + payload for fid, payload in frames)
        self.assertIn(b"TIT2", raw)
        self.assertIn(b"OTHER", raw)
        descs = [_txxx_pairs(f[1])[0] for f in frames if f[0] == b"TXXX"]
        self.assertEqual(["OTHER", "AIGC"], descs)

    def test_mp3_v24_syncsafe_sizes(self):
        path = self.p("d.mp3")
        tit2 = _frame(b"TIT2", b"\x03title", version=4)
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 32
        Path(path).write_bytes(_id3([tit2], version=4) + audio)
        wa.inject_mp3(path, JSON)
        data = Path(path).read_bytes()
        version, size, frames, rest = _parse_id3(data)
        self.assertEqual(4, version)
        self.assertEqual(audio, rest)
        # 帧 size 字段必须是 syncsafe（高位为 0）
        self.assertTrue(all(b < 0x80 for b in data[14:18]))
        txxx = [f for f in frames if f[0] == b"TXXX"]
        self.assertEqual(1, len(txxx))
        self.assertEqual("AIGC", _txxx_pairs(txxx[0][1])[0])

    def test_mp3_repeat_single_and_bytes_stable(self):
        path = self.p("e.mp3")
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 64
        Path(path).write_bytes(_id3([_frame(b"TIT2", b"\x03t")]) + audio)
        wa.inject_mp3(path, JSON)
        first = Path(path).read_bytes()
        wa.inject_mp3(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())
        _v, _s, frames, _rest = _parse_id3(first)
        descs = [_txxx_pairs(f[1])[0] for f in frames if f[0] == b"TXXX"]
        self.assertEqual(["AIGC"], descs)

    def test_mp3_duplicate_aigc_frames_deduped(self):
        path = self.p("dup.mp3")
        a1 = _frame(b"TXXX", _txxx("AIGC", "old-1"))
        a2 = _frame(b"TXXX", _txxx("AIGC", "old-2"))
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 32
        Path(path).write_bytes(_id3([a1, a2]) + audio)
        wa.inject_mp3(path, JSON)
        data = Path(path).read_bytes()
        _v, _s, frames, rest = _parse_id3(data)
        self.assertEqual(audio, rest)
        values = [_txxx_pairs(f[1])[1] for f in frames if f[0] == b"TXXX"]
        self.assertEqual([JSON], values)

    def test_mp3_replace_value(self):
        path = self.p("f.mp3")
        audio = b"\xff\xfb\x90\x00" + b"\x00" * 64
        Path(path).write_bytes(audio)
        wa.inject_mp3(path, JSON)
        second = json.dumps({"AIGC": {"Label": 3}}, ensure_ascii=False)
        wa.inject_mp3(path, second)
        data = Path(path).read_bytes()
        _v, _s, frames, rest = _parse_id3(data)
        self.assertEqual(audio, rest)
        txxx = [f for f in frames if f[0] == b"TXXX"]
        self.assertEqual(1, len(txxx))
        self.assertEqual(second, _txxx_pairs(txxx[0][1])[1])

    def test_mp3_bad_files(self):
        good_audio = b"\xff\xfb\x90\x00" + b"\x00" * 32
        cases = {
            "tag-overrun": (b"ID3" + bytes([3, 0, 0])
                            + _syncsafe(9999) + b"\x00" * 20),
            "unsync-flag": (b"ID3" + bytes([3, 0, 0x80])
                            + _syncsafe(0) + good_audio),
            "id3v22": b"ID3" + bytes([2, 0, 0]) + _syncsafe(0),
            "frame-overrun": (b"ID3" + bytes([3, 0, 0])
                              + _syncsafe(10) + b"TIT2" + b"\x00\x00\x30\x00"
                              + b"\x00\x00"),
        }
        for name, data in cases.items():
            path = self.p(name + ".mp3")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wa.inject_mp3(path, JSON)

    # ============================================================ FLAC
    def test_flac_insert_vorbis_after_streaminfo(self):
        path = self.p("a.flac")
        audio = b"\xff\xf8" + b"\x00" * 96
        _flac(path, [(0, _streaminfo()), (1, b"\x00" * 8)], audio)
        wa.inject_flac(path, JSON)
        blocks, rest = _parse_flac(Path(path).read_bytes())
        self.assertEqual(audio, rest)
        self.assertEqual([0, 4, 1], [b[0] for b in blocks])
        self.assertEqual([True], [b[2] for b in blocks[-1:]])
        vendor, comments = _vorbis_comments(blocks[1][1])
        self.assertIn((wa.FLAC_KEY + "=" + JSON).encode("utf-8"), comments)
        self.assertTrue(blocks[-1][2])

    def test_flac_existing_vorbis_preserved(self):
        path = self.p("b.flac")
        audio = b"\xff\xf8" + b"\x00" * 96
        vb = _vorbis(b"myvendor", [b"ARTIST=x", b"AIGC=old"])
        _flac(path, [(0, _streaminfo()), (4, vb)], audio)
        wa.inject_flac(path, JSON)
        blocks, rest = _parse_flac(Path(path).read_bytes())
        self.assertEqual(audio, rest)
        vendor, comments = _vorbis_comments(blocks[1][1])
        self.assertEqual(b"myvendor", vendor)
        self.assertEqual([b"ARTIST=x"],
                         [c for c in comments if not c.startswith(b"AIGC=")])
        self.assertEqual([(wa.FLAC_KEY + "=" + JSON).encode("utf-8")],
                         [c for c in comments if c.startswith(b"AIGC=")])

    def test_flac_repeat_single_and_bytes_stable(self):
        path = self.p("c.flac")
        _flac(path, [(0, _streaminfo())])
        wa.inject_flac(path, JSON)
        first = Path(path).read_bytes()
        wa.inject_flac(path, JSON)
        self.assertEqual(first, Path(path).read_bytes())
        _blocks, _rest = _parse_flac(first)
        _vendor, comments = _vorbis_comments(
            [b for b in _blocks if b[0] == 4][0][1])
        self.assertEqual(1, len([c for c in comments
                                 if c.startswith(b"AIGC=")]))

    def test_flac_replace_value(self):
        path = self.p("d.flac")
        _flac(path, [(0, _streaminfo())])
        wa.inject_flac(path, JSON)
        second = json.dumps({"AIGC": {"Label": 4}}, ensure_ascii=False)
        wa.inject_flac(path, second)
        blocks, rest = _parse_flac(Path(path).read_bytes())
        self.assertEqual(1, len([b for b in blocks if b[0] == 4]))
        _vendor, comments = _vorbis_comments(
            [b for b in blocks if b[0] == 4][0][1])
        self.assertEqual([(wa.FLAC_KEY + "=" + second).encode("utf-8")],
                         [c for c in comments if c.startswith(b"AIGC=")])

    def test_flac_last_flag_unique_and_audio_offset(self):
        path = self.p("e.flac")
        audio = b"\xff\xf8" + b"\x00" * 40
        _flac(path, [(0, _streaminfo()), (1, b"\x00" * 4),
                     (2, b"\x00" * 6)], audio)
        wa.inject_flac(path, JSON)
        data = Path(path).read_bytes()
        blocks, rest = _parse_flac(data)
        self.assertEqual(audio, rest)
        self.assertEqual(1, len([b for b in blocks if b[2]]))
        self.assertTrue(blocks[-1][2])
        # 音频起始 = 4 + 所有块头/负载
        off = 4 + sum(4 + len(b[1]) for b in blocks)
        self.assertEqual(audio, data[off:])

    def test_flac_bad_files(self):
        good = _block(0, _streaminfo(), last=True)
        cases = {
            "empty": b"",
            "not-flac": b"JUNK" + good[1:],
            "truncated": b"fLaC" + good[:10],
            "no-last-flag": b"fLaC" + _block(0, _streaminfo(), last=False),
            "bad-vorbis": (b"fLaC" + _block(0, _streaminfo(), last=False)
                           + _block(4, b"\x00\x00", last=True)),
            "vorbis-tail": (b"fLaC" + _block(0, _streaminfo(), last=False)
                            + _block(4, _vorbis() + b"junk", last=True)),
            "two-vorbis": (b"fLaC" + _block(0, _streaminfo(), last=False)
                           + _block(4, _vorbis(), last=False)
                           + _block(4, _vorbis(), last=True)),
        }
        for name, data in cases.items():
            path = self.p(name + ".flac")
            Path(path).write_bytes(data)
            with self.assertRaises(ValueError, msg=name):
                wa.inject_flac(path, JSON)

    # ============================================================ 通用
    def test_bad_json_leaves_files_untouched(self):
        paths = []
        p = self.p("x.wav")
        _wav(p)
        paths.append(p)
        p = self.p("x.mp3")
        Path(p).write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 32)
        paths.append(p)
        p = self.p("x.flac")
        _flac(p, [(0, _streaminfo())])
        paths.append(p)
        for p in paths:
            before = Path(p).read_bytes()
            with self.assertRaises(ValueError):
                if p.endswith(".wav"):
                    wa.inject_wav(p, "{not json")
                elif p.endswith(".mp3"):
                    wa.inject_mp3(p, "{not json")
                else:
                    wa.inject_flac(p, "{not json")
            self.assertEqual(before, Path(p).read_bytes(), p)

    def test_atomic_no_temp_left(self):
        p = self.p("y.wav")
        _wav(p)
        wa.inject_wav(p, JSON)
        leftovers = [n for n in os.listdir(self.dir)
                     if n.startswith(".nf-audio-")]
        self.assertEqual([], leftovers)


if __name__ == "__main__":
    unittest.main()
