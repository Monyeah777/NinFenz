"""JPEG / PDF 标识写入（TC260 隐式标识载体）。

作者：impl（DSH agent）· 2026-11-02
定位：nf-labelcheck 的「写入面」补充——原型此前只写过 PNG 文本块与 sidecar；
本模块补 JPEG（APP1 XMP）与 PDF（Info 字典 /AIGC）两条真实载体。

纪律：
- 不修改 metadata.py / checker.py / cli.py（Lead 负责集成）；
- 纯标准库；写面失败抛 ValueError（带说明），不裸崩；
- 写完后可被 `metadata.extract_json_candidates()` 原样取回（JPEG 走 XMP 分支，
  PDF 走 pdf.info 分支——AIGC 已在 `metadata._PDF_KEYS` 白名单内）。
"""

from __future__ import annotations

import html
import json
import re
import struct
from pathlib import Path

#: JPEG APP1 XMP 命名空间签名（metadata._jpeg_entries 按它识别 XMP）。
_XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
#: TC260 隐式标识扩展命名空间（GB 45438 / TC260-PG-202511A 约定的 AIGC 扩展）。
_TC260_NS = "http://www.tc260.org.cn/ns/AIGC/1.0/"
#: XMP 包首/包尾（begin 的 \ufeff 是 XMP 规定的 UTF-8 BOM 占位）。
_XPACKET_HEAD = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
_XPACKET_TAIL = '<?xpacket end="w"?>'
#: APP1 段长上限（2 字节长度字段，含长度字段自身）。
_APP1_MAX = 0xFFFF
#: PDF 里 AIGC 键名（metadata._PDF_KEYS 白名单已含 "AIGC"）。
_PDF_KEY = "AIGC"


# ---------------------------------------------------------------- 基础 IO
def _read(path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as exc:
        raise ValueError("无法读取文件：%s（%s）" % (path, exc))


def _write(path, data: bytes) -> None:
    try:
        Path(path).write_bytes(data)
    except OSError as exc:
        raise ValueError("无法写入文件：%s（%s）" % (path, exc))


def _check_json_text(json_text) -> object:
    """校验 json_text 为 JSON 文本；返回解析后的对象（失败给可读 ValueError）。"""
    if not isinstance(json_text, str) or not json_text.strip():
        raise ValueError("json_text 不得为空（修复指引：传标识 JSON 文本）")
    try:
        return json.loads(json_text)
    except ValueError as exc:
        raise ValueError("json_text 不是合法 JSON：%s" % exc)


# ---------------------------------------------------------------- JPEG
def _iter_segments(data: bytes):
    """迭代 JPEG 段 (start, end, payload_or_None)；遇 SOS 返回，其后是熵编码数据。

    payload = (marker, 段数据) 或 None（无长度的独立标记）。所有失败抛 ValueError。
    """
    if data[:2] != b"\xff\xd8":
        raise ValueError("不是 JPEG（缺 SOI 0xFFD8）")
    pos = 2
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            raise ValueError("JPEG 标记结构损坏（偏移 %d 不是 0xFF）" % pos)
        start = pos
        while pos < n and data[pos] == 0xFF:
            pos += 1
        if pos >= n:
            raise ValueError("JPEG 截断（缺标记字节）")
        marker = data[pos]
        pos += 1
        if marker == 0x00:
            raise ValueError("JPEG 结构异常：熵数据外的 0xFF00")
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            yield start, pos, None
            continue
        if marker == 0xD9:                      # EOI
            yield start, pos, None
            return
        if pos + 2 > n:
            raise ValueError("JPEG 截断（段缺长度字段）")
        seglen = int.from_bytes(data[pos:pos + 2], "big")
        if seglen < 2 or pos + seglen > n:
            raise ValueError("JPEG 段长越界（偏移 %d）" % start)
        end = pos + seglen
        yield start, end, (marker, data[pos + 2:end])
        pos = end
        if marker == 0xDA:                      # SOS：其后不再按段解析
            return


def _xmp_packet(json_text: str) -> bytes:
    """生成带 TC260:AIGC 的 XMP 包（JSON 经 XML 转义后放入元素文本）。"""
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
        '</x:xmpmeta>\n' % (_TC260_NS, escaped)
    ) + _XPACKET_TAIL
    return body.encode("utf-8")


def _app1(payload: bytes) -> bytes:
    """拼 APP1 段：0xFFE1 + 段长（含 2 字节自身）+ 数据。"""
    seglen = len(payload) + 2
    if seglen > _APP1_MAX:
        raise ValueError(
            "XMP 过大（APP1 段上限 %d 字节，实际 %d；修复指引：缩短 "
            "json_text 或拆分标识）" % (_APP1_MAX, seglen))
    return b"\xff\xe1" + struct.pack(">H", seglen) + payload


def inject_jpeg_xmp(path, json_text) -> None:
    """把 json_text 写入 JPEG 的 APP1 XMP（TC260 命名空间）。

    - 先移除文件里已存在的 XMP APP1（同一命名空间），再在 SOI 后插入新的，
      因此重复写入只保留 1 份；
    - SOS..EOI（含熵编码数据）逐字节不变；
    - 写后可被 `metadata.extract_json_candidates` 取回同一 json_text。
    """
    _check_json_text(json_text)
    data = _read(path)
    payload = _XMP_NS + _xmp_packet(json_text)
    app1 = _app1(payload)
    out = bytearray(data[:2])
    out += app1
    last = 2
    seen_sos = False
    for start, end, info in _iter_segments(data):
        last = end
        if info is not None and info[0] == 0xE1 and info[1].startswith(_XMP_NS):
            continue                              # 旧 XMP：丢弃（防重复）
        out += data[start:end]
        if info is not None and info[0] == 0xDA:
            seen_sos = True
    if not seen_sos:
        raise ValueError("JPEG 缺 SOS（不是可写入的完整 JPEG；修复指引：先确认文件完整）")
    out += data[last:]                           # SOS 之后的熵数据 + EOI 原样保留
    _write(path, bytes(out))


# ---------------------------------------------------------------- PDF
def _pdf_literal(text: str) -> bytes:
    """PDF 字面量字符串：转义 \\ ( ) 与换行，保证单行可解析。"""
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == "(":
            out.append("\\(")
        elif ch == ")":
            out.append("\\)")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return ("(" + "".join(out) + ")").encode("latin-1")


def _pdf_json_text(obj, json_text: str) -> str:
    """PDF 字面量只能安全回 ASCII：非 ASCII JSON 用 \\uXXXX 转义（解析结果不变）。"""
    if json_text.isascii():
        return json_text
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def _last_startxref(data: bytes) -> int:
    idx = data.rfind(b"startxref")
    if idx < 0:
        raise ValueError("PDF 缺 startxref（修复指引：确认是完整 PDF）")
    m = re.match(rb"startxref\s+(\d+)", data[idx:idx + 64])
    if not m:
        raise ValueError("PDF startxref 格式非法")
    off = int(m.group(1))
    if off >= len(data):
        raise ValueError("PDF startxref 偏移越界（%d >= %d）" % (off, len(data)))
    return off


def _classic_xref_guard(data: bytes, off: int) -> None:
    """确认 startxref 指向经典 xref 表；xref 流（PDF1.5+）明确拒绝。"""
    head = data[off:off + 8]
    if re.match(rb"xref[\s]", head) or head[:4] == b"xref":
        return
    window = data[off:off + 4096]
    if re.search(rb"/Type\s*/XRef\b", window):
        raise ValueError("xref 流 PDF 写入未支持")
    raise ValueError(
        "startxref 不指向 xref 表（偏移 %d；修复指引：用经典 xref 的 PDF）"
        % off)


def _trailer_region(data: bytes, off: int) -> bytes:
    tpos = data.find(b"trailer", off)
    if tpos < 0:
        raise ValueError("经典 xref 后缺 trailer 字典")
    return data[tpos:tpos + 4096]


def _ref(region: bytes, key: str):
    m = re.search((r"/%s\s+(\d+)\s+(\d+)\s+R" % key).encode("ascii"), region)
    return m.group(0) if m else None


def _object_num(region: bytes, key: str):
    m = re.search((r"/%s\s+(\d+)\s+(\d+)\s+R" % key).encode("ascii"), region)
    return int(m.group(1)) if m else None


def _object_body(data: bytes, num: int) -> bytes | None:
    pat = re.compile(rb"(?m)^\s*%d\s+\d+\s+obj\b" % num)
    m = pat.search(data)
    if not m:
        return None
    end = data.find(b"endobj", m.end())
    if end < 0:
        return None
    return data[m.end():end]


def _dict_inner(body: bytes) -> bytes | None:
    """取对象体里字典的内部字节（要求整段是 << ... >>）。"""
    start = body.find(b"<<")
    end = body.rfind(b">>")
    if start < 0 or end <= start:
        return None
    return body[start + 2:end]


_PDF_AIGC_RE = re.compile(
    rb"/AIGC\s*(?:\((?:\\\\.|[^\\\\)])*\)|<[0-9A-Fa-f\s]*>)")


def _strip_aigc(inner: bytes) -> bytes:
    return _PDF_AIGC_RE.sub(b" ", inner)


def _max_obj_num(data: bytes) -> int:
    nums = [int(m.group(1))
            for m in re.finditer(rb"(?m)^\s*(\d+)\s+\d+\s+obj\b", data)]
    return max(nums) if nums else 0


def inject_pdf_info(path, json_text) -> None:
    """PDF 增量更新：新 Info 对象保留原键并追加 /AIGC (JSON)。

    - 只支持经典 xref 表（xref 流 → ValueError("xref 流 PDF 写入未支持")）；
    - 原文件字节（含到 %%EOF 的前缀）**完全不变**，只在末尾追加新对象 +
      新 xref + trailer（/Prev 指回旧 xref）/ startxref / %%EOF；
    - 同一 JSON 重复写入为 no-op（不产生多份 AIGC）；不同 JSON 会追加新修订
      （历史修订仍留旧串，属 PDF 增量语义）。
    - 写后 `metadata.extract_json_candidates` 可取回同一 JSON（容器 pdf.info）。
    """
    obj = _check_json_text(json_text)
    data = _read(path)
    if not data.startswith(b"%PDF-"):
        raise ValueError("不是 PDF（缺 %PDF- 头）")
    if b"%%EOF" not in data:
        raise ValueError("PDF 缺 %%EOF（修复指引：确认文件完整）")
    old_xref = _last_startxref(data)
    _classic_xref_guard(data, old_xref)
    region = _trailer_region(data, old_xref)
    root_ref = _ref(region, "Root")
    if root_ref.startswith(b"/Root"):
        root_ref = root_ref[len(b"/Root"):].strip()
    if root_ref is None:
        raise ValueError("PDF trailer 缺 /Root（修复指引：用带 /Root 的完整 PDF）")
    old_info = _object_num(region, "Info")
    old_size_m = re.search(rb"/Size\s+(\d+)", region)
    old_size = int(old_size_m.group(1)) if old_size_m else 0

    pdf_json = _pdf_json_text(obj, json_text)
    literal = _pdf_literal(pdf_json)
    # 幂等：当前修订的 Info 对象里已有同一 /AIGC ⇒ 不重复追加
    if old_info is not None:
        cur = _object_body(data, old_info)
        if cur is not None and literal in cur:
            return

    new_num = max(_max_obj_num(data), old_size - 1) + 1
    if old_info is not None:
        body = _object_body(data, old_info)
        inner = _dict_inner(body) if body is not None else None
        if inner is None:
            raise ValueError("原 Info 对象不是字典（修复指引：手工修正 PDF）")
        inner = _strip_aigc(inner).rstrip()
        dict_body = b"<< " + inner + b" /AIGC " + literal + b" >>"
    else:
        dict_body = b"<< /AIGC " + literal + b" >>"

    base = data if data.endswith(b"\n") else data + b"\n"
    obj_off = len(base)
    new_obj = b"%d 0 obj\n" % new_num + dict_body + b"\nendobj\n"
    xref_off = obj_off + len(new_obj)
    xref = b"xref\n%d 1\n%010d 00000 n \n" % (new_num, obj_off)
    trailer = (b"trailer\n<< /Size %d /Root %s /Info %d 0 R /Prev %d >>\n"
               % (new_num + 1, root_ref, new_num, old_xref))
    tail = b"startxref\n%d\n%%%%EOF\n" % xref_off
    _write(path, base + new_obj + xref + trailer + tail)
