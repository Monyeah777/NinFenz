"""nf-dsse/1 签名信封（FR-A3-01）：PAE 预认证编码 + 信封签名/验签。

冻结依据：ADR-005 与向量集 pae 族（results/trust/trust_vectors.json）。

规则：
- PAE：`DSSEv1 <len(ptype)> <ptype> <len(payload)> <payload>`，长度一律**按字节**；
- 信封：`nf-dsse/1`（payloadType / payload(base64) / signatures[{keyid,sig,alg?}]），至少 1 个签名；
- 算法白名单：hmac-sha256（stdlib 原生）/ ed25519 / ecdsa-p256（**可插拔**：本仓 core 不引
  第三方加密库，调用方传 signer/verifier 回调，算法仍受白名单约束）；
- 验签 fail-closed：trusted keyid 的签名必须验过（不过即 invalid，不降级）；未知 keyid 记为
  untrusted 并跳过，但最终必须有 ≥1 个 trusted-valid 签名；算法越界/与 key 注册算法不符即拒。

边界：本模块只证「信封与载荷一致、签名可验」；issuer/密钥注册、轮换与吊销接线在 WP-21。
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import json_doc, json_schema

GUIDE = "修复指引："
SCHEMA = "nf-dsse/1"
SCHEMA_REL = "protocol/trust/dsse.schema.json"
ALGS = ("hmac-sha256", "ed25519", "ecdsa-p256")
MAX_SIGNATURES = 64


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    """读冻结的 dsse schema（缺件/坏 JSON 直接抛，不静默降级）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 dsse schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def pae(payload_type: bytes, payload: bytes) -> bytes:
    """DSSE 预认证编码（Pre-Authentication Encoding）；空 payloadType 即拒。"""
    if not isinstance(payload_type, (bytes, bytearray)) or not payload_type:
        raise ValueError(f"PAE-EMPTY-TYPE：payloadType 必须是非空 bytes"
                         f"（{GUIDE}形如 application/vnd.nf.*）")
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError(f"PAE-PAYLOAD-NOT-BYTES：payload 必须是 bytes"
                         f"（{GUIDE}先编码成字节再签）")
    return (b"DSSEv1 " + str(len(payload_type)).encode() + b" " + bytes(payload_type)
            + b" " + str(len(payload)).encode() + b" " + bytes(payload))


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: Any) -> bytes:
    if not isinstance(text, str):
        raise ValueError(f"base64 字段必须是字符串（{GUIDE}检查信封结构）")
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"base64 解码失败：{exc}（{GUIDE}用严格 base64 重签）") from exc


def build_envelope(payload_type: str, payload: bytes, signatures: list) -> dict:
    """组装信封（调用方给已签好的 signatures）；结构不做静默修正。"""
    if not isinstance(payload_type, str) or not payload_type:
        raise ValueError(f"payloadType 必须是非空字符串（{GUIDE}见 nf-dsse/1）")
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError(f"payload 必须是 bytes（{GUIDE}先编码成字节）")
    if not isinstance(signatures, list) or not signatures:
        raise ValueError(f"signatures 至少 1 条（{GUIDE}无签名信封不得产出）")
    if len(signatures) > MAX_SIGNATURES:
        raise ValueError(f"signatures 超过上限 {MAX_SIGNATURES}（{GUIDE}拆批签或减签）")
    return {"schema": SCHEMA, "payloadType": payload_type, "payload": _b64e(bytes(payload)),
            "signatures": signatures}


def sign_envelope(payload_type: str, payload: bytes, signers: list) -> dict:
    """签一封：signers = [{keyid, alg?, sign(data)->bytes}]；sig 以严格 base64 入信封。"""
    data = pae(payload_type.encode() if isinstance(payload_type, str) else payload_type,
               payload)
    signatures = []
    for signer in signers:
        if not isinstance(signer, dict) or not str(signer.get("keyid") or ""):
            raise ValueError(f"signer 必须是 {{keyid, sign}}（{GUIDE}补 keyid）")
        alg = str(signer.get("alg") or "hmac-sha256")
        if alg not in ALGS:
            raise ValueError(f"算法 {alg!r} 不在白名单 {ALGS}（{GUIDE}换白名单算法）")
        raw = signer["sign"](data)
        if not isinstance(raw, (bytes, bytearray)):
            raise ValueError(f"signer 必须返回 bytes（{GUIDE}不要直接返回已编码字符串）")
        signatures.append({"keyid": str(signer["keyid"]), "sig": _b64e(bytes(raw)), "alg": alg})
    return build_envelope(payload_type, payload, signatures)


def hmac_sign(key: bytes, data: bytes) -> bytes:
    """stdlib HMAC-SHA256 签名器（可作 signer["sign"] 直接传）。"""
    if not isinstance(key, (bytes, bytearray)) or not key:
        raise ValueError(f"HMAC key 必须是非空 bytes（{GUIDE}测试/演示用固定 key）")
    return hmac.new(bytes(key), bytes(data), hashlib.sha256).digest()


def hmac_verifier(key: bytes) -> Callable[[bytes, bytes], bool]:
    """返回 HMAC 验签回调（constant-time 比较）。"""
    if not isinstance(key, (bytes, bytearray)) or not key:
        raise ValueError(f"HMAC key 必须是非空 bytes（{GUIDE}验签方与签名方同 key）")

    def verify(data: bytes, signature: bytes) -> bool:
        return hmac.compare_digest(hmac_sign(bytes(key), data), bytes(signature))

    return verify


def verify_envelope(envelope: Any, keys: dict, schema: dict | None = None) -> dict:
    """验信封：返回 {valid, reason?, payload_type?, payload?, signers?, untrusted?}。

    keys = {keyid: {"alg": 白名单算法, "verify": callable(pae_bytes, sig_bytes)->bool}}。
    trusted keyid 的签名任一失败即 invalid（fail-closed）；未知 keyid 不算 valid 依据。
    """
    if schema is not None:
        problems = json_schema.json_schema_check(envelope, schema)
        if problems:
            return {"valid": False, "reason": "SCHEMA-INVALID", "detail": problems[0]}
    if not isinstance(envelope, dict):
        return {"valid": False, "reason": "ENVELOPE-NOT-OBJECT"}
    payload_type = envelope.get("payloadType")
    if not isinstance(payload_type, str) or not payload_type:
        return {"valid": False, "reason": "PAYLOAD-TYPE-INVALID"}
    try:
        payload = _b64d(envelope.get("payload"))
    except ValueError:
        return {"valid": False, "reason": "PAYLOAD-B64-INVALID"}
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return {"valid": False, "reason": "SIGNATURES-MISSING"}
    if len(signatures) > MAX_SIGNATURES:
        return {"valid": False, "reason": "SIGNATURES-TOO-MANY"}
    data = pae(payload_type.encode(), payload)
    signers, untrusted = [], []
    for item in signatures:
        if not isinstance(item, dict) or not str(item.get("keyid") or ""):
            return {"valid": False, "reason": "SIGNATURE-INVALID"}
        keyid = str(item["keyid"])
        key = (keys or {}).get(keyid)
        if not isinstance(key, dict):
            untrusted.append(keyid)
            continue
        key_alg = str(key.get("alg") or "")
        if key_alg not in ALGS:
            return {"valid": False, "reason": "ALG-UNSUPPORTED"}
        sig_alg = str(item.get("alg") or key_alg)
        if sig_alg != key_alg:
            return {"valid": False, "reason": "ALG-MISMATCH"}
        try:
            signature = _b64d(item.get("sig"))
        except ValueError:
            return {"valid": False, "reason": "SIGNATURE-B64-INVALID"}
        verify = key.get("verify")
        if not callable(verify):
            return {"valid": False, "reason": "VERIFIER-MISSING"}
        try:
            ok = bool(verify(data, signature))
        except Exception:
            # 静默跳过理由：验签回调异常 = 验签失败（fail-closed），绝不把异常当通过。
            ok = False
        if not ok:
            return {"valid": False, "reason": "SIGNATURE-INVALID"}
        signers.append(keyid)
    if not signers:
        return {"valid": False, "reason": "NO-VALID-SIGNATURE"}
    return {"valid": True, "payload_type": payload_type, "payload": payload,
            "signers": signers, "untrusted": untrusted}
