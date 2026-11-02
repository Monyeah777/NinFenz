"""最小 DER 编解码（X.509 / CMS 子集够用）。

只实现本工具需要的部分：TLV 读写、OID、INTEGER、BIT STRING、时间字符串。
不追求通用 ASN.1 解析器；未知标签按原始字节保留。
"""

from __future__ import annotations

from datetime import datetime, timezone

# 常用标签
SEQUENCE = 0x30
SET = 0x31
INTEGER = 0x02
BITSTRING = 0x03
OCTETSTRING = 0x04
NULL = 0x05
OID = 0x06
UTF8STRING = 0x0C
PRINTABLESTRING = 0x13
IA5STRING = 0x16
UTCTIME = 0x17
GENERALIZEDTIME = 0x18
BOOLEAN = 0x01


def read_tlv(data: bytes, off: int = 0):
    """返回 (tag, value, next_off)。"""
    if off >= len(data):
        raise ValueError("DER 越界")
    tag = data[off]
    off += 1
    if off >= len(data):
        raise ValueError("DER 长度缺失")
    first = data[off]
    off += 1
    if first < 0x80:
        length = first
    else:
        n = first & 0x7F
        if n == 0 or n > 4:
            raise ValueError(f"不支持的 DER 长度形式：{first:#x}")
        if off + n > len(data):
            raise ValueError("DER 长度越界")
        length = int.from_bytes(data[off:off + n], "big")
        off += n
    end = off + length
    if end > len(data):
        raise ValueError("DER 内容越界")
    return tag, data[off:end], end


def parse_sequence(data: bytes):
    """把 SEQUENCE/SET 内容拆成 [(tag, value)]。"""
    out = []
    off = 0
    while off < len(data):
        tag, value, off = read_tlv(data, off)
        out.append((tag, value))
    return out


def decode_oid(data: bytes) -> str:
    if not data:
        raise ValueError("OID 为空")
    first = data[0]
    parts = [first // 40, first % 40]
    val = 0
    for b in data[1:]:
        val = (val << 7) | (b & 0x7F)
        if not b & 0x80:
            parts.append(val)
            val = 0
    return ".".join(str(p) for p in parts)


def encode_oid(text: str) -> bytes:
    parts = [int(p) for p in text.split(".")]
    if len(parts) < 2:
        raise ValueError("OID 至少两段")
    out = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.append((p & 0x7F) | 0x80)
            p >>= 7
        out += bytes(reversed(chunk))
    return out


def decode_int(data: bytes, signed: bool = False) -> int:
    return int.from_bytes(data, "big", signed=signed)


def encode_int(n: int, signed: bool = False) -> bytes:
    if n < 0:
        raise ValueError("只支持非负整数")
    length = max(1, (n.bit_length() + 8) // 8)
    return n.to_bytes(length, "big")


def decode_bitstring(data: bytes):
    """返回 (unused_bits, payload)。"""
    if not data:
        raise ValueError("BIT STRING 为空")
    return data[0], data[1:]


def decode_time(tag: int, data: bytes) -> datetime:
    text = data.decode("ascii")
    if tag == UTCTIME:
        # YYMMDDHHMMSSZ
        yy = int(text[0:2])
        year = 2000 + yy if yy < 50 else 1900 + yy
        rest = text[2:]
        dt = datetime.strptime(rest, "%m%d%H%M%SZ")
        return dt.replace(year=year, tzinfo=timezone.utc)
    if tag == GENERALIZEDTIME:
        base = text.rstrip("Z")
        fmt = "%Y%m%d%H%M%S" if len(base) == 14 else "%Y%m%d%H%M%S.%f"
        return datetime.strptime(base, fmt).replace(tzinfo=timezone.utc)
    raise ValueError(f"不是时间类型：tag={tag:#x}")


# ---------------------------------------------------------------- 编码辅助

def wrap(tag: int, content: bytes) -> bytes:
    n = len(content)
    if n < 0x80:
        return bytes([tag, n]) + content
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(raw)]) + raw + content


def seq(*parts: bytes) -> bytes:
    return wrap(SEQUENCE, b"".join(parts))


def setof(*parts: bytes) -> bytes:
    return wrap(SET, b"".join(parts))


def oid_node(text: str) -> bytes:
    return wrap(OID, encode_oid(text))


def int_node(n: int) -> bytes:
    return wrap(INTEGER, encode_int(n))


def octets(b: bytes) -> bytes:
    return wrap(OCTETSTRING, b)


def utf8(text: str) -> bytes:
    return wrap(UTF8STRING, text.encode("utf-8"))


def bitstring(b: bytes, unused: int = 0) -> bytes:
    return wrap(BITSTRING, bytes([unused]) + b)


def null() -> bytes:
    return b"\x05\x00"
