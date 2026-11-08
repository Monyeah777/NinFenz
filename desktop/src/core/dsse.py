"""DSSE v1.0.2 core primitives: PAE, JSON envelope, and HMAC verification.

Security rules from the specification are enforced here:
- signatures cover PAE(payloadType, serializedPayload), never reserialized JSON;
- standard and URL-safe Base64 are accepted, but malformed/non-canonical forms are not;
- keyid is only a lookup hint and never establishes trust;
- verification returns the exact bytes that were authenticated.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from . import json_doc

ENVELOPE_VERSION = "DSSEv1"
HMAC_SHA256 = "hmac-sha256"
_STD_B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_URL_B64 = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


class DSSEError(ValueError):
    """Invalid DSSE input or failed verification."""


@dataclass(frozen=True)
class Signature:
    keyid: str
    sig: bytes


@dataclass(frozen=True)
class Envelope:
    payload_type: str
    payload: bytes
    signatures: tuple[Signature, ...]


@dataclass(frozen=True)
class VerifiedPayload:
    payload_type: str
    payload: bytes
    accepted_keyids: tuple[str, ...]


def pae(payload_type: str, payload: bytes) -> bytes:
    """Return the exact DSSE v1 Pre-Authentication Encoding bytes."""
    if not isinstance(payload_type, str):
        raise DSSEError("payloadType 必须是字符串（修复指引：传 UTF-8 文本）")
    if not isinstance(payload, bytes):
        raise DSSEError("payload 必须是 bytes（修复指引：先严格解码，再验签）")
    ptype = payload_type.encode("utf-8")
    return (ENVELOPE_VERSION.encode("ascii") + b" " + str(len(ptype)).encode("ascii")
            + b" " + ptype + b" " + str(len(payload)).encode("ascii") + b" " + payload)


def b64encode(value: bytes) -> str:
    """Produce standard padded Base64 (the first representation allowed by DSSE)."""
    if not isinstance(value, bytes):
        raise DSSEError("Base64 输入必须是 bytes（修复指引：先编码为 bytes）")
    return base64.b64encode(value).decode("ascii")


def b64decode(value: str) -> bytes:
    """Strictly decode standard or URL-safe Base64 without accepting mixed alphabets."""
    if not isinstance(value, str):
        raise DSSEError("Base64 字段必须是字符串（修复指引：JSON 中 payload/sig 用字符串）")
    if value == "":
        return b""
    if len(value) % 4:
        raise DSSEError("Base64 缺少合法 padding（修复指引：按 RFC 4648 补齐 '='）")
    standard = _STD_B64.fullmatch(value) is not None
    urlsafe = _URL_B64.fullmatch(value) is not None
    if not (standard or urlsafe):
        raise DSSEError("Base64 含非法字符或混用了标准/URL-safe 字母表"
                        "（修复指引：整段只使用一种字母表）")
    try:
        raw = base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise DSSEError(f"Base64 解码失败：{exc}（修复指引：核对 Base64 与 padding）") from exc
    canonical = b64encode(raw) if standard else base64.urlsafe_b64encode(raw).decode("ascii")
    if value != canonical:
        raise DSSEError("Base64 不是规范表示（修复指引：重新编码，勿依赖非零 pad bits）")
    return raw


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DSSEError(f"JSON 重复键：{key}（修复指引：删除重复键）")
        out[key] = value
    return out


def loads(data: str | bytes) -> Envelope:
    """Parse one DSSE JSON envelope, accepting either Base64 alphabet."""
    try:
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    except UnicodeDecodeError as exc:
        raise DSSEError(f"DSSE envelope 不是 UTF-8：{exc}（修复指引：转为 UTF-8）") from exc
    if not isinstance(text, str):
        raise DSSEError("DSSE envelope 必须是 UTF-8 bytes 或字符串"
                        "（修复指引：传 JSON 文件内容）")
    try:
        doc = json_doc.loads(text, dict, what="DSSE envelope",
                             strict_constants=True, pairs_hook=_strict_pairs)
    except ValueError as exc:
        if isinstance(exc, DSSEError):
            raise
        raise DSSEError(str(exc)) from exc
    return parse(doc)


def parse(doc: dict) -> Envelope:
    """Validate the standard JSON envelope and ignore unknown extension fields."""
    if not isinstance(doc, dict):
        raise DSSEError("DSSE envelope 顶层必须是对象（修复指引：使用标准 JSON Envelope）")
    for key in ("payload", "payloadType", "signatures"):
        if key not in doc:
            raise DSSEError(f"DSSE envelope 缺必填字段 {key}（修复指引：补齐标准字段）")
    payload_type = doc["payloadType"]
    if not isinstance(payload_type, str):
        raise DSSEError("payloadType 必须是字符串（修复指引：使用 MIME type 或 URI）")
    payload = b64decode(doc["payload"])
    rows = doc["signatures"]
    if not isinstance(rows, list):
        raise DSSEError("signatures 必须是数组（修复指引：每条签名包成对象）")
    signatures: list[Signature] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DSSEError(f"signatures[{index}] 必须是对象（修复指引：使用 sig/keyid 对象）")
        if "sig" not in row:
            raise DSSEError(f"signatures[{index}] 缺必填字段 sig（修复指引：补 Base64 签名）")
        keyid = row.get("keyid", "")
        if keyid is None:
            keyid = ""
        if not isinstance(keyid, str):
            raise DSSEError(f"signatures[{index}].keyid 必须是字符串或省略"
                            "（修复指引：keyid 只能是字符串）")
        signatures.append(Signature(keyid=keyid, sig=b64decode(row["sig"])))
    return Envelope(payload_type=payload_type, payload=payload,
                    signatures=tuple(signatures))


def sign(payload_type: str, payload: bytes, key: bytes, keyid: str = "") -> dict:
    """Create a JSON envelope signed with HMAC-SHA256."""
    if not isinstance(payload_type, str) or not payload_type:
        raise DSSEError("payloadType 必须是非空字符串（修复指引：使用 MIME type 或 URI）")
    if not isinstance(payload, bytes):
        raise DSSEError("payload 必须是 bytes（修复指引：先读取原始字节）")
    if not key:
        raise DSSEError("HMAC-SHA256 密钥不能为空（修复指引：--key-file 指向非空密钥）")
    signature = hmac.new(key, pae(payload_type, payload), hashlib.sha256).digest()
    row = {"sig": b64encode(signature)}
    if keyid:
        row["keyid"] = keyid
    return {"payload": b64encode(payload), "payloadType": payload_type,
            "signatures": [row]}


def verify(envelope: Envelope, keys: Mapping[str, bytes], *,
           threshold: int = 1,
           accepted_payload_types: Iterable[str] | None = None) -> VerifiedPayload:
    """Verify at least ``threshold`` unique trusted HMAC keys over the exact PAE bytes."""
    if not isinstance(envelope, Envelope):
        raise DSSEError("verify 需要 parse/loads 后的 Envelope"
                        "（修复指引：先调用 dsse.loads）")
    if threshold < 1:
        raise DSSEError("threshold 必须 ≥ 1（修复指引：多签名阈值至少为 1）")
    if not keys:
        raise DSSEError("至少需要一个受信密钥（修复指引：--key-file）")
    authenticated = pae(envelope.payload_type, envelope.payload)
    accepted: dict[bytes, str] = {}
    for signature in envelope.signatures:
        if len(signature.sig) != hashlib.sha256().digest_size:
            continue
        candidates = list(keys.items())
        if signature.keyid:
            candidates = [(kid, key) for kid, key in candidates if kid == signature.keyid]
        for keyid, key in candidates:
            if not key:
                continue
            expected = hmac.new(key, authenticated, hashlib.sha256).digest()
            if hmac.compare_digest(expected, signature.sig):
                accepted.setdefault(hashlib.sha256(key).digest(), keyid)
        if len(accepted) >= threshold:
            break
    if len(accepted) < threshold:
        raise DSSEError(f"没有达到阈值的有效 DSSE 签名（需要唯一受信密钥 {threshold} 个）"
                        "（修复指引：核对 payloadType、payload、keyid 与受信密钥）")
    if accepted_payload_types is not None:
        supported = set(accepted_payload_types)
        if envelope.payload_type not in supported:
            raise DSSEError(f"payloadType 不受支持：{envelope.payload_type!r}"
                            f"（支持：{sorted(supported)}；修复指引：传预期 payloadType）")
    return VerifiedPayload(payload_type=envelope.payload_type,
                           payload=envelope.payload,
                           accepted_keyids=tuple(accepted.values()))


def verify_json(data: str | bytes, keys: Mapping[str, bytes], *,
                threshold: int = 1,
                accepted_payload_types: Iterable[str] | None = None) -> VerifiedPayload:
    """Parse once and return the exact authenticated payload bytes."""
    return verify(loads(data), keys, threshold=threshold,
                  accepted_payload_types=accepted_payload_types)


def dumps(envelope: dict) -> str:
    """Deterministic JSON representation for distribution and byte comparison."""
    parse(envelope)
    return json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
