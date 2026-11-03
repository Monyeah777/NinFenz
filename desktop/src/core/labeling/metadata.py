"""容器元数据嗅探 / 提取 / 注入（纯标准库）。

作者：impl（DSH agent）· 2026-11-02
依据：nf-labelcheck 的 docs/interfaces.md（函数名/返回结构必须逐字一致）。

覆盖的容器与标识载体：
- PNG：tEXt / iTXt / zTXt（zTXt 走 zlib 解压），以及 IHDR 后插入 tEXt。
- JPEG：APP1 里的 XMP（http://ns.adobe.com/xap/1.0/）与 EXIF UserComment。
- PDF：Info 字典字符串值 + /Metadata XMP 流（未压缩或 FlateDecode）。
- MP4：udta/XMP_、uuid 盒（XMP UUID）与 ilst 条目（©xyz/©too/---- 等）。
- MP3：ID3v2 TXXX 帧（key 为 description）。
- WAV：LIST/INFO 子块。
- text：UTF-8 原文。
- sidecar：<path>.aigc.json（追加在 extract() 末尾）。

纪律：
- 不崩溃：所有解析器对截断/畸形输入都返回「已解析出的部分」或空列表；
  只有「文件读不了 / 参数非法 / 需要严格取内容字节但结构不可用」才抛 ValueError。
- 纯标准库；代码 ≤80 列；注释中文。
"""

from __future__ import annotations

import codecs
import html
import json
import re
import struct
import zipfile
import zlib
from pathlib import Path

CONTAINERS = ("png", "jpeg", "pdf", "mp4", "mp3", "wav", "text", "unknown")

#: 单文件读取上限：超过即拒绝（避免误把镜像/视频整块读进内存）。
MAX_READ = 128 * 1024 * 1024

#: XMP 在 APP1 里的命名空间签名（JPEG）。
XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
#: EXIF 在 APP1 里的签名。
EXIF_SIG = b"Exif\x00\x00"
#: MP4 里 XMP 的 uuid：BE7ACFCB-97A9-42E8-9C71-999491E3AFAC。
XMP_UUID = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PDF_KEYS = (
    "Title", "Author", "Subject", "Keywords", "Creator",
    "Producer", "CreationDate", "ModDate", "AIGC",
)
_MP4_CONTAINERS = {
    b"moov", b"trak", b"mdia", b"minf", b"stbl", b"udta",
    b"edts", b"dinf", b"mvex", b"moof", b"traf", b"meta",
    b"ilst",
}
_MP4_BOX_TYPES = {
    b"ftyp", b"styp", b"moov", b"mdat", b"free", b"skip",
    b"wide", b"pnot", b"moof", b"sidx",
}


# ---------------------------------------------------------------- 基础
def _read(path) -> bytes:
    """读文件（带大小上限）；读不了给可读 ValueError。"""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))
    if size > MAX_READ:
        raise ValueError(
            "文件过大（%d 字节 > %d）：%s（修复指引：先裁剪或拆分）"
            % (size, MAX_READ, path)
        )
    try:
        return p.read_bytes()
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))


def _write(path, data: bytes) -> None:
    p = Path(path)
    try:
        p.write_bytes(data)
    except OSError as exc:
        raise ValueError("无法写入文件：%s（%s）" % (path, exc))


def _decode(raw: bytes, enc: str = "utf-8") -> str:
    """宽松解码：坏字节替换成 U+FFFD，绝不抛异常。"""
    return raw.decode(enc, "replace")


def _kind_of(key: str, text: str) -> str:
    """把文本块归类为 json / xmp / text（供下游按类型挑候选）。"""
    k = (key or "").strip().lower()
    t = (text or "").lstrip()
    if k in ("xmp", "xml:com.adobe.xmp") or "x:xmpmeta" in t:
        return "xmp"
    if t.startswith("<?xpacket"):
        return "xmp"
    if t[:1] in ("{", "["):
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return "text"
        # 首字符已限定 {/[；显式判一次形状，把「标签载体」钉在读取点（下游按对象取字段）。
        return "json" if isinstance(parsed, (dict, list)) else "text"
    return "text"


def _entry(container: str, key: str, text: str, offset: int) -> dict:
    return {
        "container": container,
        "key": key,
        "kind": _kind_of(key, text),
        "text": text,
        "offset": int(offset),
    }


# ---------------------------------------------------------------- sniff
def _looks_utf8_text(path) -> bool:
    """分块验证 UTF-8：含 NUL 或解码失败即判非文本（不整块读入）。"""
    dec = codecs.getincrementaldecoder("utf-8")()
    try:
        with open(path, "rb") as fh:
            while True:
                buf = fh.read(1 << 20)
                if not buf:
                    break
                if b"\x00" in buf:
                    return False
                dec.decode(buf)
            dec.decode(b"", True)
    except (OSError, UnicodeError):
        return False
    return True


def sniff(path: str) -> str:
    """按魔数判断容器；无法判断但可解码为 UTF-8 文本→'text'；否则 'unknown'。

    额外识别：docx（zip 内含 word/document.xml）、ofd（zip 内含 OFD.xml）、
    markdown（后缀 .md/.markdown）。
    """
    p = Path(path)
    try:
        size = p.stat().st_size
        with open(p, "rb") as fh:
            head = fh.read(4096)
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))
    if size == 0:
        return "unknown"
    if head.startswith(_PNG_SIG):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"%PDF-") or b"%PDF-" in head[:1024]:
        return "pdf"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"):
            return "heif"
    if len(head) >= 12 and head[4:8] in _MP4_BOX_TYPES:
        return "mp4"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:2] in (b"II", b"MM") and head[2:4] in (b"*\x00", b"\x00*"):
        return "tiff"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"OggS":
        return "ogg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"):
            return "heif"
    if head.startswith(b"ID3"):
        return "mp3"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "mp3"
    suffix = p.suffix.lower()
    if suffix in (".md", ".markdown"):
        return "markdown"
    if suffix == ".xmind":
        return "xmind"
    if suffix == ".posm":
        return "posm"
    if suffix == ".posf":
        return "posf"
    if suffix == ".uof":
        return "uof"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        kind = _zip_kind(p)
        if kind:
            return kind
    if _looks_utf8_text(p):
        return "text"
    return "unknown"


def _zip_kind(path) -> str | None:
    """zip 容器细分：docx（word/document.xml）/ ofd（OFD.xml）/ None。"""
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return None
    if "word/document.xml" in names:
        return "docx"
    if "OFD.xml" in names:
        return "ofd"
    if "_meta/meta.xml" in names:
        return "uof"
    if "metadata.json" in names and "content.json" in names:
        return "xmind"
    if "meta.json" in names:
        return "posm"
    return None


# ---------------------------------------------------------------- PNG
def _chunk(ctype: bytes, payload: bytes) -> bytes:
    """拼一个 PNG chunk（长度 + 类型 + 数据 + CRC32）。"""
    return (
        struct.pack(">I", len(payload))
        + ctype
        + payload
        + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)
    )


def _png_chunks(data: bytes):
    """迭代 (type, payload, data_offset)；遇截断即停止（不抛）。"""
    if not data.startswith(_PNG_SIG):
        return
    pos, n = 8, len(data)
    while pos + 8 <= n:
        length = int.from_bytes(data[pos:pos + 4], "big")
        ctype = data[pos + 4:pos + 8]
        dstart = pos + 8
        dend = dstart + length
        if length < 0 or dend + 4 > n:
            return
        yield ctype, data[dstart:dend], dstart
        pos = dend + 4
        if ctype == b"IEND":
            return


def _png_keyword(payload: bytes) -> tuple:
    """tEXt/zTXt/iTXt 共用：拆出 keyword 与剩余字节。"""
    idx = payload.find(b"\x00")
    if idx <= 0 or idx > 79:
        return b"", payload
    return payload[:idx], payload[idx + 1:]


def _png_text_entries(data: bytes) -> list:
    out = []
    for ctype, payload, off in _png_chunks(data):
        try:
            if ctype == b"tEXt":
                kw, rest = _png_keyword(payload)
                if not kw:
                    continue
                text = _decode(rest, "latin-1")
                out.append(_entry("png.tEXt", _decode(kw, "latin-1"),
                                  text, off))
            elif ctype == b"zTXt":
                kw, rest = _png_keyword(payload)
                if not kw or len(rest) < 1:
                    continue
                text = _decode(zlib.decompress(rest[1:]), "latin-1")
                out.append(_entry("png.zTXt", _decode(kw, "latin-1"),
                                  text, off))
            elif ctype == b"iTXt":
                kw, rest = _png_keyword(payload)
                if not kw or len(rest) < 2:
                    continue
                comp_flag = rest[0]
                body = rest[2:]
                # 语言标签与翻译名都以 NUL 结尾
                for _ in range(2):
                    cut = body.find(b"\x00")
                    body = b"" if cut < 0 else body[cut + 1:]
                if comp_flag == 1:
                    body = zlib.decompress(body)
                text = _decode(body, "utf-8")
                out.append(_entry("png.iTXt", _decode(kw, "utf-8"),
                                  text, off))
        except (zlib.error, ValueError, IndexError):
            continue
    return out


def inject_png_text(path: str, keyword: str, text: str) -> None:
    """在 PNG 的 IHDR 后插入文本 chunk（keyword 1-79 字节，Latin-1 安全）。

    - text 可 Latin-1 编码 → 写 tEXt（TC260 常见做法）；
    - 含中文等非 Latin-1 字符 → 自动改写字 iTXt（UTF-8），保证不丢内容；
    - 同名关键字去重（tEXt/iTXt 都按 keyword 判），重复注入只保留最新一条。
    """
    if not isinstance(keyword, str) or not isinstance(text, str):
        raise ValueError("keyword 与 text 必须是字符串")
    try:
        kw = keyword.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError(
            "keyword 含非 Latin-1 字符（修复指引：tEXt 关键字限 Latin-1）"
        )
    if not 1 <= len(kw) <= 79:
        raise ValueError("keyword 长度须 1-79 字节（实际 %d）" % len(kw))
    if b"\x00" in kw:
        raise ValueError("keyword 不得含 NUL")
    try:
        body = text.encode("latin-1")
        ctype = b"tEXt"
        payload = kw + b"\x00" + body
    except UnicodeEncodeError:
        # iTXt：keyword \0 压缩标志 压缩方法 语言标签 \0 翻译名 \0 UTF-8 正文
        ctype = b"iTXt"
        payload = kw + b"\x00" + bytes([0, 0]) + b"\x00\x00"
        payload += text.encode("utf-8")
    data = _read(path)
    if not data.startswith(_PNG_SIG):
        raise ValueError("不是 PNG：%s（修复指引：先 sniff 确认容器）" % path)
    chunks = list(_png_chunks(data))
    if not chunks or chunks[0][0] != b"IHDR":
        raise ValueError("PNG 首个 chunk 不是 IHDR：%s" % path)
    new = _chunk(ctype, payload)
    parts = [_PNG_SIG]
    inserted = False
    for ctype, payload, _off in chunks:
        if ctype == b"IHDR":
            parts.append(_chunk(b"IHDR", payload))
            parts.append(new)
            inserted = True
        elif ctype in (b"tEXt", b"iTXt"):
            # 同名关键字去重：重复注入只保留最新一条
            old_kw, _rest = _png_keyword(payload)
            if old_kw == kw:
                continue
            parts.append(_chunk(ctype, payload))
        else:
            parts.append(_chunk(ctype, payload))
    if not inserted:
        raise ValueError("PNG 缺少 IHDR：%s" % path)
    _write(path, b"".join(parts))


# ---------------------------------------------------------------- JPEG
def _jpeg_segments(data: bytes):
    """迭代 (marker, seg_offset, data_start, data_end)；遇畸形即停止。"""
    if not data.startswith(b"\xff\xd8"):
        return
    pos, n = 2, len(data)
    while pos + 2 <= n:
        if data[pos] != 0xFF:
            return
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0xD8 or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if marker == 0xD9:
            yield marker, pos, pos + 2, pos + 2
            return
        if pos + 4 > n:
            return
        length = int.from_bytes(data[pos + 2:pos + 4], "big")
        if length < 2 or pos + 2 + length > n:
            return
        ds = pos + 4
        de = pos + 2 + length
        yield marker, pos, ds, de
        pos = de
        if marker == 0xDA:
            return


def _tiff_value(tiff: bytes, bo: str, field) -> tuple:
    """按 TIFF 条目取 (值字节, 值在 TIFF 内的偏移)。"""
    typ, count, raw4, entry_pos = field
    if count <= 0:
        return b"", entry_pos + 8
    if count <= 4:                      # 值内联在条目的 4 字节里
        return raw4[:count], entry_pos + 8
    off = int.from_bytes(raw4, bo)
    if off < 0 or off >= len(tiff):
        return b"", entry_pos + 8
    return tiff[off:off + count], off


def _tiff_entries(tiff: bytes, ifd_off: int, bo: str):
    """迭代 IFD 条目 (tag, type, count, raw4)；畸形即停止。"""
    if ifd_off + 2 > len(tiff):
        return
    count = int.from_bytes(tiff[ifd_off:ifd_off + 2], bo)
    pos = ifd_off + 2
    for _ in range(min(count, 4096)):
        if pos + 12 > len(tiff):
            return
        tag = int.from_bytes(tiff[pos:pos + 2], bo)
        typ = int.from_bytes(tiff[pos + 2:pos + 4], bo)
        cnt = int.from_bytes(tiff[pos + 4:pos + 8], bo)
        raw4 = tiff[pos + 8:pos + 12]
        yield tag, typ, cnt, raw4, pos
        pos += 12


def _exif_user_comments(tiff: bytes) -> list:
    """从 TIFF（EXIF）里取 UserComment（0x9286）文本，返回 [(text, off)]。"""
    if len(tiff) < 8:
        return []
    bo = "little" if tiff[:2] == b"II" else "big"
    if int.from_bytes(tiff[2:4], bo) != 42:
        return []
    ifd0 = int.from_bytes(tiff[4:8], bo)
    targets = [ifd0]
    for tag, typ, cnt, raw4, _pos in _tiff_entries(tiff, ifd0, bo):
        # ExifIFD 指针：UserComment 通常挂在子 IFD 上
        if tag == 0x8769 and typ == 4 and cnt == 1:
            sub = int.from_bytes(raw4, bo)
            if 0 < sub < len(tiff):
                targets.append(sub)
    out = []
    seen = set()
    for off in targets:
        if off in seen:
            continue
        seen.add(off)
        for tag, typ, cnt, raw4, pos in _tiff_entries(tiff, off, bo):
            if tag != 0x9286:
                continue
            raw, voff = _tiff_value(tiff, bo, (typ, cnt, raw4, pos))
            if not raw:
                continue
            text = _decode_exif_user_comment(raw, bo)
            if text:
                out.append((text, voff))
    return out


def _decode_exif_user_comment(raw: bytes, bo: str) -> str:
    """UserComment：8 字节字符集前缀 + 正文（UNICODE 走 UTF-16）。"""
    if len(raw) <= 8:
        return ""
    prefix, body = raw[:8], raw[8:]
    if prefix == b"UNICODE\x00":
        if body[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return _decode(body, "utf-16")
        # EXIF 惯例：无 BOM 时按 UCS-2 大端解释
        return _decode(body, "utf-16-be")
    if prefix == b"JIS\x00\x00\x00\x00\x00":
        return _decode(body, "shift_jis")
    if prefix == b"\x00" * 8 or prefix == b"ASCII\x00\x00\x00":
        return _decode(body, "latin-1")
    return _decode(raw, "latin-1")


def _jpeg_entries(data: bytes) -> list:
    out = []
    for marker, seg_off, ds, de in _jpeg_segments(data):
        if marker != 0xE1:
            continue
        payload = data[ds:de]
        if payload.startswith(XMP_NS):
            off = ds + len(XMP_NS)
            out.append(_entry("jpeg.app1.xmp", "XMP",
                              _decode(data[off:de], "utf-8"), off))
        elif payload.startswith(EXIF_SIG):
            tiff = payload[len(EXIF_SIG):]
            tiff_off = ds + len(EXIF_SIG)
            for text, rel in _exif_user_comments(tiff):
                out.append(_entry("jpeg.exif.UserComment",
                                  "UserComment", text, tiff_off + rel))
    return out


# ---------------------------------------------------------------- PDF
def _pdf_objects(data: bytes):
    """迭代 (obj_num, body_start, body_end)；按文件内出现顺序。"""
    pat = re.compile(rb"(?m)^\s*(\d{1,10})\s+(\d{1,5})\s+obj\b")
    for m in pat.finditer(data):
        start = m.end()
        end = data.find(b"endobj", start)
        if end < 0:
            end = len(data)
        yield int(m.group(1)), start, end


def _pdf_unescape(raw: bytes) -> str:
    """解 PDF 字符串转义（\\( \\) \\\\ \\n \\ddd 等），返回文本。"""
    out = bytearray()
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch != 0x5C:
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        esc = raw[i]
        table = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
        if esc in table:
            out.append(table[esc])
            i += 1
        elif 0x30 <= esc <= 0x37:      # 八进制最多 3 位
            j = i
            while j < n and j < i + 3 and 0x30 <= raw[j] <= 0x37:
                j += 1
            out.append(int(raw[i:j], 8) & 0xFF)
            i = j
        elif esc in (0x0A, 0x0D):      # 续行
            i += 1
        else:
            out.append(esc)
            i += 1
    return _decode(bytes(out), "latin-1")


def _pdf_string_value(raw: bytes) -> str:
    """PDF 字符串：字面量 (...) 或十六进制 <...>。"""
    if raw.startswith(b"(") and raw.endswith(b")"):
        return _pdf_unescape(raw[1:-1])
    if raw.startswith(b"<") and raw.endswith(b">"):
        hexs = re.sub(rb"\s+", b"", raw[1:-1])
        if len(hexs) % 2:
            hexs += b"0"
        try:
            return _decode(bytes.fromhex(hexs.decode("ascii")), "latin-1")
        except (ValueError, UnicodeError):
            return ""
    return ""


def _pdf_info_entries(body: bytes) -> list:
    """从一个 PDF 对象体里取 Info 字典的字符串键值，返回 [(key, text, off)]。"""
    out = []
    keys = b"|".join(k.encode("ascii") for k in _PDF_KEYS)
    pat = re.compile(
        rb"/(?P<name>[A-Za-z0-9#]+)\s*"
        rb"(?P<val>\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]+>)"
    )
    for m in pat.finditer(body):
        name = m.group("name").decode("latin-1")
        if name not in _PDF_KEYS:
            continue
        text = _pdf_string_value(m.group("val"))
        if text:
            out.append((name, text, m.start("val")))
    return out


def _pdf_entries(data: bytes) -> list:
    out = []
    for _num, start, end in _pdf_objects(data):
        body = data[start:end]
        if b"stream" in body:
            soff = body.find(b"stream")
            after = body[soff + 6:soff + 8]
            if after in (b"\r\n", b"\n\r"):
                sstart = soff + 8
            elif after[:1] in (b"\n", b"\r"):
                sstart = soff + 7
            else:
                sstart = soff + 6
            send = body.find(b"endstream", sstart)
            if send < 0:
                send = len(body)
            raw = body[sstart:send]
            if b"/FlateDecode" in body[:soff]:
                try:
                    raw = zlib.decompressobj().decompress(raw)
                except zlib.error:
                    continue
            text = _decode(raw, "utf-8")
            if "x:xmpmeta" in text or "<?xpacket" in text:
                off = start + sstart
                out.append(_entry("pdf.xmp", "XMP", text, off))
            continue
        for key, text, rel in _pdf_info_entries(body):
            out.append(_entry("pdf.info", key, text, start + rel))
    return out


# ---------------------------------------------------------------- MP4
def _boxes(data: bytes, start: int, end: int):
    """迭代 (type, box_start, body_start, box_end)；畸形即停止。"""
    pos, n = start, min(end, len(data))
    while pos + 8 <= n:
        size = int.from_bytes(data[pos:pos + 4], "big")
        btype = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            if pos + 16 > n:
                return
            size = int.from_bytes(data[pos + 8:pos + 16], "big")
            hdr = 16
        elif size == 0:
            size = n - pos
        if size < hdr or pos + size > n:
            return
        yield btype, pos, pos + hdr, pos + size
        pos += size


def _mp4_keys_map(data: bytes, start: int, end: int) -> dict:
    """解析 keys 盒（fullbox）：返回 {1 基索引: 键名}。"""
    keys = {}
    body = data[start:end]
    if len(body) < 8:
        return keys
    count = int.from_bytes(body[4:8], "big")
    pos = 8
    for idx in range(1, count + 1):
        if pos + 8 > len(body):
            break
        size = int.from_bytes(body[pos:pos + 4], "big")
        if size < 8 or pos + size > len(body):
            break
        name = body[pos + 8:pos + size]
        try:
            keys[idx] = name.decode("utf-8")
        except UnicodeDecodeError:
            keys[idx] = name.decode("latin-1")
        pos += size
    return keys


def _mp4_ilst_entries(data: bytes, start: int, end: int,
                      keys: dict | None = None) -> list:
    """ilst 条目：每个 item 内有一个 data 盒（4 字节类型 + 4 字节 locale + 值）。

    keys 给定时（moov.udta.meta keys/ilst 布局），item type 是 1 基索引，
    用 keys 映射还原键名（如 AIGC）。
    """
    out = []
    for itype, _s, ibody, iend in _boxes(data, start, end):
        if keys and itype and int.from_bytes(itype, "big") in keys:
            key = keys[int.from_bytes(itype, "big")]
        else:
            key = itype.decode("latin-1")
        item_name = key
        mean = ""
        name = ""
        value = None
        sub_time = None
        for stype, _ss, sbody, send in _boxes(data, ibody, iend):
            payload = data[sbody:send]
            if stype == b"data":
                if len(payload) >= 8:
                    value = payload[8:]
                    data_type = int.from_bytes(payload[0:4], "big") & 0xFFFFFF
                    sub_time = sbody + 8
                    if data_type == 2:
                        value_text = _decode_utf16(value)
                    else:
                        value_text = _decode(value, "utf-8").strip("\x00")
                    value = value_text
            elif stype == b"mean":
                mean = _decode(payload[4:], "utf-8").strip("\x00")
            elif stype == b"name":
                name = _decode(payload[4:], "utf-8").strip("\x00")
        if value is None:
            continue
        if mean or name:
            item_name = "%s:%s" % (mean, name) if mean else name
        off = sub_time if sub_time is not None else ibody
        out.append(_entry("mp4.ilst", item_name, value, off))
    return out


def _mp4_entries(data: bytes) -> list:
    out = []

    def walk(start: int, end: int, keys_map: dict | None = None) -> None:
        keys_map = keys_map or {}
        for btype, bstart, body, bend in _boxes(data, start, end):
            if btype == b"XMP_":
                text = _decode(data[body:bend], "utf-8").strip("\x00")
                out.append(_entry("mp4.XMP_", "XMP", text, body))
            elif btype == b"uuid":
                payload = data[body:bend]
                if payload[:16] == XMP_UUID:
                    text = _decode(payload[16:], "utf-8").strip("\x00")
                    out.append(_entry("mp4.uuid", "XMP", text, body + 16))
            elif btype == b"ilst":
                out.extend(_mp4_ilst_entries(data, body, bend, keys_map))
            elif btype == b"meta":
                # meta 是 fullbox：前 4 字节版本/标志；keys 盒决定 ilst 键名
                sub_keys = {}
                for stype, ss, sbody, send in _boxes(data, body + 4, bend):
                    if stype == b"keys":
                        sub_keys = _mp4_keys_map(data, sbody, send)
                walk(body + 4, bend, sub_keys)
            elif btype in _MP4_CONTAINERS:
                walk(body, bend, keys_map)

    end = len(data)
    # 只从顶层盒遍历；解析失败时由 _boxes 自然停止
    walk(0, end)
    return out


# ---------------------------------------------------------------- MP3
def _syncsafe(raw: bytes) -> int:
    return ((raw[0] & 0x7F) << 21) | ((raw[1] & 0x7F) << 14) | (
        (raw[2] & 0x7F) << 7) | (raw[3] & 0x7F)


def _decode_utf16(raw: bytes) -> str:
    try:
        return raw.decode("utf-16").strip("\x00")
    except UnicodeError:
        return _decode(raw, "latin-1")


def _id3_text(payload: bytes) -> str:
    """解 ID3 文本帧 payload（首字节编码 + 文本/描述）。"""
    if not payload:
        return ""
    enc = payload[0]
    body = payload[1:]
    if enc == 0:
        return _decode(body, "latin-1").strip("\x00")
    if enc == 3:
        return _decode(body, "utf-8").strip("\x00")
    if enc in (1, 2):
        name = "utf-16" if enc == 1 else "utf-16-be"
        try:
            return body.decode(name).strip("\x00")
        except UnicodeError:
            return _decode(body, "latin-1").strip("\x00")
    return _decode(body, "latin-1").strip("\x00")


def _split_id3_pair(payload: bytes) -> tuple:
    """拆 TXXX 的 description / value（按编码决定的终止符）。"""
    if not payload:
        return "", ""
    enc = payload[0]
    rest = payload[1:]
    if enc in (1, 2):
        idx = -1
        for i in range(0, len(rest) - 1, 2):
            if rest[i:i + 2] == b"\x00\x00":
                idx = i
                break
        if idx < 0:
            return _id3_text(payload), ""
        desc_raw, val_raw = rest[:idx], rest[idx + 2:]
        if enc == 1:
            return _decode_utf16(desc_raw), _decode_utf16(val_raw)
        return (_decode(desc_raw, "utf-16-be").strip("\x00"),
                _decode(val_raw, "utf-16-be").strip("\x00"))
    idx = rest.find(b"\x00")
    if idx < 0:
        return _id3_text(payload), ""
    desc_raw, val_raw = rest[:idx], rest[idx + 1:]
    codec = "utf-8" if enc == 3 else "latin-1"
    return (_decode(desc_raw, codec).strip("\x00"),
            _decode(val_raw, codec).strip("\x00"))


def _mp3_entries(data: bytes) -> list:
    out = []
    if not data.startswith(b"ID3") or len(data) < 10:
        return out
    ver = data[3]
    flags = data[5]
    tag_size = _syncsafe(data[6:10])
    end = min(len(data), 10 + tag_size)
    pos = 10
    if flags & 0x40 and pos + 4 <= end:      # 扩展头
        ext = int.from_bytes(data[pos:pos + 4], "big")
        if ver == 3:
            pos += 4 + ext
        else:                                # v2.4：长度含自身 4 字节
            pos += ext
    while pos + 10 <= end:
        fid = data[pos:pos + 4]
        if not re.match(rb"^[A-Z0-9]{4}$", fid):
            break
        if ver == 4:
            fsize = _syncsafe(data[pos + 4:pos + 8])
        else:
            fsize = int.from_bytes(data[pos + 4:pos + 8], "big")
        fstart = pos + 10
        fend = fstart + fsize
        if fsize < 0 or fend > end:
            break
        if fid == b"TXXX":
            payload = data[fstart:fend]
            desc, value = _split_id3_pair(payload)
            if desc or value:
                out.append(_entry("mp3.id3.TXXX", desc, value,
                                  fstart + 1))
        pos = fend
    return out


# ---------------------------------------------------------------- WAV
def _wav_chunks(data: bytes):
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return
    pos, n = 12, len(data)
    while pos + 8 <= n:
        cid = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        ds = pos + 8
        de = ds + size
        if size < 0 or de > n:
            return
        yield cid, ds, de
        pos = de + (size & 1)


def _wav_entries(data: bytes) -> list:
    out = []
    for cid, ds, de in _wav_chunks(data):
        if cid != b"LIST":
            continue
        if data[ds:ds + 4] != b"INFO":
            continue
        pos, n = ds + 4, de
        while pos + 8 <= n:
            sid = data[pos:pos + 4]
            size = int.from_bytes(data[pos + 4:pos + 8], "little")
            sstart = pos + 8
            send = sstart + size
            if size < 0 or send > n:
                break
            key = _decode(sid, "latin-1").strip()
            text = _decode(data[sstart:send], "utf-8").strip("\x00")
            if key and text:
                out.append(_entry("wav.INFO", key, text, sstart))
            pos = send + (size & 1)
    return out


# ---------------------------------------------------------------- sidecar
def _sidecar_path(path) -> Path:
    return Path(str(path) + ".aigc.json")


def write_sidecar(path: str, obj: dict) -> str:
    """写 <path>.aigc.json（UTF-8、ensure_ascii=False、缩进 2），返回路径。"""
    if not isinstance(obj, (dict, list)):
        raise ValueError("sidecar 内容须为 JSON 对象或数组")
    target = _sidecar_path(path)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise ValueError("无法写 sidecar：%s（%s）" % (target, exc))
    return str(target)


def read_sidecar(path: str) -> dict | None:
    """读 sidecar，不存在返回 None；存在但非法 JSON 抛 ValueError。"""
    target = _sidecar_path(path)
    if not target.is_file():
        return None
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("无法读 sidecar：%s（%s）" % (target, exc))
    try:
        obj = json.loads(text)
    except ValueError as exc:
        raise ValueError("sidecar 不是合法 JSON：%s（%s）" % (target, exc))
    if not isinstance(obj, dict):
        raise ValueError("sidecar 顶层不是对象：%s（修复指引：sidecar 须是标注对象）"
                         % target)
    return obj


# ---------------------------------------------------------------- extract
def _sidecar_entries(path) -> list:
    target = _sidecar_path(path)
    if not target.is_file():
        return []
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return []
    return [_entry("sidecar", "AIGC", text, 0)]


def extract(path: str) -> list[dict]:
    """读出文件内所有可能承载标识的文本块（按文件出现顺序，末尾附 sidecar）。"""
    data = _read(path)
    kind = sniff(path)
    out = []
    if kind == "png":
        out = _png_text_entries(data)
    elif kind == "jpeg":
        out = _jpeg_entries(data)
    elif kind == "pdf":
        out = _pdf_entries(data)
    elif kind == "mp4":
        out = _mp4_entries(data)
    elif kind == "mp3":
        out = _mp3_entries(data)
    elif kind == "wav":
        out = _wav_entries(data)
        out.extend(_wav_aigc_entries(data))
    elif kind == "tiff":
        out = _tiff_aigc_entries(path)
    elif kind == "gif":
        out = _gif_entries(data)
    elif kind == "webp":
        out = _webp_entries(data)
    elif kind == "flac":
        out = _flac_entries(path)
    elif kind == "ogg":
        out = _ogg_entries(path)
    elif kind == "heif":
        out = _heif_entries(path)
    elif kind in ("xmind", "posm", "posf"):
        out = _json_meta_entries(path, kind)
    elif kind == "uof":
        out = _uof_entries(path)
    elif kind == "docx":
        out = _docx_entries(path)
    elif kind == "ofd":
        out = _ofd_entries(path)
    elif kind == "markdown":
        text = _decode(data, "utf-8")
        out = [{"container": "text", "key": "", "kind": "text",
                "text": text, "offset": 0}]
        block = _md_block(text)
        if block:
            out.append(_entry("markdown.AIGC", "AIGC", block, 0))
    elif kind == "text":
        text = _decode(data, "utf-8")
        if text:
            out = [{"container": "text", "key": "", "kind": "text",
                    "text": text, "offset": 0}]
    out.extend(_sidecar_entries(path))
    return out


# ---------------------------------------------------------------- docx / ofd / markdown
_MD_BLOCK = re.compile(r"<!--\s*AIGC:(.*?)-->", re.S)


def _xml_text(elem) -> str:
    """拼出元素内全部文本（含子元素，如 vt:lpwstr）。"""
    return "".join(elem.itertext())


def _docx_entries(path: str) -> list:
    import xml.etree.ElementTree as ET
    out = []
    try:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read("docProps/custom.xml")
    except (KeyError, zipfile.BadZipFile, OSError):
        return out
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for prop in root:
        if prop.attrib.get("name") != "AIGC":
            continue
        text = _xml_text(prop).strip()
        if text:
            out.append(_entry("docx.custom", "AIGC", text, 0))
    return out


def _ofd_entries(path: str) -> list:
    import xml.etree.ElementTree as ET
    out = []
    try:
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.startswith("CustomDatas/")]
            for name in names:
                raw = zf.read(name)
                try:
                    root = ET.fromstring(raw)
                except ET.ParseError:
                    continue
                for elem in root.iter():
                    tag = elem.tag.split("}")[-1]
                    if tag != "CustomData":
                        continue
                    if elem.attrib.get("Name") != "AIGC":
                        continue
                    text = _xml_text(elem).strip()
                    if text:
                        out.append(_entry("ofd.CustomData", "AIGC", text, 0))
    except (zipfile.BadZipFile, OSError):
        return out
    return out


def _md_block(text: str) -> str | None:
    m = _MD_BLOCK.search(text or "")
    return m.group(1).strip() if m else None


def _strip_md_block(text: str) -> str:
    """去掉头部 AIGC 注释块（含其后的一个换行），使内容口径与写入前一致。"""
    return re.sub(r"<!--\s*AIGC:.*?-->\n?", "", text or "", count=1, flags=re.S)


# ---------------------------------------------------------------- xmind / posm / posf / uof
_META_JSON = {"xmind": "metadata.json", "posm": "meta.json", "posf": "meta.json"}


def _json_meta_entries(path: str, kind: str) -> list:
    """xmind/posm/posf：从 metadata.json/meta.json 的 AIGC 键取标识串。"""
    out = []
    name = _META_JSON.get(kind)
    if not name:
        return out
    try:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read(name)
    except (KeyError, zipfile.BadZipFile, OSError):
        return out
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return out
    val = obj.get("AIGC") if isinstance(obj, dict) else None
    if isinstance(val, str) and val.strip():
        out.append(_entry(kind + ".AIGC", "AIGC", val, 0))
    elif isinstance(val, (dict, list)):
        out.append(_entry(kind + ".AIGC", "AIGC",
                          json.dumps(val, ensure_ascii=False,
                                     separators=(",", ":")), 0))
    return out


def _uof_entries(path: str) -> list:
    """UOF：从 _meta/meta.xml 的 <meta:AIGC> 元素取标识串。"""
    import xml.etree.ElementTree as ET
    out = []
    try:
        with zipfile.ZipFile(path) as zf:
            raw = zf.read("_meta/meta.xml")
    except (KeyError, zipfile.BadZipFile, OSError):
        return out
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for elem in root.iter():
        if elem.tag.split("}")[-1] != "AIGC":
            continue
        text = (elem.text or "").strip()
        if text:
            out.append(_entry("uof.AIGC", "AIGC", text, 0))
    return out


# ---------------------------------------------------------------- media content rules
def _tiff_content(data: bytes) -> bytes:
    """TIFF 内容 = 图像 strip 数据（StripOffsets/StripByteCounts），无则整文件。"""
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        return data
    bo = "little" if data[:2] == b"II" else "big"
    if int.from_bytes(data[2:4], bo) != 42:
        return data
    ifd0 = int.from_bytes(data[4:8], bo)
    offsets, counts = [], []
    for tag, typ, cnt, raw4, pos in _tiff_entries(data, ifd0, bo):
        if tag not in (0x111, 0x117):
            continue
        raw, _off = _tiff_value(data, bo, (typ, cnt, raw4, pos))
        width = 4 if typ == 4 else 2
        vals = [int.from_bytes(raw[i:i + width], bo)
                for i in range(0, len(raw), width)]
        (offsets if tag == 0x111 else counts).extend(vals)
    if not offsets or len(offsets) != len(counts):
        return data
    parts = []
    for off, ln in zip(offsets, counts):
        if 0 <= off < len(data):
            parts.append(data[off:off + ln])
    return b"".join(parts) if parts else data


def _gif_content(data: bytes) -> bytes:
    """GIF 内容 = 首个图像块起点到 trailer 前的字节（标识扩展插在其前）。"""
    blocks = list(_gif_blocks(data, _gif_start(data), len(data)))
    first = next((st for kind, st, _e in blocks if kind == "image"), None)
    trailer = next((st for kind, st, _e in blocks if kind == "trailer"), None)
    if first is None:
        return data
    return data[first:]


def _webp_content(data: bytes) -> bytes:
    if len(data) < 12 or data[8:12] != b"WEBP":
        return data
    parts = []
    for fourcc, body, end in _webp_chunks(data):
        if fourcc in (b"VP8 ", b"VP8L", b"ALPH"):
            parts.append(data[body:end])
    return b"".join(parts) if parts else data


def _wav_content(data: bytes) -> bytes:
    """WAV 内容 = 除 AIGC 子块外全部 chunk 的原始字节（头+payload+pad）。"""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    parts = []
    for fourcc, body, end in _wav_chunks(data):
        if fourcc == b"AIGC":
            continue
        parts.append(data[body - 8:end])
    return b"".join(parts) if parts else data


# ---------------------------------------------------------------- media extra readers
def _tiff_aigc_entries(path: str) -> list:
    """TIFF：IFD0 tag 0x2BC（UNDEFINED）里的 JSON 标识。"""
    data = _read(path)
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        return []
    bo = "little" if data[:2] == b"II" else "big"
    if int.from_bytes(data[2:4], bo) != 42:
        return []
    ifd0 = int.from_bytes(data[4:8], bo)
    for tag, typ, cnt, raw4, pos in _tiff_entries(data, ifd0, bo):
        if tag != 0x2BC:
            continue
        raw, _off = _tiff_value(data, bo, (typ, cnt, raw4, pos))
        text = _decode(raw, "utf-8")
        if not text:
            continue
        if "xmpmeta" in text or "xpacket" in text:
            frags = _json_fragments(_unescape_xml(text))
            if frags:
                return [_entry("tiff.IFD0", "AIGC", frags[0][0], 0)]
            continue
        return [_entry("tiff.IFD0", "AIGC", text, 0)]
    return []


def _gif_start(data: bytes) -> int:
    """GIF 头部 6 + LSD 7 + 全局色表（若有）之后的偏移。"""
    if len(data) < 13:
        return 13
    flags = data[10]
    start = 13
    if flags & 0x80:
        start += 3 * (2 ** ((flags & 7) + 1))
    return min(start, len(data))


def _gif_blocks(data: bytes, pos: int, end: int):
    """迭代 GIF 顶层块：(kind, start, end)。kind ∈ image/extension/trailer。"""
    while pos < end:
        b = data[pos]
        if b == 0x3B:
            yield "trailer", pos, pos + 1
            return
        if b == 0x2C:
            if pos + 10 > end:
                return
            flags = data[pos + 9]
            p = pos + 10
            if flags & 0x80:
                p += 3 * (2 ** ((flags & 7) + 1))
            p += 1  # LZW min code size
            while p < end:
                n = data[p]
                p += 1
                if n == 0:
                    break
                p += n
            yield "image", pos, min(p, end)
            pos = p
            continue
        if b == 0x21:
            if data[pos:pos + 3] == b"\x21\xff\x0b":
                p = pos + 3 + 11          # 跳过 app identifier/auth code
                while p < end:
                    n = data[p]
                    p += 1
                    if n == 0:
                        break
                    p += n
                yield "extension", pos, min(p, end)
                pos = p
                continue
            p = pos + 2
            while p < end:
                n = data[p]
                p += 1
                if n == 0:
                    break
                p += n
            yield "extension", pos, min(p, end)
            pos = p
            continue
        return


def _gif_entries(data: bytes) -> list:
    out = []
    for kind, start, end in _gif_blocks(data, _gif_start(data), len(data)):
        block = data[start:end]
        if kind != "extension" or not block.startswith(b"\x21\xff\x0b"):
            continue
        if b"XMP DataXMP" not in block[:32]:
            continue
        body = block[3 + 11:]
        packet = bytearray()
        pos = 0
        while pos < len(body):
            n = body[pos]
            pos += 1
            if n == 0:
                break
            packet += body[pos:pos + n]
            pos += n
        text = _decode(bytes(packet), "utf-8")
        if text and ("xmpmeta" in text or "xpacket" in text):
            out.append(_entry("gif.XMP", "AIGC", text, start))
    return out


def _webp_chunks(data: bytes):
    pos, end = 12, len(data)
    while pos + 8 <= end:
        fourcc = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = pos + 8
        yield fourcc, body, min(body + size, end)
        pos = body + size + (size & 1)


def _webp_entries(data: bytes) -> list:
    out = []
    if data[8:12] != b"WEBP":
        return out
    for fourcc, body, end in _webp_chunks(data):
        if fourcc != b"XMP ":
            continue
        text = _decode(data[body:end].rstrip(b"\x00"), "utf-8")
        if text:
            out.append(_entry("webp.XMP", "XMP", text, body))
    return out


def _wav_chunks(data: bytes):
    pos, end = 12, len(data)
    while pos + 8 <= end:
        fourcc = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = pos + 8
        yield fourcc, body, min(body + size, end)
        pos = body + size + (size & 1)


def _wav_aigc_entries(data: bytes) -> list:
    out = []
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return out
    for fourcc, body, end in _wav_chunks(data):
        if fourcc != b"AIGC":
            continue
        text = _decode(data[body:end].rstrip(b"\x00"), "utf-8")
        if text:
            out.append(_entry("wav.AIGC", "AIGC", text, body))
    return out


def _id3v2_size(data: bytes) -> int:
    if data[:3] != b"ID3" or len(data) < 10:
        return 0
    raw = data[6:10]
    return 10 + ((raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3])


def _flac_blocks(data: bytes):
    """迭代 FLAC metadata blocks：(type, body_start, body_end, header_start)。"""
    pos, end = 4, len(data)
    while pos + 4 <= end:
        header = data[pos]
        last, btype = header >> 7, header & 0x7F
        size = int.from_bytes(data[pos + 1:pos + 4], "big")
        body = pos + 4
        yield btype, body, min(body + size, end), pos
        pos = body + size
        if last:
            return


def _flac_entries(path: str) -> list:
    data = _read(path)
    if data[:4] != b"fLaC":
        return []
    out = []
    for btype, body, end, _hdr in _flac_blocks(data):
        if btype != 4:      # VORBIS_COMMENT
            continue
        block = data[body:end]
        if len(block) < 4:
            continue
        try:
            pos = 4 + int.from_bytes(block[0:4], "little")   # skip vendor
            count = int.from_bytes(block[pos:pos + 4], "little")
            pos += 4
            for _ in range(count):
                ln = int.from_bytes(block[pos:pos + 4], "little")
                pos += 4
                cmt = block[pos:pos + ln]
                pos += ln
                if cmt.upper().startswith(b"AIGC="):
                    text = _decode(cmt[5:], "utf-8")
                    if text:
                        out.append(_entry("flac.VORBIS", "AIGC", text,
                                          body + pos - ln))
        except (IndexError, ValueError):
            continue
    return out


# ---------------------------------------------------------------- heif content rule
def _heif_primary_id(data: bytes) -> int | None:
    """从 meta/pitm 取主图 item_ID。"""
    for btype, body, bend, _size in _heif_boxes(data, 0, len(data)):
        if btype != b"meta":
            continue
        for t2, b2, e2, _s2 in _heif_boxes(data, body + 4, bend):
            if t2 != b"pitm":
                continue
            ver = data[b2]
            p = b2 + 4
            if ver == 0:
                return int.from_bytes(data[p:p + 2], "big")
            return int.from_bytes(data[p:p + 4], "big")
    return None


def _heif_content(data: bytes) -> bytes:
    """HEIF 内容 = 主图 item（pitm）的 extent 字节；失败回退整文件。"""
    pid = _heif_primary_id(data)
    if pid is None:
        return data
    _ms, _me, items = _heif_meta_items(data)
    meta = items.get(pid) or {}
    parts = []
    for off, ln in meta.get("offsets") or []:
        if 0 <= off < len(data):
            parts.append(data[off:off + ln])
    return b"".join(parts) if parts else data


# ---------------------------------------------------------------- ogg / heif readers
def _ogg_pages(data: bytes):
    """迭代 Ogg 页：(payload, start, end)；畸形即停止。"""
    pos, n = 0, len(data)
    while pos + 27 <= n:
        if data[pos:pos + 4] != b"OggS":
            return
        nseg = data[pos + 26]
        if pos + 27 + nseg > n:
            return
        segs = data[pos + 27:pos + 27 + nseg]
        body = pos + 27 + nseg
        plen = sum(segs)
        end = body + plen
        if end > n:
            return
        yield data[body:end], pos, end
        pos = end


def _ogg_packets(data: bytes) -> list:
    """把页载荷拼成包；用 lacing<255 判包结束（跨页续表由 header_type 位 0x01 表示）。"""
    packets, cur = [], bytearray()
    for payload, _start, _end in _ogg_pages(data):
        p = 0
        # 段表在页头：重解析一次段长
        # 这里按 255 边界直接扫描 payload（等价：段长序列由页头决定）
    # 简化实现：重新走页并读段表
    packets, cur = [], bytearray()
    for payload, start, _end in _ogg_pages(data):
        nseg = data[start + 26]
        segs = data[start + 27:start + 27 + nseg]
        p = 0
        for seg in segs:
            cur += payload[p:p + seg]
            p += seg
            if seg < 255:
                packets.append(bytes(cur))
                cur = bytearray()
    if cur:
        packets.append(bytes(cur))
    return packets


def _vorbis_comments(packet: bytes) -> list:
    """解析 Vorbis/Opus 注释包，返回注释字符串列表。"""
    if packet.startswith(b"\x03vorbis"):
        pos = 7
    elif packet.startswith(b"OpusTags"):
        pos = 8
    else:
        return []
    try:
        vlen = int.from_bytes(packet[pos:pos + 4], "little")
        pos += 4 + vlen
        cnt = int.from_bytes(packet[pos:pos + 4], "little")
        pos += 4
        out = []
        for _ in range(cnt):
            ln = int.from_bytes(packet[pos:pos + 4], "little")
            pos += 4
            out.append(packet[pos:pos + ln].decode("utf-8", "replace"))
            pos += ln
        return out
    except (IndexError, ValueError):
        return []


def _ogg_entries(path: str) -> list:
    data = _read(path)
    packets = _ogg_packets(data)
    if len(packets) < 2:
        return []
    for cmt in _vorbis_comments(packets[1]):
        if cmt.upper().startswith("AIGC="):
            text = cmt[5:]
            if text:
                return [_entry("ogg.comment", "AIGC", text, 0)]
    return []


def _heif_boxes(data: bytes, start: int, end: int, bo: str = "little"):
    """ISO BMFF 盒：yield (type, body_start, box_end, size)。"""
    pos = start
    while pos + 8 <= end:
        size = int.from_bytes(data[pos:pos + 4], "big")
        btype = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = int.from_bytes(data[pos + 8:pos + 16], "big")
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr or pos + size > end:
            return
        yield btype, pos + hdr, pos + size, size
        pos += size


def _heif_meta_items(data: bytes):
    """解析 meta：返回 (meta_start, meta_end, items)。

    items = {item_id: {"name": str|None, "offsets": [(off, len)],
                       "type": bytes|None}}
    infe 采用 fullbox 布局：version(1)+flags(3)+item_ID(2)+protection(2)
    [+ item_type(4) + item_name(NUL) if version>=2]。
    """
    items = {}
    for btype, body, bend, _size in _heif_boxes(data, 0, len(data)):
        if btype != b"meta":
            continue
        for t2, b2, e2, _s2 in _heif_boxes(data, body + 4, bend):
            if t2 == b"iinf":
                ver = data[b2]
                p = b2 + 4
                cnt_bytes = 2 if ver == 0 else 4
                cnt = int.from_bytes(data[p:p + cnt_bytes], "big")
                p += cnt_bytes
                for _ in range(cnt):
                    kids = list(_heif_boxes(data, p, e2))
                    if not kids:
                        break
                    t3, b3, e3, sz3 = kids[0]
                    p = e3
                    if t3 != b"infe":
                        continue
                    v = data[b3]
                    item_id = int.from_bytes(data[b3 + 4:b3 + 6], "big")
                    item_type = data[b3 + 8:b3 + 12] if v >= 2 else None
                    name = None
                    if v >= 2:
                        nstart = b3 + 12
                        nend = data.find(b"\x00", nstart, e3)
                        if nend < 0:
                            nend = e3
                        name = data[nstart:nend].decode("utf-8", "replace")
                    items.setdefault(item_id, {})
                    items[item_id].update({"name": name, "type": item_type})
            elif t2 == b"iloc":
                ver = data[b2]
                p = b2 + 4
                off_size = data[p] >> 4
                len_size = data[p] & 0x0F
                p += 1
                base_size = data[p] >> 4
                idx_size = data[p] & 0x0F if ver in (1, 2) else 0
                p += 1
                id_size = 2 if ver < 2 else 4
                cnt = int.from_bytes(data[p:p + (2 if ver < 2 else 4)], "big")
                p += (2 if ver < 2 else 4)
                for _ in range(cnt):
                    item_id = int.from_bytes(data[p:p + id_size], "big")
                    p += id_size
                    if ver in (1, 2):
                        p += 2  # construction_method
                    p += 2      # data_reference_index
                    base = int.from_bytes(data[p:p + base_size], "big") \
                        if base_size else 0
                    p += base_size
                    ext_cnt = int.from_bytes(data[p:p + 2], "big")
                    p += 2
                    exts = []
                    for _ in range(ext_cnt):
                        if idx_size:
                            p += idx_size
                        eoff = int.from_bytes(data[p:p + off_size], "big") \
                            if off_size else 0
                        p += off_size
                        elen = int.from_bytes(data[p:p + len_size], "big") \
                            if len_size else 0
                        p += len_size
                        exts.append((base + eoff, elen))
                    items.setdefault(item_id, {})
                    items[item_id]["offsets"] = exts
        return body, bend, items
    return None, None, {}


def _heif_entries(path: str) -> list:
    data = _read(path)
    _ms, _me, items = _heif_meta_items(data)
    for item_id, meta in items.items():
        if (meta.get("name") or "").upper() != "AIGC":
            continue
        for off, ln in meta.get("offsets") or []:
            if 0 <= off < len(data):
                text = _decode(data[off:off + ln], "utf-8")
                if text:
                    return [_entry("heif.item", "AIGC", text, off)]
    return []


# ---------------------------------------------------------------- JSON 候选
def _json_fragments(text: str) -> list:
    """从任意文本里挑出可解析的 JSON 片段（含 XMP 里嵌的 JSON）。"""
    out = []
    if not text:
        return out
    dec = json.JSONDecoder()
    i, n = 0, min(len(text), 8 * 1024 * 1024)
    attempts = 0
    while i < n and attempts < 20000:
        positions = [p for p in (text.find("{", i), text.find("[", i))
                     if 0 <= p < n]
        if not positions:
            break
        pos = min(positions)
        attempts += 1
        try:
            obj, end = dec.raw_decode(text, pos)
        except ValueError:
            i = pos + 1
            continue
        raw = text[pos:end]
        out.append((raw, obj))
        i = max(end, pos + 1)
    return out


def _unescape_xml(text: str) -> str:
    """XMP 文本里的 JSON 可能被实体转义（&quot; 等），先还原。"""
    try:
        return html.unescape(text)
    except (ValueError, TypeError):
        return text


def extract_json_candidates(path: str) -> list[dict]:
    """从 extract() 结果里挑出可解析为 JSON 的候选。

    返回 [{container, key, obj, raw}]；解析失败的项保留为
    {container, key, raw, obj: None, error: 说明}（不抛异常，便于体检报告列出）。
    """
    out = []
    for item in extract(path):
        text = item.get("text") or ""
        kind = item.get("kind")
        container = item.get("container")
        key = item.get("key")
        if kind == "json" or container == "sidecar":
            try:
                obj = json.loads(text)
            except (ValueError, TypeError) as exc:
                out.append({"container": container, "key": key,
                            "raw": text, "obj": None,
                            "error": "JSON 解析失败：%s" % exc})
                continue
            if not isinstance(obj, (dict, list)):
                out.append({"container": container, "key": key,
                            "raw": text, "obj": None,
                            "error": "顶层不是对象/数组"})
                continue
            out.append({"container": container, "key": key,
                        "raw": text, "obj": obj})
        elif kind == "xmp":
            frags = _json_fragments(_unescape_xml(text))
            if not frags:
                continue
            for raw, obj in frags:
                out.append({"container": container, "key": key,
                            "raw": raw, "obj": obj})
        elif text.lstrip()[:1] in ("{", "["):
            try:
                obj = json.loads(text)
            except (ValueError, TypeError):
                continue
            if not isinstance(obj, (dict, list)):
                continue
            out.append({"container": container, "key": key,
                        "raw": text, "obj": obj})
    return out


# ---------------------------------------------------------------- 内容字节
def _png_idat(data: bytes) -> bytes:
    parts = []
    for ctype, payload, _off in _png_chunks(data):
        if ctype == b"IDAT":
            parts.append(payload)
    if not parts:
        raise ValueError("PNG 缺少 IDAT（修复指引：文件未生成完？）")
    return b"".join(parts)


def _jpeg_span(data: bytes) -> bytes:
    sos = None
    for marker, seg_off, _ds, _de in _jpeg_segments(data):
        if marker == 0xDA:
            sos = seg_off
            break
    if sos is None:
        raise ValueError("JPEG 找不到 SOS(0xFFDA)（修复指引：文件截断？）")
    eoi = data.find(b"\xff\xd9", sos)
    if eoi < 0:
        raise ValueError("JPEG 找不到 EOI(0xFFD9)（修复指引：文件截断？）")
    return data[sos:eoi + 2]


def content_bytes(path: str, cntsel: str) -> bytes:
    """按 TC260 指南的 CntSel 取内容字节。

    'PNG'→所有 IDAT 数据拼接；'JPEG'→SOS(0xFFDA) 到 EOI(0xFFD9)；
    其他（'OTHER' 或空/未知）→ 整个文件。异常时抛 ValueError。
    """
    data = _read(path)
    sel = (cntsel or "").strip().upper()
    if sel == "PNG":
        return _png_idat(data)
    if sel == "JPEG":
        return _jpeg_span(data)
    return data


def content_bytes_for(path: str, container: str) -> tuple:
    """按容器给出「与标识无关」的内容字节，返回 (cntsel, bytes)。

    写/验两侧必须同口径（见 docs/DESIGN.md）：
    - png  → IDAT 拼接；jpeg → SOS..EOI
    - pdf  → 首个 %%EOF（含）之前的原始字节；增量更新追加其后
    - mp4  → 顶层 mdat 载荷拼接（只追加/替换 moov 外的标识，不动 mdat）
    - 其他 → 整个文件
    """
    if container == "png":
        return "PNG", content_bytes(path, "PNG")
    if container == "jpeg":
        return "JPEG", content_bytes(path, "JPEG")
    if container in ("docx", "ofd", "xmind", "posm", "posf", "uof"):
        skip_sets = {
            "docx": {"[Content_Types].xml", "_rels/.rels", "docProps/custom.xml"},
            "ofd": {"OFD.xml"},
            "xmind": {"metadata.json"},
            "posm": {"meta.json"},
            "posf": {"meta.json"},
            "uof": {"_meta/meta.xml"},
        }
        prefixes = {"ofd": ("CustomDatas/",)}
        parts = []
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name in skip_sets[container]:
                    continue
                if any(name.startswith(pfx) for pfx in prefixes.get(container, ())):
                    continue
                parts.append(name.encode("utf-8") + b"\x00" + zf.read(name))
        return "DFT", b"\x00".join(parts)
    if container == "ogg":
        data = _read(path)
        packets = _ogg_packets(data)
        return "DFT", b"".join(packets[2:]) if len(packets) > 2 else data
    if container == "heif":
        data = _read(path)
        return "DFT", _heif_content(data)
    if container == "tiff":
        data = _read(path)
        return "DFT", _tiff_content(data)
    if container == "gif":
        data = _read(path)
        return "DFT", _gif_content(data)
    if container == "webp":
        data = _read(path)
        return "DFT", _webp_content(data)
    if container == "wav":
        data = _read(path)
        return "DFT", _wav_content(data)
    if container == "mp3":
        data = _read(path)
        size = _id3v2_size(data)
        return "DFT", data[size:] if size else data
    if container == "flac":
        data = _read(path)
        audio = 4
        for _btype, _body, end, _hdr in _flac_blocks(data):
            audio = end
        return "DFT", data[audio:]
    data = _read(path)
    if container == "markdown":
        return "DFT", _strip_md_block(_decode(data, "utf-8")).encode("utf-8")
    if container == "pdf":
        idx = data.find(b"%%EOF")
        if idx < 0:
            raise ValueError("PDF 缺 %%EOF，无法界定原始内容")
        return "DFT", data[:idx + 5]
    if container == "mp4":
        parts = []
        for btype, _start, body, end in _boxes(data, 0, len(data)):
            if btype == b"mdat":
                parts.append(data[body:end])
        if not parts:
            raise ValueError("MP4 缺 mdat，无法界定媒体内容")
        return "DFT", b"".join(parts)
    return "DFT", data


# ---------------------------------------------------------------- 夹具
def make_png(path: str, text_kv: dict | None = None,
             width: int = 8, height: int = 8) -> None:
    """生成合法最小 PNG（1 个 IDAT），可选写入若干 tEXt。"""
    rows = b"".join(b"\x00" + b"\x11\x22\x33" * width
                    for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    parts = [_PNG_SIG, _chunk(b"IHDR", ihdr)]
    for key, value in (text_kv or {}).items():
        try:
            payload = (key.encode("latin-1") + b"\x00"
                       + value.encode("latin-1"))
        except UnicodeEncodeError:
            raise ValueError(
                "tEXt 仅支持 Latin-1（修复指引：中文请用 itxt 夹具/inject）"
            )
        parts.append(_chunk(b"tEXt", payload))
    parts.append(_chunk(b"IDAT", zlib.compress(rows)))
    parts.append(_chunk(b"IEND", b""))
    _write(path, b"".join(parts))


def make_png_with_ztxt(path: str, keyword: str, text: str) -> None:
    """生成带 zTXt chunk 的最小 PNG（zlib 压缩文本）。"""
    payload = (keyword.encode("latin-1") + b"\x00" + b"\x00"
               + zlib.compress(text.encode("latin-1")))
    _make_png_with_extra(path, _chunk(b"zTXt", payload))


def make_png_with_itxt(path: str, keyword: str, text: str,
                       compressed: bool = False) -> None:
    """生成带 iTXt chunk 的最小 PNG（UTF-8 文本，可压缩）。"""
    flag = 1 if compressed else 0
    body = text.encode("utf-8")
    if compressed:
        body = zlib.compress(body)
    payload = (keyword.encode("latin-1") + b"\x00" + bytes([flag, 0])
               + b"\x00" + b"\x00" + body)
    _make_png_with_extra(path, _chunk(b"iTXt", payload))


def _make_png_with_extra(path: str, extra: bytes) -> None:
    """在 IHDR 之后插入一个额外 chunk 的最小 PNG。"""
    rows = b"\x00" + b"\x11\x22\x33" * 8
    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    parts = [_PNG_SIG, _chunk(b"IHDR", ihdr), extra,
             _chunk(b"IDAT", zlib.compress(rows * 8)),
             _chunk(b"IEND", b"")]
    _write(path, b"".join(parts))


def _jpeg_seg(marker: int, payload: bytes) -> bytes:
    """拼一个 JPEG 段（0xFF + marker + 长度 + 数据）。"""
    return (b"\xff" + bytes([marker])
            + struct.pack(">H", len(payload) + 2) + payload)


def _jpeg_min_width(height: int, width: int) -> bytes:
    return (struct.pack(">BHHB", 8, height, width, 3)
            + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00")


def _jpeg_min_sos() -> bytes:
    return (b"\x03" + b"\x01\x00\x02\x11\x03\x11"
            + b"\x00\x3f\x00")


def make_jpeg_with_xmp(path: str, xmp_xml: str,
                       width: int = 8, height: int = 8) -> None:
    """生成最小 JPEG（SOI + APP1 XMP + SOS/EOI），可被 sniff/提取。"""
    xmp = XMP_NS + xmp_xml.encode("utf-8")
    data = (b"\xff\xd8"
            + _jpeg_seg(0xE1, xmp)
            + _jpeg_seg(0xC0, _jpeg_min_width(height, width))
            + _jpeg_seg(0xDA, _jpeg_min_sos())
            + b"\x12\x34\x56\x78"
            + b"\xff\xd9")
    _write(path, data)


def make_jpeg_with_exif(path: str, comment: str,
                        width: int = 8, height: int = 8) -> None:
    """生成带 EXIF UserComment（UNICODE）的最小 JPEG。"""
    payload = EXIF_SIG + _tiff_with_user_comment(comment)
    data = (b"\xff\xd8"
            + _jpeg_seg(0xE1, payload)
            + _jpeg_seg(0xC0, _jpeg_min_width(height, width))
            + _jpeg_seg(0xDA, _jpeg_min_sos())
            + b"\x12\x34\x56\x78"
            + b"\xff\xd9")
    _write(path, data)


def _tiff_with_user_comment(comment: str) -> bytes:
    """构造最小 little-endian TIFF：IFD0 → ExifIFD → UserComment。"""
    body = b"UNICODE\x00" + comment.encode("utf-16-be")
    ifd0_off = 8
    exif_ifd_off = ifd0_off + 2 + 12 + 4
    data_off = exif_ifd_off + 2 + 12 + 4
    out = bytearray(b"II" + struct.pack("<H", 42)
                    + struct.pack("<I", ifd0_off))
    out += struct.pack("<H", 1)
    out += struct.pack("<HHII", 0x8769, 4, 1, exif_ifd_off)
    out += struct.pack("<I", 0)
    out += struct.pack("<H", 1)
    out += struct.pack("<HHII", 0x9286, 7, len(body), data_off)
    out += struct.pack("<I", 0)
    out += body
    return bytes(out)


def make_pdf_with_xmp(path: str, xmp_xml: str) -> None:
    """生成最小 PDF 1.4（1 页 + /Metadata XMP 流，FlateDecode）。"""
    comp = zlib.compress(xmp_xml.encode("utf-8"))
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R /Metadata 4 0 R "
        b"/Info 5 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
        (b"<< /Type /Metadata /Subtype /XML /Length "
         + str(len(comp)).encode("ascii")
         + b" /Filter /FlateDecode >>\nstream\n" + comp
         + b"\nendstream"),
        (b"<< /Title (nf-labelcheck) /Producer (nf-labelcheck) "
         b"/Creator (tests) /Keywords (aigc) >>"),
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\n"
            % (len(objs) + 1))
    out += b"startxref\n%d\n%%%%EOF\n" % xref
    _write(path, bytes(out))


def _mp4_box(btype: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + btype + payload


def make_mp4_with_xmp(path: str, xmp_xml: str) -> None:
    """生成最小 MP4（ftyp + moov/udta/uuid XMP），可被提取。"""
    ftyp = _mp4_box(b"ftyp", b"isom" + struct.pack(">I", 512)
                    + b"isomiso2mp41")
    uuid = _mp4_box(b"uuid", XMP_UUID + xmp_xml.encode("utf-8"))
    moov = _mp4_box(b"moov", _mp4_box(b"udta", uuid))
    _write(path, ftyp + moov + _mp4_box(b"mdat", b""))


def make_mp4_with_stco(path: str, payload: bytes = b"NF-MEDIA-PAYLOAD") -> None:
    """生成 moov 在 mdat 之前、且 stco 指向 mdat 载荷的最小小 MP4（写入偏移修正用）。"""
    mdat = _mp4_box(b"mdat", payload)

    def build(stco_offset: int) -> bytes:
        stco = _mp4_box(b"stco", struct.pack(">II", 1, stco_offset))
        stbl = _mp4_box(b"stbl", stco)
        minf = _mp4_box(b"minf", stbl)
        mdia = _mp4_box(b"mdia", minf)
        trak = _mp4_box(b"trak", mdia)
        mvhd = _mp4_box(b"mvhd", b"\x00" * 8)
        return _mp4_box(b"moov", mvhd + trak)

    ftyp = _mp4_box(b"ftyp", b"isom" + struct.pack(">I", 512)
                    + b"isomiso2mp41")
    # 先占位算长度，再按真实绝对偏移重建（moov 长度与偏移数值无关）
    moov = build(0)
    payload_off = len(ftyp) + len(moov) + 8
    moov = build(payload_off)
    _write(path, ftyp + moov + mdat)


def make_mp4_with_ilst(path: str, tags: dict) -> None:
    """生成带 udta/meta/ilst 条目的最小 MP4（tags: {4 字节类型: 文本}）。"""
    items = []
    for btype, value in tags.items():
        if not isinstance(btype, bytes) or len(btype) != 4:
            raise ValueError("ilst 条目类型须为 4 字节")
        payload = struct.pack(">II", 1, 0) + value.encode("utf-8")
        items.append(_mp4_box(btype, _mp4_box(b"data", payload)))
    meta = struct.pack(">I", 0) + _mp4_box(b"ilst", b"".join(items))
    udta = _mp4_box(b"udta", _mp4_box(b"meta", meta))
    ftyp = _mp4_box(b"ftyp", b"isom" + struct.pack(">I", 512)
                    + b"isomiso2mp41")
    moov = _mp4_box(b"moov", udta + _mp4_box(b"mvhd", b"\x00" * 8))
    _write(path, ftyp + moov + _mp4_box(b"mdat", b""))


def _id3_frame(frame_id: bytes, payload: bytes, ver: int = 3) -> bytes:
    size = len(payload).to_bytes(4, "big")
    return frame_id + size + b"\x00\x00" + payload


def _id3_syncsafe(value: int) -> bytes:
    return bytes([(value >> 21) & 0x7F, (value >> 14) & 0x7F,
                  (value >> 7) & 0x7F, value & 0x7F])


def make_mp3_with_txxx(path: str, description: str, value: str) -> None:
    """生成最小 ID3v2.3 + TXXX 帧的 mp3 壳（音频帧为空）。"""
    payload = (b"\x01" + description.encode("utf-16")
               + b"\x00\x00" + value.encode("utf-16"))
    frame = _id3_frame(b"TXXX", payload)
    tag = b"ID3" + b"\x03\x00" + b"\x00" + _id3_syncsafe(len(frame))
    _write(path, tag + frame)


def make_wav_with_info(path: str, info_kv: dict) -> None:
    """生成最小 WAV（RIFF/WAVE + LIST/INFO）。"""
    subs = b""
    for key, value in info_kv.items():
        raw = value.encode("utf-8")
        subs += key.encode("ascii")[:4].ljust(4, b" ")
        subs += struct.pack("<I", len(raw)) + raw
        if len(raw) & 1:
            subs += b"\x00"
    list_payload = b"INFO" + subs
    body = b"WAVE" + b"LIST" + struct.pack("<I", len(list_payload))
    body += list_payload
    _write(path, b"RIFF" + struct.pack("<I", len(body)) + body)


# ---------------------------------------------------------------- docx / ofd 夹具
def _zip_write(path: str, entries: list) -> None:
    """写最小 zip（固定时间戳，便于测试断言确定性）。"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)


def make_docx(path: str, custom_property: str | None = None) -> None:
    """生成最小 DOCX（[Content_Types]/_rels/word/document.xml，可选 custom.xml）。"""
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
          'package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/'
          'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/'
            'document.xml"/></Relationships>')
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
           '2006/main"><w:body><w:p><w:r><w:t>demo</w:t></w:r></w:p></w:body>'
           '</w:document>')
    entries = [("[Content_Types].xml", ct), ("_rels/.rels", rels),
               ("word/document.xml", doc)]
    if custom_property is not None:
        custom = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Properties xmlns="http://schemas.openxmlformats.org/'
                  'officeDocument/2006/custom-properties" xmlns:vt="http://'
                  'schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
                  '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" '
                  'pid="2" name="AIGC"><vt:lpwstr>' + custom_property
                  + '</vt:lpwstr></property></Properties>')
        entries.append(("docProps/custom.xml", custom))
    _zip_write(path, entries)


def make_ofd(path: str, custom_data: str | None = None) -> None:
    """生成最小 OFD（OFD.xml + Doc_0/Document.xml + 一页内容，可选 CustomDatas）。"""
    ofd = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<ofd:OFD xmlns:ofd="http://www.ofdspec.org/2016" DocType="OFD" '
           'Version="1.0"><ofd:DocBody><ofd:DocInfo><ofd:DocID>demo</ofd:DocID>'
           '</ofd:DocInfo><ofd:DocRoot>Doc_0/Document.xml</ofd:DocRoot>'
           '</ofd:DocBody></ofd:OFD>')
    doc = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<ofd:Document xmlns:ofd="http://www.ofdspec.org/2016">'
           '<ofd:CommonData><ofd:PageArea><ofd:PhysicalBox>0 0 100 100'
           '</ofd:PhysicalBox></ofd:PageArea></ofd:CommonData>'
           '<ofd:Pages><ofd:Page ID="1" BaseLoc="Pages/Page_0/Content.xml"/>'
           '</ofd:Pages></ofd:Document>')
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<ofd:Page xmlns:ofd="http://www.ofdspec.org/2016"><ofd:Area>'
               '<ofd:PhysicalBox>0 0 100 100</ofd:PhysicalBox></ofd:Area>'
               '</ofd:Page>')
    entries = [("OFD.xml", ofd), ("Doc_0/Document.xml", doc),
               ("Doc_0/Pages/Page_0/Content.xml", content)]
    if custom_data is not None:
        custom = ('<?xml version="1.0" encoding="UTF-8"?>'
                  '<CustomData xmlns="http://www.ofdspec.org/2016" Name="AIGC" '
                  'Version="1.0"><Content>' + custom_data
                  + '</Content></CustomData>')
        entries.append(("CustomDatas/AIGC.xml", custom))
    _zip_write(path, entries)


def _make_zip_json(path: str, extra: list, meta_name: str,
                   aigc: str | None = None) -> None:
    entries = list(extra)
    meta = {"creator": "nf-labelcheck"}
    if aigc is not None:
        meta["AIGC"] = aigc
    entries.append((meta_name, json.dumps(meta, ensure_ascii=False)))
    _zip_write(path, entries)


def make_xmind(path: str, aigc: str | None = None) -> None:
    """生成最小 xmind（zip：content.json + metadata.json）。"""
    _make_zip_json(path, [("content.json", '{"sheets": []}')],
                   "metadata.json", aigc)


def make_posm(path: str, aigc: str | None = None) -> None:
    """生成最小 posm（zip：content.xml + meta.json）。"""
    _make_zip_json(path, [("content.xml", '<posm><title>demo</title></posm>')],
                   "meta.json", aigc)


def make_posf(path: str, aigc: str | None = None) -> None:
    """生成最小 posf（zip：pages/page_1.xml + meta.json）。"""
    _make_zip_json(path, [("pages/page_1.xml", '<page><title>demo</title></page>')],
                   "meta.json", aigc)


def make_uof(path: str, aigc: str | None = None) -> None:
    """生成最小 UOF（zip：_meta/meta.xml + document.xml）。"""
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<meta:Meta xmlns:meta="http://schemas.uof.org/cn/2009/meta">'
           '<meta:Title>demo</meta:Title>')
    if aigc is not None:
        xml += "<meta:AIGC>" + aigc + "</meta:AIGC>"
    xml += "</meta:Meta>"
    _zip_write(path, [("_meta/meta.xml", xml),
                      ("document.xml", "<document><body>demo</body></document>")])


# ---------------------------------------------------------------- media extra 夹具
def make_tiff(path: str, payload: bytes = b"TIFF-IMAGE-DATA") -> None:
    """生成最小小端 TIFF（IFD0: StripOffsets/StripByteCounts + strip 数据）。"""
    entries = 2
    ifd_size = 2 + entries * 12 + 4
    data_off = 8 + ifd_size

    def entry(tag, typ, count, value):
        return struct.pack("<HHI", tag, typ, count) + value

    out = bytearray()
    out += b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    out += struct.pack("<H", entries)
    out += entry(0x0111, 4, 1, struct.pack("<I", data_off))
    out += entry(0x0117, 4, 1, struct.pack("<I", len(payload)))
    out += struct.pack("<I", 0)
    out += payload
    _write(path, bytes(out))


def make_gif(path: str, payload: bytes = b"GIF-IMAGE") -> None:
    """生成结构合法的 GIF89a（LSD + 2 色全局表 + 1 个图像块 + trailer）。"""
    out = bytearray(b"GIF89a")
    # LSD: 宽=1 高=1，全局色表标志 + 色表大小 2 色，背景 0，像素比 0
    out += struct.pack("<HH", 1, 1) + bytes([0x80, 0, 0])
    out += b"\x00\x00\x00" + b"\xff\xff\xff"   # 2 色全局表
    out += b"\x2c" + struct.pack("<HHHH", 0, 0, 1, 1) + b"\x00"
    out += b"\x02" + bytes([2]) + b"\x44\x01" + b"\x00" + b"\x3b"
    _write(path, bytes(out))


def make_webp(path: str, payload: bytes = b"WEBP-IMAGE") -> None:
    """生成最小 WebP（RIFF + WEBP + VP8L 块）。"""
    chunk = b"VP8L" + struct.pack("<I", len(payload)) + payload
    if len(payload) % 2:
        chunk += b"\x00"
    body = b"WEBP" + chunk
    _write(path, b"RIFF" + struct.pack("<I", len(body)) + body)


def make_flac(path: str, payload: bytes = b"FLAC-AUDIO") -> None:
    """生成最小 FLAC（fLaC + STREAMINFO(last) + 音频字节）。"""
    streaminfo = b"\x00" * 34
    header = bytes([0x80]) + len(streaminfo).to_bytes(3, "big")
    _write(path, b"fLaC" + header + streaminfo + payload)


# ---------------------------------------------------------------- ogg / heif 夹具
_OGG_CRC_TABLE = []


def _ogg_crc_table():
    if _OGG_CRC_TABLE:
        return _OGG_CRC_TABLE
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = ((r << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if (r & 0x80000000) \
                else (r << 1) & 0xFFFFFFFF
        _OGG_CRC_TABLE.append(r)
    return _OGG_CRC_TABLE


def _ogg_crc(data: bytes) -> int:
    crc = 0
    table = _ogg_crc_table()
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ b) & 0xFF]
    return crc


def _ogg_page(payload: bytes, seq: int, granule: int = 0,
              header_type: int = 0) -> bytes:
    segs = []
    n = len(payload)
    while n >= 255:
        segs.append(255)
        n -= 255
    segs.append(n)
    header = (
        b"OggS" + b"\x00" + bytes([header_type]) + struct.pack("<Q", granule)
        + struct.pack("<I", 1234) + struct.pack("<I", seq)
        + b"\x00\x00\x00\x00" + bytes([len(segs)]) + bytes(segs)
    )
    page = bytearray(header + payload)
    crc = _ogg_crc(bytes(page))
    page[22:26] = struct.pack("<I", crc)
    return bytes(page)


def make_ogg(path: str, audio: bytes = b"OGG-AUDIO-FRAMES") -> None:
    """生成最小 Ogg/Vorbis（ident + comment + 1 个音频包，3 页）。"""
    ident = (b"\x01vorbis" + struct.pack("<I", 0) + b"\x02"
             + struct.pack("<I", 44100) + b"\x00" * 12 + b"\x00\x00" + b"\x01")
    vendor = b"nf-labelcheck"
    cmt = (b"\x03vorbis" + struct.pack("<I", len(vendor)) + vendor
           + struct.pack("<I", 0) + b"\x01")
    out = (_ogg_page(ident, 0, header_type=0x02) + _ogg_page(cmt, 1)
           + _ogg_page(audio, 2, header_type=0x04))
    _write(path, out)


def _heif_box(btype: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + btype + payload


def make_heif(path: str, payload: bytes = b"HEIF-PRIMARY-IMAGE") -> None:
    """生成最小 HEIF（ftyp + meta(hdlr/pitm/iinf v0/iloc v0) + mdat 主图）。"""
    ftyp = _heif_box(b"ftyp", b"heic" + struct.pack(">I", 0) + b"heicmif1")

    def build(iloc_offset: int) -> bytes:
        hdlr = _heif_box(b"hdlr", b"\x00\x00\x00\x00" + b"\x00" * 4
                         + b"pict" + b"\x00" * 12 + b"image\x00")
        pitm = _heif_box(b"pitm", b"\x00\x00\x00\x00" + struct.pack(">H", 1))
        infe = _heif_box(b"infe", b"\x02\x00\x00\x00" + struct.pack(">HH", 1, 0)
                         + b"hvc1" + b"image\x00")
        iinf = _heif_box(b"iinf", b"\x00\x00\x00\x00" + struct.pack(">H", 1)
                         + infe)
        iloc = _heif_box(
            b"iloc",
            b"\x00\x00\x00\x00" + bytes([0x44, 0x00]) + struct.pack(">H", 1)
            + struct.pack(">H", 1) + struct.pack(">H", 0)
            + struct.pack(">H", 1) + struct.pack(">I", iloc_offset)
            + struct.pack(">I", len(payload)))
        return _heif_box(b"meta", b"\x00\x00\x00\x00" + hdlr + pitm + iinf + iloc)

    meta = build(0)
    offset = len(ftyp) + len(meta) + 8
    meta = build(offset)
    _write(path, ftyp + meta + _heif_box(b"mdat", payload))
