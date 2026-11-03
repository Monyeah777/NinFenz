"""TIFF / GIF / WebP 标识写入（图片类剩余载体）。

作者：impl（DSH agent）· 2026-11-02
依据：`/tmp/mediaextra-spec.md` A / B / C 节。

载体约定（写入侧）：
- TIFF：支持 II（小端）/ MM（大端）；在文件尾追加 JSON（UTF-8），IFD0 里加/替换
  tag 0x2BC（FieldType 7 = UNDEFINED，count=len(json)，>4 字节用 offset 指向尾部数据）；
  新增 entry 时**整体重写 IFD0**（按 tag 升序、追加到文件尾、头里改 IFD0 偏移），
  原 IFD 其它 entry 指向的数据偏移不变（不移动原数据）；
- GIF：Header+LSD(+GCT) 之后插入 Application Extension
  `0x21 0xFF 0x0B` + `XMP DataXMP` + XMP 包（含 TC260:AIGC）+ `0x00` 块终止；
  已有同标识扩展则替换，其余块字节不变；
- WebP：RIFF 末尾追加 `XMP ` chunk（payload=XMP 包，奇数补 pad），更新 RIFF size；
  已有 XMP chunk 替换；图像块（VP8/VP8L/ALPH）payload 不变。

纪律：纯标准库；坏文件 / 坏 JSON / 截断 → ValueError；原子写（同目录临时件 +
os.replace，保留权限位）；同 JSON 二次写幂等（不重写文件）。
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from ._atomic import write_bytes as _atomic_write

#: GIF 里 XMP Application Extension 的标识（11 字节）。
GIF_XMP_ID = b"XMP DataXMP"
#: TIFF 里 XMP 标签号（XMP 规范）。
TIFF_XMP_TAG = 0x2BC
#: TIFF FieldType 7 = UNDEFINED。
TIFF_TYPE_UNDEFINED = 7
#: XMP 包用的 TC260 命名空间（与 JPEG 写入同口径）。
TC260_NS = "http://www.tc260.org.cn/ns/AIGC/1.0/"
_XPACKET_HEAD = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
_XPACKET_TAIL = '<?xpacket end="w"?>'


# ---------------------------------------------------------------- 基础
def _read(path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))


def _check_json_text(json_text) -> bytes:
    """校验 JSON 文本并返回 UTF-8 字节（写入载体用）。"""
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("json_text 不得为空（修复指引：传标识 JSON 文本）")
    try:
        json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)
    return json_text.encode("utf-8")


def _xmp_packet(json_text: str) -> bytes:
    """生成带 TC260:AIGC 的 XMP 包（读侧按 xpacket/xmpmeta 识别）。"""
    escaped = html.escape(json_text, quote=True)
    body = (
        _XPACKET_HEAD + "\n"
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        ' <rdf:RDF xmlns:rdf='
        '"http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '  <rdf:Description rdf:about="" xmlns:TC260="%s">\n'
        '   <TC260:AIGC>%s</TC260:AIGC>\n'
        '  </rdf:Description>\n'
        ' </rdf:RDF>\n'
        '</x:xmpmeta>\n' % (TC260_NS, escaped)
    ) + _XPACKET_TAIL
    return body.encode("utf-8")



# ---------------------------------------------------------------- TIFF
def _tiff_value(data: bytes, bo: str, entry) -> bytes:
    """TIFF entry 的原始值字节（count<=4 内联，否则按 offset 取）。"""
    tag, typ, count, raw4, _pos = entry
    del tag, typ
    if count <= 4:
        return raw4[:count]
    off = int.from_bytes(raw4, bo)
    if off < 0 or off >= len(data):
        raise ValueError("TIFF entry 值偏移越界（%d）" % off)
    return data[off:off + count]


def _tiff_ifd(data: bytes, bo: str, off: int):
    """解析一个 IFD → (entries, next_ifd_offset)。entries 按文件内顺序。"""
    if off < 8 or off + 2 > len(data):
        raise ValueError("TIFF IFD 偏移非法（%d）" % off)
    count = int.from_bytes(data[off:off + 2], bo)
    if count == 0 or count > 4096:
        raise ValueError("TIFF IFD entry 数异常（%d）" % count)
    end = off + 2 + count * 12 + 4
    if end > len(data):
        raise ValueError("TIFF IFD 截断")
    entries = []
    pos = off + 2
    for _ in range(count):
        tag = int.from_bytes(data[pos:pos + 2], bo)
        typ = int.from_bytes(data[pos + 2:pos + 4], bo)
        cnt = int.from_bytes(data[pos + 4:pos + 8], bo)
        raw4 = data[pos + 8:pos + 12]
        entries.append((tag, typ, cnt, raw4, pos))
        pos += 12
    next_ifd = int.from_bytes(data[pos:pos + 4], bo)
    return entries, next_ifd


def _tiff_encode(entries, next_ifd: int, bo: str) -> bytes:
    """把 entries 编码成 IFD 字节（不排序，调用方保证升序）。"""
    out = bytearray(int(len(entries)).to_bytes(2, bo))
    for tag, typ, cnt, raw4, _pos in entries:
        out += tag.to_bytes(2, bo) + typ.to_bytes(2, bo)
        out += cnt.to_bytes(4, bo) + raw4
    out += next_ifd.to_bytes(4, bo)
    return bytes(out)


def inject_tiff(path, json_text) -> None:
    """在 TIFF 的 IFD0 写 tag 0x2BC（UNDEFINED）指向文件尾追加的 JSON。

    - 支持 II 小端 / MM 大端；同 JSON 二次写幂等（no-op）；
    - 新增/替换 entry：IFD0 整体重写并追加到文件尾，头里只改 IFD0 偏移；
      原 strip 等数据不移动（其它 entry 的 offset 保持原值）；
    - count<=4 的内联值（极短 JSON）不追加尾部数据（TIFF 规定小值内联）。
    """
    _check_json_text(json_text)
    jb = _xmp_packet(json_text)      # 0x2BC 是 XMP 标签，必须放 XMP 包
    data = _read(path)
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        raise ValueError("不是 TIFF（缺 II/MM 头）")
    bo = "little" if data[:2] == b"II" else "big"
    if int.from_bytes(data[2:4], bo) != 42:
        raise ValueError("TIFF 魔数不是 42")
    ifd0 = int.from_bytes(data[4:8], bo)
    entries, next_ifd = _tiff_ifd(data, bo, ifd0)

    # 幂等：已有同内容 0x2BC（type 7、count 一致、字节一致）→ 不写
    for entry in entries:
        tag, typ, cnt = entry[0], entry[1], entry[2]
        if tag == TIFF_XMP_TAG and typ == TIFF_TYPE_UNDEFINED:
            if cnt == len(jb) and _tiff_value(data, bo, entry) == jb:
                return

    keep = [e for e in entries if e[0] != TIFF_XMP_TAG]
    if len(jb) <= 4:
        raw4 = jb.ljust(4, b"\x00")
        new_entry = (TIFF_XMP_TAG, TIFF_TYPE_UNDEFINED, len(jb), raw4, 0)
        body = data + (b"\x00" if len(data) & 1 else b"")
        ifd_off = len(body)
        new_ifd = _tiff_encode(
            sorted(keep + [new_entry], key=lambda e: e[0]), next_ifd, bo)
        out = body + new_ifd
    else:
        pad0 = len(data) & 1
        json_off = len(data) + pad0
        if json_off & 1:                        # 双保险：值必须偶对齐
            json_off += 1
            pad0 += 1
        after = json_off + len(jb)
        pad1 = after & 1
        ifd_off = after + pad1
        raw4 = json_off.to_bytes(4, bo)
        new_entry = (TIFF_XMP_TAG, TIFF_TYPE_UNDEFINED, len(jb), raw4, 0)
        new_ifd = _tiff_encode(
            sorted(keep + [new_entry], key=lambda e: e[0]), next_ifd, bo)
        out = (data + b"\x00" * pad0 + jb + b"\x00" * pad1 + new_ifd)
    # 头里只改 IFD0 偏移（其余字节原样）
    out = out[:4] + ifd_off.to_bytes(4, bo) + out[8:]
    _atomic_write(path, out)


# ---------------------------------------------------------------- GIF
def _gif_prefix_len(data: bytes) -> int:
    """校验 GIF 头/LSD，返回「首个块」起点（跳过 LSD 与可选 GCT）。"""
    if len(data) < 13 or data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("不是 GIF（缺 GIF87a/GIF89a 头）")
    packed = data[10]
    pos = 13
    if packed & 0x80:                           # 全局颜色表
        pos += 3 * (2 ** ((packed & 0x07) + 1))
    if pos > len(data):
        raise ValueError("GIF 全局颜色表截断")
    return pos


def _gif_block_end(data: bytes, pos: int) -> int:
    """从块起点找该块结束偏移（普通块按子块长度推进）。"""
    b = data[pos]
    if b == 0x3B:
        return pos + 1
    if b == 0x2C:                               # 图像块
        p = pos + 10
        if p > len(data):
            raise ValueError("GIF 图像块截断")
        flags = data[pos + 9]
        if flags & 0x80:
            p += 3 * (2 ** ((flags & 0x07) + 1))
        p += 1
        while p < len(data):
            n = data[p]
            p += 1
            if n == 0:
                return p
            p += n
        raise ValueError("GIF 图像数据截断")
    if b == 0x21:                               # 扩展块
        label = data[pos + 1] if pos + 1 < len(data) else None
        p = pos + 2
        if label == 0xFF and data[pos + 2:pos + 14] == (
                bytes([0x0B]) + GIF_XMP_ID):
            # 我方写入的 XMP 扩展：标识后是裸 XMP 包 + 0x00
            stop = data.find(b"\x00", pos + 14)
            if stop < 0:
                raise ValueError("GIF XMP 扩展缺块终止符")
            return stop + 1
        while p < len(data):
            n = data[p]
            p += 1
            if n == 0:
                return p
            p += n
        raise ValueError("GIF 扩展块截断")
    raise ValueError("GIF 未知块标记 0x%02x（偏移 %d）" % (b, pos))


def inject_gif(path, json_text) -> None:
    """在 GIF 的 Header+LSD(+GCT) 后插入/替换 XMP Application Extension。"""
    jb = _check_json_text(json_text)
    packet = _xmp_packet(json_text)
    data = _read(path)
    pos = _gif_prefix_len(data)
    prefix = data[:pos]
    out = bytearray(prefix)
    sub = bytearray()
    for i in range(0, len(packet), 255):
        chunk = packet[i:i + 255]
        sub += bytes([len(chunk)]) + chunk
    sub += b"\x00"
    ext = (b"\x21\xff\x0b" + GIF_XMP_ID + bytes(sub))
    inserted = False
    p = pos
    while p < len(data):
        end = _gif_block_end(data, p)
        block = data[p:end]
        is_xmp = block.startswith(b"\x21\xff\x0b" + GIF_XMP_ID)
        if is_xmp:
            body = block[14:]
            old = bytearray()
            pos = 0
            while pos < len(body):
                n = body[pos]
                pos += 1
                if n == 0:
                    break
                old += body[pos:pos + n]
                pos += n
            if bytes(old) == packet:            # 幂等：内容一致直接返回
                return
            continue                            # 旧扩展丢弃（替换）
        if not inserted:
            out += ext                          # 首个非 XMP 块之前插入
            inserted = True
        out += block
        p = end
    if not inserted:
        out += ext                              # 没有其它块（只有 trailer）
    _atomic_write(path, bytes(out))


# ---------------------------------------------------------------- WebP
def _webp_chunks(data: bytes):
    """迭代 (fourcc, body_start, body_end)；校验 RIFF/WEBP 与块长度。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("不是 WebP（缺 RIFF/WEBP 头）")
    pos, end = 12, len(data)
    while pos + 8 <= end:
        fourcc = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = pos + 8
        if size < 0 or body + size > end:
            raise ValueError("WebP 块长度越界（%r）" % fourcc)
        yield fourcc, body, body + size
        pos = body + size + (size & 1)


def inject_webp(path, json_text) -> None:
    """在 WebP 的 RIFF 末尾追加/替换 `XMP ` chunk（更新 RIFF size）。"""
    _check_json_text(json_text)
    packet = _xmp_packet(json_text)
    data = _read(path)
    chunks = list(_webp_chunks(data))
    kept = []
    for fourcc, body, end in chunks:
        payload = data[body:end]
        if fourcc == b"XMP ":
            if payload == packet:               # 幂等：内容一致直接返回
                return
            continue                            # 旧 XMP 丢弃（替换）
        kept.append((fourcc, payload))
    out = bytearray(b"RIFF\x00\x00\x00\x00WEBP")
    for fourcc, payload in kept:
        out += fourcc + len(payload).to_bytes(4, "little") + payload
        if len(payload) & 1:
            out += b"\x00"
    out += b"XMP " + len(packet).to_bytes(4, "little") + packet
    if len(packet) & 1:
        out += b"\x00"
    out[4:8] = (len(out) - 8).to_bytes(4, "little")
    _atomic_write(path, bytes(out))
