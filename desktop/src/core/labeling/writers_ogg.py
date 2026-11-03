"""OGG 标识写入（Vorbis / Opus 的 comment header）。

载体
----
OGG 是「页（page）→ 段表（segment table）→ 包（packet）」的容器：
- 页头 27 字节：`OggS`、version、header_type、granule、serial、seq、CRC、
  page_segments，随后是 N 字节段表（lace 0..255）与 payload；
- 若干段拼成一个包；lace=255 表示包跨页继续，<255 结束当前包。

本写入器：
1. 解析全部页（**校验每页 CRC**），重组包；
2. 第一包必须是识别头（`\\x01vorbis` / `OpusHead`），第二包必须是注释头
   （`\\x03vorbis` / `OpusTags`）；
3. 在 Vorbis comment 结构里加/替换 `AIGC=<json_text>`（UTF-8；保留 vendor
   与其它注释原字节）；Vorbis 保留 framing bit（LSB=1），Opus 无 framing；
4. 重建「注释头 + 后续头部包」各自的页（可能多页，每页 ≤255 段 ≈65025B），
   随后所有页 **seq 顺延、CRC 重算**；识别页（第 0 页）与音频页的
   **payload/包字节不变**（音频页只改 seq 与 CRC 两处字段）；
5. 原子写（同目录临时件 + os.replace，保留权限位）。

纪律与边界
----------
- 只支持单流（所有页 serial 相同）；分片/多路复用/链式 OGG → ValueError；
- 识别头必须**独占第 0 页**（Vorbis/Opus 规范要求），注释头必须从新页
  起点开始；若音频包与头部包同页，本实现无法在不重排音频页的前提下
  修正 granule，故如实 ValueError（修复指引：先 remux）；
- 头部页的 granule 统一写 0（规范要求）；音频页 granule 原样保留；
- 幂等：同一 json_text 二次写 → 分包与 seq 计算确定，输出逐字节相同；
  换 json_text 原位替换 AIGC 注释（其它注释保持顺序）；
- 不做 OGG 之外的 HEIF 面（见另一件）；不做签名/时间戳。
"""

from __future__ import annotations

import json
import os
import struct
import tempfile

#: 首包 / 注释包签名。
VORBIS_ID = b"\x01vorbis"
VORBIS_COMMENT = b"\x03vorbis"
OPUS_HEAD = b"OpusHead"
OPUS_TAGS = b"OpusTags"
#: Vorbis / Opus 的头部包个数（ident + comment [+ setup]）。
VORBIS_HEADERS = 3
OPUS_HEADERS = 2
#: 每页最大段数（段表 1 字节计数）。
MAX_SEGMENTS = 255
#: AIGC 注释前缀（UTF-8）。
AIGC_PREFIX = b"AIGC="


def _make_crc_table() -> list:
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            if r & 0x80000000:
                r = ((r << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                r = (r << 1) & 0xFFFFFFFF
        table.append(r)
    return table


_CRC_TABLE = _make_crc_table()


def _ogg_crc(data: bytes) -> int:
    """Ogg 页 CRC（多项式 0x04C11DB7，初值 0，不反射，不 xorout）。"""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _CRC_TABLE[
            ((crc >> 24) & 0xFF) ^ byte]
    return crc


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
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        mode = os.stat(path).st_mode & 0o7777
    except OSError:
        mode = None
    fd, tmp = tempfile.mkstemp(prefix=".nf-ogg-", suffix=".tmp",
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


# ---------------------------------------------------------------- 页
def _parse_pages(data: bytes) -> list:
    """解析全部 Ogg 页并校验 CRC；畸形 ValueError。"""
    pages = []
    pos, n = 0, len(data)
    while pos < n:
        if data[pos:pos + 4] != b"OggS":
            raise ValueError("不是 Ogg 流（缺 OggS 捕获）：偏移 %d" % pos)
        if pos + 27 > n:
            raise ValueError("Ogg 页头不完整：偏移 %d" % pos)
        version = data[pos + 4]
        if version != 0:
            raise ValueError("Ogg 版本 %d 不支持（只支持 0）" % version)
        header_type = data[pos + 5]
        granule = struct.unpack("<q", data[pos + 6:pos + 14])[0]
        serial = struct.unpack("<I", data[pos + 14:pos + 18])[0]
        seq = struct.unpack("<I", data[pos + 18:pos + 22])[0]
        crc = struct.unpack("<I", data[pos + 22:pos + 26])[0]
        nseg = data[pos + 26]
        seg_start = pos + 27
        payload_start = seg_start + nseg
        if payload_start > n:
            raise ValueError("Ogg 段表越界：页 seq=%d" % seq)
        laces = data[seg_start:payload_start]
        plen = sum(laces)
        end = payload_start + plen
        if end > n:
            raise ValueError("Ogg 页 payload 越界：页 seq=%d" % seq)
        payload = data[payload_start:end]
        raw = bytearray(data[pos:end])
        raw[22:26] = b"\x00\x00\x00\x00"
        if _ogg_crc(bytes(raw)) != crc:
            raise ValueError("Ogg 页 CRC 校验失败：页 seq=%d" % seq)
        pages.append({
            "version": version, "header_type": header_type,
            "granule": granule, "serial": serial, "seq": seq,
            "laces": list(laces), "payload": payload,
            "raw": bytes(data[pos:end]),
        })
        pos = end
    if not pages:
        raise ValueError("Ogg 流没有页")
    return pages


def _packets(pages: list) -> list:
    """按段表重组包 → [(packet, 起始页号, 页内偏移)]；畸形 ValueError。"""
    packets = []
    cur = bytearray()
    started = False          # 上一页结束时是否有包未结束
    start_page = None
    start_off = None
    for pi, page in enumerate(pages):
        cont = bool(page["header_type"] & 0x01)
        if cont != started:
            raise ValueError("Ogg continuation 标志与包状态不一致：页 seq=%d"
                             % page["seq"])
        off = 0
        for lace in page["laces"]:
            if start_page is None:
                start_page, start_off = pi, off
            cur += page["payload"][off:off + lace]
            off += lace
            if lace < 255:
                packets.append((bytes(cur), start_page, start_off))
                cur = bytearray()
                start_page = None
                started = False
            else:
                started = True
    if cur or started:
        raise ValueError("Ogg 流末尾存在未结束的包")
    return packets


def _analyze(pages: list) -> dict:
    """识别编解码器并确定可重建的头部页区间。"""
    serials = {p["serial"] for p in pages}
    if len(serials) > 1:
        raise ValueError("多 serial OGG（分片/多路复用/链式）不支持：%s"
                         % sorted(serials))
    if not pages[0]["header_type"] & 0x02:
        raise ValueError("第 0 页缺 BOS 标志，不是 Ogg 流首包")
    packets = _packets(pages)
    if len(packets) < 2:
        raise ValueError("Ogg 包太少（至少 ident + comment 两包）")
    p0 = packets[0][0]
    if p0.startswith(VORBIS_ID):
        codec, header_count = "vorbis", VORBIS_HEADERS
        comment_magic = VORBIS_COMMENT
    elif p0.startswith(OPUS_HEAD):
        codec, header_count = "opus", OPUS_HEADERS
        comment_magic = OPUS_TAGS
    else:
        raise ValueError("不支持的 Ogg 编解码器（首包既非 vorbis 也非 Opus）")
    if len(packets) < header_count:
        raise ValueError("Ogg 头部包不全：需要 %d 包，实有 %d"
                         % (header_count, len(packets)))
    if not packets[1][0].startswith(comment_magic):
        raise ValueError("第 2 包不是 %s 注释头" % codec)
    # 识别头必须独占第 0 页；注释头必须从第 1 页起点开始
    if packets[0][1] != 0 or packets[0][2] != 0:
        raise ValueError("识别头不在第 0 页起点，布局不支持")
    if len(packets) > 1:
        if packets[1][1] != 1 or packets[1][2] != 0:
            raise ValueError("注释头未从新页起点开始，布局不支持")
    if packets[0][1] == packets[1][1]:
        raise ValueError("识别头与注释头同页，布局不支持")
    if len(packets) > header_count:
        apage, aoff = packets[header_count][1], packets[header_count][2]
        if pages[apage]["header_type"] & 0x01:
            raise ValueError("音频包页带 continued 标志，布局不支持")
        if aoff != 0:
            raise ValueError("音频包与头部包同页，无法在不重排音频页下修正"
                             " granule（修复指引：先 remux）")
        audio_start = apage
    else:
        audio_start = len(pages)          # 没有音频包：只重建头部页
    if audio_start < 2:
        raise ValueError("头部页区间异常（audio_start=%d）" % audio_start)
    return {"codec": codec, "header_count": header_count,
            "packets": packets, "audio_start": audio_start,
            "comment_magic": comment_magic,
            "serial": pages[0]["serial"], "first_seq": pages[0]["seq"]}


# ---------------------------------------------------------------- 注释包
def _parse_vorbis_comment(packet: bytes, magic: bytes, framing: bool):
    """→ (vendor 原始字节, [comment 原始字节])；畸形 ValueError。"""
    body = packet[len(magic):]
    off = 0

    def need(k: int, what: str):
        nonlocal off
        if off + k > len(body):
            raise ValueError("Vorbis comment 缺 %s（偏移 %d）" % (what, off))

    need(4, "vendor 长度")
    vlen = int.from_bytes(body[off:off + 4], "little")
    off += 4
    need(vlen, "vendor")
    vendor = body[off:off + vlen]
    off += vlen
    need(4, "comment 计数")
    count = int.from_bytes(body[off:off + 4], "little")
    off += 4
    comments = []
    for _ in range(count):
        need(4, "comment 长度")
        clen = int.from_bytes(body[off:off + 4], "little")
        off += 4
        need(clen, "comment 内容")
        comments.append(body[off:off + clen])
        off += clen
    if framing:
        need(1, "framing bit")
        if not body[off] & 0x01:
            raise ValueError("Vorbis comment 的 framing bit 不为 1")
        off += 1
    if off != len(body):
        raise ValueError("Vorbis comment 尾部有多余字节：%d"
                         % (len(body) - off))
    return vendor, comments


def _build_vorbis_comment(magic: bytes, vendor: bytes, comments,
                          framing: bool) -> bytes:
    out = [magic, struct.pack("<I", len(vendor)), vendor,
           struct.pack("<I", len(comments))]
    for item in comments:
        out.append(struct.pack("<I", len(item)))
        out.append(item)
    if framing:
        out.append(b"\x01")
    return b"".join(out)


# ---------------------------------------------------------------- 分包
def _paginate(packets: list):
    """把若干包按 Ogg 段规则切成 [(header_type, laces, payload)]。"""
    laces = []
    payload = bytearray()
    for pkt in packets:
        off = 0
        while True:
            n = min(MAX_SEGMENTS, len(pkt) - off)
            laces.append(n)
            payload += pkt[off:off + n]
            off += n
            if n < MAX_SEGMENTS:
                break
            if off == len(pkt):          # 恰好 255 的倍数：补 0 段终止
                laces.append(0)
                break
    pages = []
    pos = 0
    continued = False
    while pos < len(laces):
        take = laces[pos:pos + MAX_SEGMENTS]
        start = sum(laces[:pos])
        end = start + sum(take)
        header_type = 0x01 if continued else 0x00
        pages.append((header_type, take, bytes(payload[start:end])))
        continued = take[-1] == MAX_SEGMENTS
        pos += MAX_SEGMENTS
    return pages


def _build_page(header_type: int, granule: int, serial: int, seq: int,
                laces, payload: bytes) -> bytes:
    if not 0 <= len(laces) <= MAX_SEGMENTS:
        raise ValueError("页段数非法：%d" % len(laces))
    if len(payload) != sum(laces):
        raise ValueError("页 payload 与段表不一致")
    head = bytearray()
    head += b"OggS" + b"\x00" + bytes([header_type])
    head += struct.pack("<q", granule)
    head += struct.pack("<I", serial)
    head += struct.pack("<I", seq)
    head += b"\x00\x00\x00\x00"                 # CRC 占位
    head += bytes([len(laces)]) + bytes(laces) + payload
    crc = _ogg_crc(bytes(head))
    raw = bytes(head[:22]) + struct.pack("<I", crc) + bytes(head[26:])
    return raw


def inject_ogg(path: str, json_text: str) -> None:
    """把 JSON 标识写进 OGG 的 comment header（保留 vendor/其它注释）。

    - 只重建「注释头 + 其余头部包」所在页；识别页原样保留；
    - 音频页 payload/包字节不变，仅 seq 重编与 CRC 重算；
    - 幂等；坏文件（CRC/结构/framing）→ ValueError；成功返回 None。
    """
    payload = _validate_json(json_text)
    with open(path, "rb") as fh:
        data = fh.read()
    pages = _parse_pages(data)
    info = _analyze(pages)
    magic = info["comment_magic"]
    framing = info["codec"] == "vorbis"
    packets = info["packets"]
    vendor, comments = _parse_vorbis_comment(packets[1][0], magic, framing)
    kept = [c for c in comments if not c.startswith(AIGC_PREFIX)]
    kept.append(AIGC_PREFIX + payload)
    new_comment = _build_vorbis_comment(magic, vendor, kept, framing)
    header_packets = [new_comment]
    for idx in range(2, info["header_count"]):
        header_packets.append(packets[idx][0])
    rebuilt = _paginate(header_packets)
    out = [pages[0]["raw"]]
    seq = info["first_seq"] + 1
    last = len(rebuilt) - 1
    no_audio = info["audio_start"] == len(pages)
    for i, (header_type, laces, page_payload) in enumerate(rebuilt):
        ht = header_type
        if no_audio and i == last:
            ht |= 0x04
        out.append(_build_page(ht, 0, info["serial"], seq,
                               laces, page_payload))
        seq += 1
    for page in pages[info["audio_start"]:]:
        out.append(_build_page(page["header_type"], page["granule"],
                               info["serial"], seq, page["laces"],
                               page["payload"]))
        seq += 1
    _write_atomic(path, b"".join(out))


__all__ = [
    "VORBIS_ID",
    "VORBIS_COMMENT",
    "OPUS_HEAD",
    "OPUS_TAGS",
    "AIGC_PREFIX",
    "inject_ogg",
]
