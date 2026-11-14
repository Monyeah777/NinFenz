"""nf-public-anchor/1 公共锚（T4）：Rekor 风格公共透明日志条目的离线验证 + 显式联网抓取。

为什么需要它：T4 要求「外部公共锚」，而不是本仓自签自验。公共日志（如 Sigstore Rekor）
提供两样东西：① RFC6962 inclusion proof 把一个条目纳入已发布的 tree root；② 日志对
SET（signed entry timestamp）的签名。本模块离线复算这两者，并强制目标摘要绑定：

- 日志身份必须由调用方**显式钉住**（expected_log_id），不信任条目自述；
- inclusion proof 折叠到 root_hash；SET 由 pinned log public key 验（openssl ECDSA 或注入回调）；
- 目标摘要从 hashedrekord body 的 spec.data.hash.value 提取（或显式 target_digest 字段），
  必须等于被锚对象摘要；
- 抓取（fetch）只在 CLI 显式请求时联网，不把网络依赖塞进判定路径。

边界：本模块验证「公共日志确实收录了该条目且签名有效」；不验证 Rekor 的入口语义/签名者身份
（entry type 语义、Sigstore 身份策略另属 G4/G5），也不因验证通过就声称「内容真实」。
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import subprocess
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import canonical as tc

GUIDE = "修复指引："
SCHEMA = "nf-public-anchor/1"
SCHEMA_REL = "protocol/trust/public-anchor.schema.json"
DEFAULT_REKOR = "https://rekor.sigstore.dev"
REASON_SCHEMA = "PUBLIC-ANCHOR-SCHEMA-INVALID"
REASON_LOG_UNPINNED = "PUBLIC-ANCHOR-LOG-UNPINNED"
REASON_LOG_MISMATCH = "PUBLIC-ANCHOR-LOG-MISMATCH"
REASON_INCLUSION = "PUBLIC-ANCHOR-INCLUSION-INVALID"
REASON_SET = "PUBLIC-ANCHOR-SET-INVALID"
REASON_TARGET_UNBOUND = "PUBLIC-ANCHOR-TARGET-UNBOUND"
REASON_TARGET_MISMATCH = "PUBLIC-ANCHOR-TARGET-MISMATCH"


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 public anchor schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 schema.const）")
    return doc


def load_public_anchor(path: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺 public anchor：{path}（{GUIDE}传 nf-public-anchor/1 JSON）")
    return json_doc.load(target, dict, what="public anchor")


def leaf_hash(body: bytes) -> str:
    """Rekor 叶哈希：sha256(0x00 || body_bytes)。"""
    return hashlib.sha256(b"\x00" + bytes(body)).hexdigest()


def node_hash(left_hex: str, right_hex: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(left_hex)
                          + bytes.fromhex(right_hex)).hexdigest()


def root_from_inclusion(log_index: int, tree_size: int, leaf_hex: str,
                        proof: list) -> str:
    """CT/RFC6962 inclusion proof 折叠（proof 自叶向根）；非法输入抛 ValueError。"""
    if not isinstance(tree_size, int) or tree_size < 1 or not 0 <= log_index < tree_size:
        raise ValueError(f"inclusion 参数越界：index={log_index} size={tree_size}")
    if len(proof) > 64:
        raise ValueError("inclusion proof 深度超过 64")
    fn, sn = log_index, tree_size - 1
    root = leaf_hex
    for step in proof:
        sib = str(step)
        if len(sib) != 64:
            raise ValueError(f"proof 元素不是 64 hex：{sib!r}")
        if fn & 1 or fn == sn:
            root = node_hash(sib, root)
            while fn and not fn & 1:
                fn >>= 1
                sn >>= 1
        else:
            root = node_hash(root, sib)
        fn >>= 1
        sn >>= 1
    if sn != 0:
        raise ValueError("inclusion proof 未折叠到整棵树根（余 sn != 0）")
    return root


def set_payload(doc: dict) -> bytes:
    """SET 签名载荷：canonical({body, integratedTime, logID, logIndex})。

    注：Rekor 官方用 JCS 规范化；本载荷字段为 ASCII/整数，本仓 canonical（键排序+紧凑）与之一致。
    """
    body = {"body": str(doc.get("body_b64")), "integratedTime": int(doc.get("integrated_time")),
            "logID": str(doc.get("log_id")), "logIndex": int(doc.get("log_index"))}
    return tc.canonical_bytes(body)


def _b64d(text: Any, what: str) -> bytes:
    if not isinstance(text, str):
        raise ValueError(f"{what} 必须是 base64 字符串（{GUIDE}检查锚件结构）")
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{what} base64 解码失败：{exc}") from exc


def make_openssl_verifier(pem_path: str) -> Callable[[bytes, bytes], bool]:
    """openssl ECDSA-SHA256 验签回调（Rekor 公共 key 为 ECDSA P-256 PEM）。"""
    pem = Path(pem_path)
    if not pem.is_file():
        raise ValueError(f"缺 log 公钥 PEM：{pem_path}（{GUIDE}先取公共日志 publicKey）")

    def verify(data: bytes, signature: bytes) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "data").write_bytes(data)
            (base / "sig").write_bytes(signature)
            try:
                proc = subprocess.run(
                    ["openssl", "dgst", "-sha256", "-verify", str(pem),
                     "-signature", str(base / "sig"), str(base / "data")],
                    capture_output=True, text=True, encoding="utf-8", timeout=60)
            except (OSError, subprocess.SubprocessError):
                return False
        return proc.returncode == 0 and "Verified OK" in (proc.stdout or "")

    return verify


def _extract_target(body_bytes: bytes) -> str:
    """从 Rekor entry body 提取目标摘要。

    支持 hashedrekord 的 spec.data.hash.value，或顶层 target_digest 字段。
    """
    try:
        body = json_doc.loads(body_bytes.decode("utf-8"), dict, what="Rekor entry body")
    except (UnicodeDecodeError, ValueError):
        return ""
    if isinstance(body, dict) and isinstance(body.get("target_digest"), str):
        return body["target_digest"]
    spec = (body or {}).get("spec") if isinstance(body, dict) else None
    data = (spec or {}).get("data") if isinstance(spec, dict) else None
    hashed = (data or {}).get("hash") if isinstance(data, dict) else None
    value = (hashed or {}).get("value") if isinstance(hashed, dict) else None
    return str(value) if isinstance(value, str) else ""


def verify_public_anchor(doc: Any, verifier: Callable[[bytes, bytes], bool],
                         expected_log_id: str, target_digest: str = "",
                         schema: dict | None = None, root: str = ".",
                         require_target: bool = True) -> dict:
    """离线验证公共锚：结构 → 日志钉住 → inclusion → SET → 目标绑定。"""
    check_schema = schema if schema is not None else load_schema(root)
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        return {"ok": False, "reason": REASON_SCHEMA, "detail": problems[0]}
    if not expected_log_id:
        return {"ok": False, "reason": REASON_LOG_UNPINNED}
    if str(doc.get("log_id")) != str(expected_log_id):
        return {"ok": False, "reason": REASON_LOG_MISMATCH}
    try:
        body = _b64d(doc.get("body_b64"), "body_b64")
        signature = _b64d(doc.get("signed_entry_timestamp"), "signed_entry_timestamp")
    except ValueError as exc:
        return {"ok": False, "reason": REASON_SCHEMA, "detail": str(exc)}
    try:
        root_hash = root_from_inclusion(int(doc.get("log_index")), int(doc.get("tree_size")),
                                        leaf_hash(body), doc.get("inclusion_proof") or [])
    except ValueError as exc:
        return {"ok": False, "reason": REASON_INCLUSION, "detail": str(exc)}
    if root_hash != doc.get("root_hash"):
        return {"ok": False, "reason": REASON_INCLUSION,
                "detail": "折叠根与 root_hash 不符"}
    if not callable(verifier):
        return {"ok": False, "reason": REASON_SET, "detail": "缺 log 验签器"}
    try:
        set_ok = bool(verifier(set_payload(doc), signature))
    except Exception:
        # 静默跳过理由：验签回调异常 = 验签失败（fail-closed），不把异常当通过。
        set_ok = False
    if not set_ok:
        return {"ok": False, "reason": REASON_SET, "detail": "SET 签名校验失败"}
    extracted = str(doc.get("target_digest") or _extract_target(body))
    if not extracted:
        if require_target:
            return {"ok": False, "reason": REASON_TARGET_UNBOUND}
        return {"ok": True, "target_digest": "", "log_id": doc.get("log_id"),
                "tree_size": doc.get("tree_size")}
    if target_digest and extracted != target_digest:
        return {"ok": False, "reason": REASON_TARGET_MISMATCH,
                "detail": f"公共条目绑定 {extracted}，期望 {target_digest}"}
    return {"ok": True, "target_digest": extracted, "log_id": doc.get("log_id"),
            "tree_size": doc.get("tree_size"), "log_index": doc.get("log_index")}


def _http_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "NinFenz-trust/1",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json_doc.loads(resp.read().decode("utf-8"), dict, what="Rekor API")


def fetch_rekor_public_key(base_url: str = DEFAULT_REKOR) -> str:
    """抓取公共日志 publicKey（PEM 文本）。"""
    req = urllib.request.Request(base_url.rstrip("/") + "/api/v1/log/publicKey",
                                 headers={"User-Agent": "NinFenz-trust/1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch_rekor_entry(uuid: str, base_url: str = DEFAULT_REKOR) -> dict:
    """抓取 Rekor 条目并转成 nf-public-anchor/1（联网仅在此函数内发生）。"""
    data = _http_json(base_url.rstrip("/") + "/api/v1/log/entries/" + str(uuid))
    if not isinstance(data, dict) or not data:
        raise ValueError(f"Rekor 响应空/形状异常：{uuid}")
    entry = next(iter(data.values()))
    verification = entry.get("verification") or {}
    proof = verification.get("inclusionProof") or {}
    body_b64 = str(entry.get("body") or "")
    try:
        body = _b64d(body_b64, "body")
    except ValueError as exc:
        raise ValueError(f"Rekor body 不可解码：{exc}") from exc
    doc = {"schema": SCHEMA, "kind": "rekor-entry",
           "log_id": str(entry.get("logID") or ""),
           "log_index": int(proof.get("logIndex") or entry.get("logIndex") or 0),
           "tree_size": int(proof.get("treeSize") or 0),
           "root_hash": str(proof.get("rootHash") or ""),
           "body_b64": body_b64,
           "integrated_time": int(entry.get("integratedTime") or 0),
           "signed_entry_timestamp": str(verification.get("signedEntryTimestamp") or ""),
           "inclusion_proof": [str(h) for h in (proof.get("hashes") or [])],
           "log_url": base_url}
    target = _extract_target(body)
    if target:
        doc["target_digest"] = target
    if not doc["root_hash"] or not doc["tree_size"] or not doc["body_b64"]:
        raise ValueError(f"Rekor 条目缺必要字段：{uuid}（{GUIDE}确认条目已 integrate）")
    return doc
