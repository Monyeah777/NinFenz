"""WAV / MP3 / FLAC 的标识写入（TC260 指南的音频类隐式标识）。

三个入口
--------
- `inject_wav(path, json_text)`：RIFF/WAVE 追加（或替换）子块 `AIGC`，
  payload = JSON UTF-8（奇数长度补 1 字节 pad），同步更新 RIFF size；
  `fmt `/`data` 子块字节不变。
- `inject_mp3(path, json_text)`：ID3v2 的 `TXXX`（Description="AIGC"，
  编码 0x03 UTF-8，Value=JSON）。无 ID3v2 头则新建 ID3v2.3；已有 2.3/2.4
  则加/替换该帧并更新 syncsafe tag size；音频帧字节不变。
- `inject_flac(path, json_text)`：`fLaC` 后的 VORBIS_COMMENT（type 4）
  注释列表里加/替换 `AIGC=JSON`（保留 vendor 与其它注释，last-block 标志
  正确，必要时插在 STREAMINFO 之后）；音频帧字节不变。

纪律
----
- 只改标识所在结构；音频帧 / `fmt `/`data` / 其它 metadata 的**原始字节**
  保持不变（容器头/长度字段按规范同步）；
- 幂等：同一 json_text 二次写不新增第二份标识，输出逐字节稳定；
  换 json_text 原位替换；
- 坏文件 → `ValueError`（带说明），不静默写坏；
- 写盘走「同目录临时件 + os.replace」原子替换（保留权限位）。

已知边界
--------
- MP3：只支持 ID3v2.3/2.4 且 flags=0（不支持 unsync / 扩展头 / footer /
  ID3v2.2）；重建标签时不保留尾部 padding（音频字节不受影响）；
- FLAC：要求恰好一个 STREAMINFO 且 last-block 标志只出现在最后一个块；
  多个 VORBIS_COMMENT 视为损坏（ValueError）；
- WAV：不保留“块之外的尾巴”——RIFF 之后剩余不足 8 字节视为损坏
  （ValueError）；保留尾部非块数据的需求本波不做；
- 不做 OGG/HEIF（Ogg 页重建 / HEIF iinf/iloc 重写本波不做）；
- 不做签名/时间戳，只把已生成的 JSON 放进容器。
"""

from __future__ import annotations

import json
import os
import struct
import tempfile

#: WAV 标识子块 FourCC。
WAV_CHUNK_ID = b"AIGC"
#: MP3 标识帧的描述（TXXX Description）。
MP3_DESC = "AIGC"
#: FLAC VORBIS_COMMENT 的标识键。
FLAC_KEY = "AIGC"


def _validate_json(json_text: str) -> bytes:
    if not isinstance(json_text, str):
        raise ValueError("json_text 必须是 str（收到 %r）" % type(json_text))
    if not json_text.strip():
        raise ValueError("json_text 为空")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)
    return json_text.encode("utf-8")


def _write_atomic(path: str, data: bytes) -> None:
    """同目录临时件 + os.replace；保留权限位，失败不留半成品。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        mode = None
    fd, tmp = tempfile.mkstemp(prefix=".nf-audio-", suffix=".tmp",
                               dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------- WAV
def _riff_chunks(data: bytes):
    """解析 RIFF/WAVE 子块 → ([(cid, raw, pad)], trailing)。畸形 ValueError。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("不是 RIFF/WAVE 文件（缺 RIFF/WAVE 头）")
    pos, n = 12, len(data)
    chunks = []
    while pos < n:
        if pos + 8 > n:
            raise ValueError("WAV 子块头不完整：偏移 %d（文件长 %d）"
                             % (pos, n))
        cid = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        ds = pos + 8
        de = ds + size
        if de > n:
            raise ValueError("WAV 子块越界：%s size=%d 偏移 %d 文件长 %d"
                             % (cid, size, pos, n))
        raw = data[pos:de]
        pad = b""
        if size & 1:
            if de < n:
                pad = data[de:de + 1]
            de += 1
        chunks.append((cid, raw, pad))
        pos = de
    return chunks


def inject_wav(path: str, json_text: str) -> None:
    """把 JSON 标识写成 RIFF `AIGC` 子块（替换旧块；fmt/data 字节不变）。"""
    payload = _validate_json(json_text)
    with open(path, "rb") as fh:
        data = fh.read()
    chunks = _riff_chunks(data)
    kept = [(cid, raw, pad) for (cid, raw, pad) in chunks
            if cid != WAV_CHUNK_ID]
    body = b"".join(raw + pad for _cid, raw, pad in kept)
    padv = b"\x00" if len(payload) & 1 else b""
    chunk = (WAV_CHUNK_ID
             + struct.pack("<I", len(payload))
             + payload + padv)
    body += chunk
    out = b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body
    _write_atomic(path, out)


# ---------------------------------------------------------------- MP3
def _syncsafe_encode(n: int) -> bytes:
    if n < 0 or n > 0x0FFFFFFF:
        raise ValueError("syncsafe 整数越界：%d" % n)
    return bytes([
        (n >> 21) & 0x7F, (n >> 14) & 0x7F,
        (n >> 7) & 0x7F, n & 0x7F,
    ])


def _syncsafe_decode(raw: bytes) -> int:
    if len(raw) != 4:
        raise ValueError("syncsafe 需要 4 字节")
    return (((raw[0] & 0x7F) << 21) | ((raw[1] & 0x7F) << 14)
            | ((raw[2] & 0x7F) << 7) | (raw[3] & 0x7F))


def _txxx_desc(payload: bytes) -> str:
    """TXXX payload 的 Description（解不出返回空串）。"""
    if not payload:
        return ""
    enc = payload[0]
    rest = payload[1:]
    try:
        if enc in (1, 2):
            name = "utf-16" if enc == 1 else "utf-16-be"
            idx = -1
            for i in range(0, len(rest) - 1, 2):
                if rest[i:i + 2] == b"\x00\x00":
                    idx = i
                    break
            if idx < 0:
                return ""
            return rest[:idx].decode(name, "replace")
        idx = rest.find(b"\x00")
        if idx < 0:
            return ""
        codec = "utf-8" if enc == 3 else "latin-1"
        return rest[:idx].decode(codec, "replace")
    except (UnicodeError, IndexError):
        return ""


def _txxx_payload(payload: bytes) -> bytes:
    """新 TXXX payload：编码 0x03(UTF-8) + Description\\0 + Value。"""
    return b"\x03" + MP3_DESC.encode("utf-8") + b"\x00" + payload


def _mp3_frame(fid: bytes, payload: bytes, version: int) -> bytes:
    if len(fid) != 4:
        raise ValueError("帧 ID 必须是 4 字节")
    if version >= 4:
        size = _syncsafe_encode(len(payload))
    else:
        size = struct.pack(">I", len(payload))
    return fid + size + b"\x00\x00" + payload


def _parse_mp3(data: bytes):
    """→ (version_major, revision, frames[(fid, raw)], audio)。坏→ValueError。"""
    if len(data) < 10 or not data.startswith(b"ID3"):
        return None
    version = data[3]
    revision = data[4]
    flags = data[5]
    if version not in (3, 4):
        raise ValueError("只支持 ID3v2.3/2.4（收到 v2.%d）" % version)
    if flags != 0:
        raise ValueError("ID3v2 flags=0x%02x 不支持（unsync/扩展头/footer）"
                         % flags)
    tag_size = _syncsafe_decode(data[6:10])
    end = 10 + tag_size
    if end > len(data):
        raise ValueError("ID3v2 tag 尺寸越界：tag=%d 文件长=%d"
                         % (tag_size, len(data)))
    frames = []
    pos = 10
    while pos + 10 <= end:
        fid = data[pos:pos + 4]
        if fid == b"\x00\x00\x00\x00":       # 进入 padding：忽略余下
            break
        if not all(0x41 <= b <= 0x5A or 0x30 <= b <= 0x39 for b in fid):
            raise ValueError("ID3v2 帧 ID 非法：%r（偏移 %d）"
                             % (fid, pos))
        if version == 4:
            fsize = _syncsafe_decode(data[pos + 4:pos + 8])
        else:
            fsize = int.from_bytes(data[pos + 4:pos + 8], "big")
        fend = pos + 10 + fsize
        if fend > end:
            raise ValueError("ID3v2 帧越界：%r size=%d 偏移 %d"
                             % (fid, fsize, pos))
        frames.append((fid, data[pos:fend]))
        pos = fend
    return version, revision, frames, data[end:]


def inject_mp3(path: str, json_text: str) -> None:
    """把 JSON 标识写进 ID3v2 TXXX 帧（无 ID3 则新建 v2.3；音频帧不变）。"""
    payload = _txxx_payload(_validate_json(json_text))
    with open(path, "rb") as fh:
        data = fh.read()
    parsed = _parse_mp3(data)
    if parsed is None:
        tag = (b"ID3" + bytes([3, 0]) + b"\x00"
               + _syncsafe_encode(len(_mp3_frame(b"TXXX", payload, 3)))
               + _mp3_frame(b"TXXX", payload, 3))
        _write_atomic(path, tag + data)
        return
    version, revision, frames, audio = parsed
    out = []
    placed = False
    for fid, raw in frames:
        if fid == b"TXXX":
            if _txxx_desc(raw[10:]) == MP3_DESC:
                if not placed:
                    out.append(_mp3_frame(b"TXXX", payload, version))
                    placed = True
                continue              # 重复的 AIGC 帧：只留一份
        out.append(raw)
    if not placed:
        out.append(_mp3_frame(b"TXXX", payload, version))
    frames_bytes = b"".join(out)
    tag = (b"ID3" + bytes([version, revision]) + b"\x00"
           + _syncsafe_encode(len(frames_bytes)) + frames_bytes)
    _write_atomic(path, tag + audio)


# ---------------------------------------------------------------- FLAC
def _flac_blocks(data: bytes):
    """解析 fLaC metadata blocks → ([(type, payload)], audio)。畸形 ValueError。"""
    if not data.startswith(b"fLaC"):
        raise ValueError("不是 FLAC 文件（缺 fLaC 头）")
    pos, n = 4, len(data)
    blocks = []
    last_seen = False
    while True:
        if pos + 4 > n:
            raise ValueError("FLAC metadata 块头不完整：偏移 %d" % pos)
        head = data[pos]
        last = bool(head & 0x80)
        btype = head & 0x7F
        size = int.from_bytes(data[pos + 1:pos + 4], "big")
        ds = pos + 4
        de = ds + size
        if de > n:
            raise ValueError("FLAC metadata 块越界：type=%d size=%d 偏移 %d"
                             % (btype, size, pos))
        blocks.append((btype, data[ds:de]))
        pos = de
        if last:
            last_seen = True
            break
    if not last_seen:
        raise ValueError("FLAC 缺 last-block 标志（最后一个 metadata 块）")
    if not blocks or blocks[0][0] != 0:
        raise ValueError("FLAC 首块不是 STREAMINFO（type 0）")
    return blocks, data[pos:]


def _parse_vorbis_comment(payload: bytes):
    """VORBIS_COMMENT → (vendor 原始字节, [comment 原始字节])。"""
    if len(payload) < 4:
        raise ValueError("VORBIS_COMMENT 太短（缺 vendor 长度）")
    off = 0
    vlen = int.from_bytes(payload[off:off + 4], "little")
    off += 4
    if off + vlen > len(payload):
        raise ValueError("VORBIS_COMMENT vendor 越界")
    vendor = payload[off:off + vlen]
    off += vlen
    if off + 4 > len(payload):
        raise ValueError("VORBIS_COMMENT 缺 comment 计数")
    count = int.from_bytes(payload[off:off + 4], "little")
    off += 4
    comments = []
    for _ in range(count):
        if off + 4 > len(payload):
            raise ValueError("VORBIS_COMMENT 条目长度缺失")
        clen = int.from_bytes(payload[off:off + 4], "little")
        off += 4
        if off + clen > len(payload):
            raise ValueError("VORBIS_COMMENT 条目越界")
        comments.append(payload[off:off + clen])
        off += clen
    if off != len(payload):
        raise ValueError("VORBIS_COMMENT 尾部有多余字节：%d"
                         % (len(payload) - off))
    return vendor, comments


def _build_vorbis_comment(vendor: bytes, comments) -> bytes:
    out = [struct.pack("<I", len(vendor)), vendor,
           struct.pack("<I", len(comments))]
    for item in comments:
        out.append(struct.pack("<I", len(item)))
        out.append(item)
    return b"".join(out)


def inject_flac(path: str, json_text: str) -> None:
    """把 JSON 写成 FLAC VORBIS_COMMENT 的 AIGC=JSON（保留其它注释）。"""
    payload = _validate_json(json_text)
    with open(path, "rb") as fh:
        data = fh.read()
    blocks, audio = _flac_blocks(data)
    vorbis_idx = None
    for i, (btype, bpayload) in enumerate(blocks):
        if btype == 4:
            if vorbis_idx is not None:
                raise ValueError("FLAC 存在多个 VORBIS_COMMENT 块")
            vorbis_idx = i
    if vorbis_idx is None:
        vendor = b"nf-labelcheck"
        comments = []
        idx = 1                       # 插在 STREAMINFO 之后
    else:
        vendor, comments = _parse_vorbis_comment(blocks[vorbis_idx][1])
        idx = vorbis_idx
    marker = (FLAC_KEY + "=").encode("utf-8")
    kept = [c for c in comments if not c.startswith(marker)]
    kept.append(marker + payload)
    new_payload = _build_vorbis_comment(vendor, kept)
    new_blocks = []
    if vorbis_idx is None:
        new_blocks = [blocks[0], (4, new_payload)] + list(blocks[1:])
    else:
        for i, (btype, bpayload) in enumerate(blocks):
            if i == idx:
                new_blocks.append((4, new_payload))
            else:
                new_blocks.append((btype, bpayload))
    out = [b"fLaC"]
    total = len(new_blocks)
    for i, (btype, bpayload) in enumerate(new_blocks):
        if len(bpayload) > 0xFFFFFF:
            raise ValueError("FLAC metadata 块过大（>16MiB），不支持")
        head = btype | (0x80 if i == total - 1 else 0)
        out.append(bytes([head]) + len(bpayload).to_bytes(3, "big"))
        out.append(bpayload)
    out.append(audio)
    _write_atomic(path, b"".join(out))


__all__ = [
    "WAV_CHUNK_ID",
    "MP3_DESC",
    "FLAC_KEY",
    "inject_wav",
    "inject_mp3",
    "inject_flac",
]
