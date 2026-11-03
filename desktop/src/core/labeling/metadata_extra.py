"""多格式容器元数据读取（metadata.sniff 未覆盖的常见容器）。

作者：impl（DSH agent）· 2026-11-02

支持清单（CONTAINERS）与读取载体：
- mov：moov.udta（含 meta/ilst）下的 ©nam/©too/©cmt 等文本 atom；
- mkv：EBML Tags/SimpleTag（TagName=TagString）里含 AIGC/XMP 的字符串；
- avi：RIFF LIST/INFO 子块（INAM/ISFT/ICMT 等）；
- pptx：zip 内 docProps/core.xml + docProps/custom.xml；
- xlsx：同上；
- svg：<metadata>/<desc> 里的 JSON 或文本；
- rtf：\\info 组里的 {\\*\\company}/{\\title} 等目标字符串。

纪律：
- 纯标准库；不 import metadata，解析逻辑独立实现。
- 嗅探双判：扩展名 + 文件头魔数（zip 类再查内部 entry）。
- 所有解析器对畸形输入返回「已解析部分」或空列表，不崩溃。
- 函数 ≤120 行；中文注释；raise 消息带修复指引。

限制：
- 大文件（>128 MB）拒绝整块读入（mov/mkv/avi 需要顺序扫描，暂不支持流式）。
- mkv 只取 AIGC/XMP 相关 SimpleTag；位于文件尾部且超出读取上限的 Tags 读不到。
- pptx/xlsx 只读 docProps 两个 XML，不解析正文；加密/非 zip 返回空。
"""

from __future__ import annotations

import json
import re
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

#: 本模块支持的容器清单（sniff_extra 的返回值域）。
CONTAINERS = ("mov", "mkv", "avi", "pptx", "xlsx", "svg", "rtf")

__all__ = ["CONTAINERS", "sniff_extra", "extract_extra", "selfcheck"]

#: 单文件读取上限：mov/mkv/avi 需要顺序扫描，超过即拒绝。
MAX_READ = 128 * 1024 * 1024
#: 单个 zip entry 解压上限（防止压缩炸弹撑爆内存）。
MAX_ZIP_ENTRY = 8 * 1024 * 1024

#: mov 的 ftyp 品牌白名单（QuickTime 与常见同族）。
_MOV_BRANDS = frozenset((b"qt  ", b"isom", b"mp41", b"mp42", b"MSNV"))
#: mov 的文本 atom 类型（© 开头 + 常见大写键）。
_MOV_TEXT_ATOMS = frozenset((
    b"\xa9nam", b"\xa9too", b"\xa9cmt", b"\xa9des", b"\xa9day",
    b"\xa9ART", b"\xa9alb", b"\xa9gen", b"\xa9cpy", b"\xa9wrt",
    b"\xa9url", b"\xa9lyr", b"\xa9grp", b"\xa9enc", b"\xa9mak",
    b"\xa9mod", b"\xa9prd", b"\xa9swr",
))
#: mov 的容器 atom（递归向下找 udta）。
_MOV_CONTAINERS = frozenset((
    b"moov", b"udta", b"meta", b"ilst", b"trak", b"mdia", b"minf",
    b"stbl", b"edts", b"dinf", b"mvex", b"moof", b"traf",
))

#: EBML 母元素（只有这些 ID 才继续向下递归）。
_EBML_MASTER = frozenset((
    0x18538067, 0x1254C367, 0x7373, 0x67C8, 0x63C0, 0x1549A966,
    0x1654AE6B, 0x1F43B675, 0x1941A469, 0x1043A770, 0x114D9B74,
    0x1C53BB6B, 0xAE, 0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE8, 0xE9,
    0x6D80, 0x6240, 0x5035, 0x45B9, 0x7670,
))
#: EBML 里 tags 相关的叶子元素。
_EBML_TAG_NAME = 0x45A3
_EBML_TAG_STRING = 0x4487

#: AVI RIFF INFO 子块白名单。
_AVI_INFO_KEYS = frozenset((
    "INAM", "ISFT", "ICMT", "IART", "ICOP", "ISBJ", "ICRD",
    "IGNR", "ICMS", "IENG", "IPRD", "IKYWD", "ICNT",
))

#: RTF \info 里可承载标识的目标字符串。
_RTF_KEYS = frozenset((
    "title", "subject", "author", "manager", "company", "category",
    "keywords", "comment", "doccomm", "operator",
))
_RTF_CTRL = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?")


# ---------------------------------------------------------------- 基础
def _read(path) -> bytes:
    """读整个文件；读不了 / 超上限给带修复指引的 ValueError。"""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as exc:
        raise ValueError(
            f"无法读取文件：{path}（{exc}）（修复指引：先确认路径存在且可读，"
            "或改用绝对路径重试）"
        ) from exc
    if size > MAX_READ:
        raise ValueError(
            f"文件过大（{size} 字节 > {MAX_READ}）：{path}"
            "（修复指引：先裁剪或拆分，或只保留容器头部后再试）"
        )
    try:
        return p.read_bytes()
    except OSError as exc:
        raise ValueError(
            f"无法读取文件：{path}（{exc}）（修复指引：先确认读权限，"
            "或把文件复制到可读目录后再试）"
        ) from exc


def _head(path, limit: int = 4096) -> bytes:
    """只读文件头（嗅探用，不整块载入）。"""
    try:
        with open(path, "rb") as fh:
            return fh.read(limit)
    except OSError as exc:
        raise ValueError(
            f"无法读取文件头：{path}（{exc}）（修复指引：先确认路径与读权限，"
            "再重试嗅探）"
        ) from exc


def _text(raw: bytes) -> str:
    """宽松解码：去掉 NUL，坏字节替换，绝不抛异常。"""
    return raw.replace(b"\x00", b"").decode("utf-8", "replace").strip()


def _local(tag: str) -> str:
    """取 XML 标签的本地名（去掉 {namespace} 前缀）。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _kind_of(key: str, text: str) -> str:
    """把文本块归类为 json / xmp / text（与 metadata._kind_of 同口径）。"""
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
        return "json" if isinstance(parsed, (dict, list)) else "text"
    return "text"


def _entry(container: str, key: str, text: str, offset: int) -> dict:
    """与 metadata._entry 同形状（含 kind，便于下游按类型挑候选）。"""
    return {
        "container": container,
        "key": key,
        "kind": _kind_of(key, text),
        "text": text,
        "offset": int(offset),
    }


# ---------------------------------------------------------------- sniff
def _is_mov(head: bytes) -> bool:
    """mov 魔数：ftyp + QuickTime 系品牌，或无 ftyp 的 moov/mdat 起头。"""
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return head[8:12] in _MOV_BRANDS
    return len(head) >= 8 and head[4:8] in (b"moov", b"mdat", b"wide")


def _is_svg(head: bytes) -> bool:
    """svg：以 <svg 开头，或以 <?xml 开头且前 4 KB 内出现 <svg。"""
    body = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    low = body.lower()
    if low.startswith(b"<svg"):
        return True
    if low.startswith(b"<?xml"):
        return b"<svg" in low
    return False


def _zip_names(path) -> set | None:
    """打开 zip 取名列表；坏 zip 返回 None。"""
    try:
        with zipfile.ZipFile(path) as zf:
            return set(zf.namelist())
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None


def sniff_extra(path: str) -> str | None:
    """按「扩展名 + 文件头魔数」双判容器；不匹配返回 None。

    zip 类（pptx/xlsx）还要求内部 entry 存在；扩展名不符即判 None，
    避免把改名文件误认成受支持容器。
    """
    p = Path(path)
    suffix = p.suffix.lower()
    head = _head(p)
    if not head:
        return None
    if suffix in (".mov", ".qt") and _is_mov(head):
        return "mov"
    if suffix in (".mkv", ".mk3d") and head[:4] == b"\x1aE\xdf\xa3":
        return "mkv"
    if suffix == ".avi" and head[:4] == b"RIFF" and head[8:12] in (b"AVI ", b"AVIX"):
        return "avi"
    if suffix in (".pptx", ".xlsx"):
        if not (head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06")):
            return None
        names = _zip_names(p) or set()
        if suffix == ".pptx" and "ppt/presentation.xml" in names:
            return "pptx"
        if suffix == ".xlsx" and "xl/workbook.xml" in names:
            return "xlsx"
        return None
    if suffix == ".svg" and _is_svg(head):
        return "svg"
    if suffix == ".rtf" and head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"{\\rtf"):
        return "rtf"
    return None


# ---------------------------------------------------------------- mov
def _atom_header(data: bytes, pos: int, end: int):
    """解析一个 atom 头 → (size, type, payload_start, next_pos)；畸形返回 None。"""
    if pos + 8 > end:
        return None
    size = struct.unpack_from(">I", data, pos)[0]
    atype = data[pos + 4:pos + 8]
    head = 8
    if size == 1:
        if pos + 16 > end:
            return None
        size = struct.unpack_from(">Q", data, pos + 8)[0]
        head = 16
    elif size == 0:
        size = end - pos
    if size < head or pos + size > end:
        return None
    return size, atype, pos + head, pos + size


def _mov_text(data: bytes, start: int, end: int) -> str:
    """取 atom 文本：兼容 iTunes data 子 atom 与 2 字节长度前缀。"""
    chunk = data[start:end]
    if len(chunk) >= 16 and chunk[4:8] == b"data":
        chunk = chunk[16:]
    if len(chunk) >= 2 and struct.unpack(">H", chunk[:2])[0] == len(chunk) - 2:
        chunk = chunk[2:]
    return _text(chunk)


def _mov_walk(data: bytes, start: int, end: int, out: list, depth: int) -> None:
    """递归走 atom 树，收集文本 atom（最多 8 层，畸形即停）。"""
    pos = start
    while pos + 8 <= end and depth <= 8:
        hdr = _atom_header(data, pos, end)
        if hdr is None:
            return
        _size, atype, payload, nxt = hdr
        if atype in _MOV_TEXT_ATOMS:
            value = _mov_text(data, payload, nxt)
            if value:
                out.append(_entry("mov.udta", atype.decode("latin-1"),
                                  value, payload))
        elif atype in _MOV_CONTAINERS:
            child = payload
            if atype == b"meta" and data[payload:payload + 4] == b"\x00" * 4:
                child += 4
            _mov_walk(data, child, nxt, out, depth + 1)
        pos = nxt


def _mov_entries(data: bytes) -> list:
    """mov 入口：从顶层 atom 开始走树。"""
    out: list = []
    _mov_walk(data, 0, len(data), out, 0)
    return out


# ---------------------------------------------------------------- mkv
def _vint(data: bytes, pos: int, keep_marker: bool):
    """读 EBML 变长整数 → (值, 新位置)；数据不足返回 (None, pos)。"""
    if pos >= len(data) or data[pos] == 0:
        return None, pos
    first = data[pos]
    length = 1
    mask = 0x80
    while not first & mask:
        mask >>= 1
        length += 1
        if length > 8:
            return None, pos
    if pos + length > len(data):
        return None, pos
    value = first if keep_marker else first & (mask - 1)
    for i in range(1, length):
        value = (value << 8) | data[pos + i]
    return value, pos + length


def _ebml_walk(data: bytes, start: int, end: int, pairs: list,
               depth: int) -> None:
    """递归走 EBML，收集 TagName/TagString（畸形即停，保留已解析部分）。"""
    pos = start
    while pos < end and depth <= 12:
        eid, after = _vint(data, pos, True)
        if eid is None:
            return
        size, payload = _vint(data, after, False)
        if size is None or payload > end:
            return
        length = payload - after
        if size == (1 << (7 * length)) - 1:
            size = end - payload
        stop = payload + size
        if stop > end or stop < payload:
            return
        if eid in _EBML_MASTER:
            _ebml_walk(data, payload, stop, pairs, depth + 1)
        elif eid == _EBML_TAG_NAME:
            pairs.append(("name", _text(data[payload:stop]), payload))
        elif eid == _EBML_TAG_STRING:
            pairs.append(("value", _text(data[payload:stop]), payload))
        pos = stop


def _aigcish(value: str) -> bool:
    """字符串是否与 AIGC/XMP 有关（大小写不敏感）。"""
    low = (value or "").lower()
    return "aigc" in low or "xmp" in low


def _mkv_raw(data: bytes) -> list:
    """兜底：在可打印 ASCII 串里找含 AIGC/XMP 的片段。"""
    out: list = []
    for m in re.finditer(rb"[\x20-\x7e]{8,}", data):
        value = m.group().decode("ascii", "replace")
        if _aigcish(value):
            out.append(_entry("mkv.raw", "AIGC", value, m.start()))
        if len(out) >= 32:
            break
    return out


def _mkv_entries(data: bytes) -> list:
    """mkv 入口：结构化 Tags 优先，找不到再退化为原文扫描。"""
    pairs: list = []
    _ebml_walk(data, 0, len(data), pairs, 0)
    out: list = []
    pending = None
    for kind, value, off in pairs:
        if kind == "name":
            pending = (value, off)
            continue
        name = pending[0] if pending else ""
        if _aigcish(name) or _aigcish(value):
            out.append(_entry("mkv.Tags", name or "AIGC", value, off))
        pending = None
    return out or _mkv_raw(data)


# ---------------------------------------------------------------- avi
def _riff_chunks(data: bytes, start: int, end: int):
    """迭代 RIFF 子块 → (fourcc, payload_start, payload_end)；截断即停。"""
    pos = start
    while pos + 8 <= end:
        cid = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        payload = pos + 8
        stop = payload + size
        if stop > end:
            return
        yield cid, payload, stop
        pos = stop + (size & 1)


def _avi_info(data: bytes, start: int, end: int, out: list) -> None:
    """读 LIST/INFO 下的文本子块。"""
    for cid, payload, stop in _riff_chunks(data, start, end):
        key = cid.decode("latin-1")
        if key in _AVI_INFO_KEYS:
            out.append(_entry("avi.INFO", key, _text(data[payload:stop]),
                              payload))


def _avi_entries(data: bytes) -> list:
    """avi 入口：RIFF/AVI 头 + 顶层 LIST/INFO。"""
    out: list = []
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] not in (b"AVI ", b"AVIX"):
        return out
    for cid, payload, stop in _riff_chunks(data, 12, len(data)):
        if cid == b"LIST" and stop - payload >= 4 and data[payload:payload + 4] == b"INFO":
            _avi_info(data, payload + 4, stop, out)
    return out


# ---------------------------------------------------------------- pptx / xlsx
def _props_entries(raw: bytes, container: str, base: int) -> list:
    """解析 docProps XML：core 取子元素文本，custom 取 property@name。"""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    out: list = []
    for child in list(root):
        key = child.get("name") or _local(child.tag)
        value = "".join(child.itertext()).strip()
        if value:
            out.append(_entry(container, key, value, base))
    return out


def _office_entries(path, kind: str) -> list:
    """pptx/xlsx：读 docProps/core.xml 与 custom.xml（加密/坏 zip 返回空）。"""
    out: list = []
    try:
        with zipfile.ZipFile(path) as zf:
            for part, suffix in (("docProps/core.xml", "core"),
                                 ("docProps/custom.xml", "custom")):
                try:
                    info = zf.getinfo(part)
                except KeyError:
                    continue
                if info.file_size > MAX_ZIP_ENTRY:
                    continue
                out.extend(_props_entries(zf.read(info),
                                          f"{kind}.{suffix}",
                                          info.header_offset))
    except (zipfile.BadZipFile, OSError, RuntimeError, KeyError,
            NotImplementedError, zlib.error):
        return out
    return out


# ---------------------------------------------------------------- svg
def _svg_regex(text: str) -> list:
    """畸形 XML 的兜底：正则取 <metadata>/<desc> 文本。"""
    out: list = []
    for tag in ("metadata", "desc"):
        pat = re.compile(rf"<{tag}\b[^>]*>(.*?)</{tag}>", re.S | re.I)
        for m in pat.finditer(text):
            body = re.sub(r"(?s)<[^>]+>", " ", m.group(1))
            body = re.sub(r"\s+", " ", body).strip()
            if body:
                out.append(_entry("svg." + tag, tag, body, m.start()))
    return out


def _svg_entries(data: bytes) -> list:
    """svg 入口：XML 解析优先（保留 JSON 原文），失败走正则兜底。"""
    text = data.decode("utf-8", "replace")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _svg_regex(text)
    out: list = []
    for elem in root.iter():
        tag = _local(elem.tag)
        if tag not in ("metadata", "desc"):
            continue
        value = "".join(elem.itertext()).strip()
        if value:
            pos = text.find(value)
            out.append(_entry("svg." + tag, tag, value, pos if pos >= 0 else 0))
    return out


# ---------------------------------------------------------------- rtf
def _rtf_braced(text: str, pos: int) -> str:
    """取 pos 处 {…} 的组内文本（跳过转义花括号）。"""
    depth = 0
    i = pos
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[pos + 1:i]
        i += 1
    return text[pos + 1:]


def _rtf_plain(text: str, pos: int) -> str:
    """取控制字后不带花括号的裸文本（直到 } 或下一个控制字）。"""
    i = pos
    while i < len(text) and text[i] not in "}\\\r\n":
        i += 1
    return text[pos:i]


def _rtf_decode(raw: str) -> str:
    """解 RTF 转义：\\{ \\} \\\\ \\'hh \\uN，并丢弃其它控制字。"""
    out: list = []
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in "\\{}":
                out.append(nxt)
                i += 2
                continue
            if nxt == "'":
                hexs = raw[i + 2:i + 4]
                if len(hexs) == 2 and all(c in "0123456789abcdefABCDEF" for c in hexs):
                    out.append(bytes([int(hexs, 16)]).decode("cp1252", "replace"))
                i += 4
                continue
            m = re.match(r"u(-?\d+) ?", raw[i + 1:])
            if m:
                code = int(m.group(1))
                out.append(chr(code + 65536 if code < 0 else code))
                i += 1 + m.end()
                continue
            m = re.match(r"[a-zA-Z]+-?\d* ?", raw[i + 1:])
            i += 1 + (m.end() if m else 1)
            continue
        if char not in "{}\r\n":
            out.append(char)
        i += 1
    return "".join(out).strip()


def _rtf_entries(data: bytes) -> list:
    """rtf 入口：扫 \\info 目标控制字（\\title/\\company 等）。"""
    text = data.decode("latin-1", "replace")
    out: list = []
    i = 0
    while i < len(text):
        if text[i] != "\\":
            i += 1
            continue
        m = _RTF_CTRL.match(text, i)
        if m is None:
            i += 1
            continue
        word = m.group(1)
        end = m.end()
        if word in _RTF_KEYS:
            body = (_rtf_braced(text, end)
                    if end < len(text) and text[end] == "{" else
                    _rtf_plain(text, end))
            value = _rtf_decode(body)
            if value:
                out.append(_entry("rtf.info", word, value, i))
        i = end
    return out


# ---------------------------------------------------------------- 分发
_EXTRACTORS = {
    "mov": _mov_entries,
    "mkv": _mkv_entries,
    "avi": _avi_entries,
    "svg": _svg_entries,
    "rtf": _rtf_entries,
}


def extract_extra(path: str) -> list[dict]:
    """读出受支持容器里的标识文本块；不认识 / 畸形 → []。

    返回项与 metadata._entry 同形状：
    {container, key, kind, text, offset}。
    """
    kind = sniff_extra(path)
    if kind is None:
        return []
    if kind in ("pptx", "xlsx"):
        return _office_entries(path, kind)
    data = _read(path)
    try:
        return _EXTRACTORS[kind](data)
    except (ValueError, IndexError, KeyError, struct.error, UnicodeError):
        return []


# ---------------------------------------------------------------- 自检样例
def _atom(atype: bytes, payload: bytes) -> bytes:
    """拼一个 ISO BMFF atom（32 位长度）。"""
    return struct.pack(">I", len(payload) + 8) + atype + payload


def _ebml_size(size: int) -> bytes:
    """EBML 变长长度字段（找不到合适宽度就固定 8 字节）。"""
    for length in range(1, 8):
        if size < (1 << (7 * length)) - 1:
            return ((1 << (7 * length)) | size).to_bytes(length, "big")
    return ((1 << 56) | size).to_bytes(8, "big")


def _ebml(eid: int, payload: bytes) -> bytes:
    """拼一个 EBML 元素。"""
    width = max(1, (eid.bit_length() + 7) // 8)
    return eid.to_bytes(width, "big") + _ebml_size(len(payload)) + payload


def _riff(cid: bytes, payload: bytes) -> bytes:
    """拼一个 RIFF 子块（奇数长度补 pad）。"""
    pad = b"\x00" if len(payload) & 1 else b""
    return cid + struct.pack("<I", len(payload)) + payload + pad


def _write_zip(path, entries) -> None:
    """按给定 entry 列表写 zip。"""
    with zipfile.ZipFile(path, "w") as zf:
        for name, body in entries:
            zf.writestr(name, body)


_CORE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
    b'package/2006/metadata/core-properties"'
    b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b"<dc:title>NF-TITLE</dc:title><dc:creator>NF-CREATOR</dc:creator>"
    b"</cp:coreProperties>"
)
_CUSTOM_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Properties xmlns="http://schemas.openxmlformats.org/'
    b'officeDocument/2006/custom-properties"'
    b' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/'
    b'2006/docPropsVTypes">'
    b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2"'
    b' name="AIGC"><vt:lpwstr>{"AIGC":{"Label":"1"}}</vt:lpwstr></property>'
    b"</Properties>"
)
_SVG_DOC = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg">'
    b'<metadata>{"AIGC":{"Label":"1"}}</metadata>'
    b"<desc>NF-SVG-DESC</desc></svg>"
)
_RTF_DOC = (
    b"{\\rtf1\\ansi{\\info{\\title NF-RTF-TITLE}"
    b"{\\*\\company NF-RTF-CO}}{\\pard body}}"
)


def _sample_mov(path) -> None:
    """最小 mov：ftyp(qt) + moov.udta.©nam。"""
    udta = _atom(b"udta", _atom(b"\xa9nam", b"NF-MOV-TITLE")
                 + _atom(b"\xa9too", b"nf-mov-tool"))
    ftyp = _atom(b"ftyp", b"qt  \x00\x00\x02\x00qt  ")
    Path(path).write_bytes(ftyp + _atom(b"moov", udta))


def _sample_mkv(path) -> None:
    """最小 mkv：EBML 头 + Segment/Tags/SimpleTag(AIGC)。"""
    simple = _ebml(0x67C8, _ebml(0x45A3, b"AIGC")
                   + _ebml(0x4487, b'{"AIGC":{"Label":"1"}}'))
    tags = _ebml(0x1254C367, _ebml(0x7373, simple))
    header = _ebml(0x1A45DFA3, _ebml(0x4282, b"matroska"))
    Path(path).write_bytes(header + _ebml(0x18538067, tags))


def _sample_avi(path) -> None:
    """最小 avi：RIFF/AVI + LIST/INFO。"""
    info = _riff(b"LIST", b"INFO" + _riff(b"INAM", b"NF-AVI")
                 + _riff(b"ISFT", b"nf-avi-tool"))
    body = b"AVI " + info
    Path(path).write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def _sample_pptx(path) -> None:
    """最小 pptx：presentation.xml + docProps 两件。"""
    _write_zip(path, (
        ("[Content_Types].xml", b"<Types/>"),
        ("ppt/presentation.xml", b"<p/>"),
        ("docProps/core.xml", _CORE_XML),
        ("docProps/custom.xml", _CUSTOM_XML),
    ))


def _sample_xlsx(path) -> None:
    """最小 xlsx：workbook.xml + docProps/core.xml。"""
    _write_zip(path, (
        ("[Content_Types].xml", b"<Types/>"),
        ("xl/workbook.xml", b"<workbook/>"),
        ("docProps/core.xml", _CORE_XML),
    ))


def _sample_svg(path) -> None:
    """最小 svg：<metadata> JSON + <desc> 文本。"""
    Path(path).write_bytes(_SVG_DOC)


def _sample_rtf(path) -> None:
    """最小 rtf：\\info 里的 title 与 \\*\\company。"""
    Path(path).write_bytes(_RTF_DOC)


#: (容器, 扩展名, 样例构造器, 期望 key 片段, 期望 text 片段)
_SAMPLE_SPECS = (
    ("mov", ".mov", _sample_mov, "nam", "NF-MOV-TITLE"),
    ("mkv", ".mkv", _sample_mkv, "AIGC", "AIGC"),
    ("avi", ".avi", _sample_avi, "INAM", "NF-AVI"),
    ("pptx", ".pptx", _sample_pptx, "title", "NF-TITLE"),
    ("xlsx", ".xlsx", _sample_xlsx, "creator", "NF-CREATOR"),
    ("svg", ".svg", _sample_svg, "metadata", "AIGC"),
    ("rtf", ".rtf", _sample_rtf, "company", "NF-RTF-CO"),
)


def selfcheck() -> list[tuple[str, bool, str]]:
    """逐容器造最小样例，断言 sniff/extract 正确 → [(name, ok, detail)]。

    不写仓库、不联网：样例落在 tempfile 临时目录，退出自动清理。
    """
    results: list[tuple] = []
    with tempfile.TemporaryDirectory(prefix="nf-metaextra-") as tmp:
        for name, ext, build, key_part, text_part in _SAMPLE_SPECS:
            path = str(Path(tmp) / ("sample" + ext))
            detail = ""
            ok = False
            try:
                build(path)
                got = sniff_extra(path)
                entries = extract_extra(path)
                hit = any(key_part in e["key"] and text_part in e["text"]
                          for e in entries)
                ok = got == name and hit
                detail = (f"sniff={got} entries={len(entries)}"
                          + ("" if hit else "（缺期望文本）"))
            except (ValueError, OSError, KeyError, struct.error,
                    zipfile.BadZipFile) as exc:
                detail = f"异常：{exc!r}（修复指引：先核对样例构造器与解析入口）"
            results.append((name, ok, detail))
    return results
