"""core.revocations 私有实现分片 1/2（对外只经 core.revocations 门面导入）：FEED_SCHEMA 等"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from core import attest, iso8601

FEED_SCHEMA = "nf-revocation-feed/1"


TABLE_SCHEMA = "nf-revocation/1"


ZERO = "0" * 64


GUIDE = "修复指引："


#: 签名算法（v0 只有一种；不是协商面）
ALG = "hmac-sha256"


#: 非对称方案：跨组织时验证方只持公钥，不因此获得伪造能力。
ALG_ED25519 = "ed25519"


#: ttl 上限（1 年）：比这更长就不是「缓存窗口」，而是「永不过期」的伪装
MAX_TTL = 31536000


#: 新鲜度词表（只进输出，不进四词判定；严格开关才升级成 invalid）
FRESH = ("fresh", "stale", "unknown")


#: 有效期时间戳口径（UTC 秒级；与 attest.issue_stamp 同形，可直接字典序比）
STAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"


STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def canonical_bytes(obj: Any) -> bytes:
    """规范化编码（与证据线同源：attest.canonical）。"""
    return attest.canonical(obj)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table_of(doc: dict[str, Any]) -> dict[str, Any] | None:
    """从 table 或 feed 里取出 nf-revocation/1 表（不是则 None）。"""
    if not isinstance(doc, dict):
        return None
    if str(doc.get("schema") or "") == TABLE_SCHEMA:
        return doc
    if str(doc.get("schema") or "") == FEED_SCHEMA:
        table = doc.get("table")
        if isinstance(table, dict) and str(table.get("schema") or "") == TABLE_SCHEMA:
            return table
    return None


def body(doc: dict[str, Any]) -> dict[str, Any]:
    """feed 的签名体 = 除 signature 之外的全部字段（排序后规范化）。"""
    return {k: v for k, v in doc.items() if k != "signature"}


def digest(doc: dict[str, Any]) -> str:
    """feed 摘要（对签名体求）——前序链与合并判据都用它。"""
    return _sha256_hex(canonical_bytes(body(doc)))


def make_table(revoked: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """把条目集合规整成 nf-revocation/1 表（按摘要/路径去重排序，确定性合并用）。"""
    seen: dict[str, dict[str, Any]] = {}
    for item in revoked:
        if not isinstance(item, dict):
            continue
        key = str(item.get("digest") or item.get("path") or "")
        if not key:
            continue
        if key not in seen:
            seen[key] = item
    ordered = [seen[k] for k in sorted(seen)]
    return {"schema": TABLE_SCHEMA, "revoked": ordered, "count": len(ordered)}


def _valid_ttl(value: Any) -> bool:
    """ttl 口径：正整数秒且 ≤ 1 年（bool 是 int 子类，显式排除）。"""
    return (isinstance(value, int) and not isinstance(value, bool)
            and 0 < value <= MAX_TTL)


def _expiry_of(doc: dict[str, Any]) -> tuple[str, str]:
    """→ (生效到期时刻, basis)；没给有效期 → ("", "none")。

    `expires_at` 在场就以它为准；否则 `issued_at + ttl`（解析后加秒，避免手工算日期）。
    """
    exp = doc.get("expires_at")
    if isinstance(exp, str) and STAMP_RE.match(exp):
        return exp, "expires_at"
    ttl = doc.get("ttl")
    issued = doc.get("issued_at")
    if _valid_ttl(ttl) and isinstance(issued, str):
        start = iso8601.parse_instant(issued)
        if start is not None:
            return (start + timedelta(seconds=ttl)).strftime(STAMP_FMT), "ttl"
    return "", "none"


def freshness(doc: dict[str, Any], at: str = "") -> dict[str, Any]:
    """吊销件新鲜度 → {state: fresh|stale|unknown, expires_at, basis}。

    **只输出，不参与判定**（判定只在 evidence 的严格开关下升级）。裸表没有信封可读有效期
    → unknown；旧 feed 没给 `expires_at`/`ttl` 也 → unknown（不因此判死）。
    """
    exp, basis = ("", "none")
    if isinstance(doc, dict) and str(doc.get("schema") or "") == FEED_SCHEMA:
        exp, basis = _expiry_of(doc)
    if not exp:
        return {"state": "unknown", "expires_at": "", "basis": "none"}
    now = at or attest.issue_stamp()
    return {"state": "fresh" if now <= exp else "stale", "expires_at": exp, "basis": basis}


def _expires_issue(doc: dict[str, Any]) -> str:
    """expires_at 形状判定（可选字段；空串=通过）。"""
    exp = doc.get("expires_at")
    if "expires_at" in doc and not (isinstance(exp, str) and STAMP_RE.match(exp)):
        return (f"feed 的 expires_at 形状不对：{exp!r}（" + GUIDE +
                "UTC 秒级 YYYY-MM-DDTHH:MM:SSZ）")
    return ""


def _ttl_issue(doc: dict[str, Any]) -> str:
    """ttl 形状判定（可选字段；空串=通过）。"""
    if "ttl" in doc and not _valid_ttl(doc.get("ttl")):
        return ("feed 的 ttl 必须是正整数秒且 ≤31536000（" + GUIDE +
                "重签该 feed；不要手工改已签名件）")
    return ""


def _status_uri_issue(doc: dict[str, Any]) -> str:
    """status_uri 形状判定（可选字段；空串=通过）。"""
    uri = doc.get("status_uri")
    if "status_uri" in doc and not (isinstance(uri, str) and uri.strip()):
        return ("feed 的 status_uri 必须是非空字符串（" + GUIDE +
                "填 URI 形式；本仓不会去取它）")
    return ""


def _order_issue(doc: dict[str, Any]) -> str:
    """expires_at 早于 issued_at 判定（空串=通过）。"""
    exp = doc.get("expires_at")
    issued = doc.get("issued_at")
    if (isinstance(exp, str) and STAMP_RE.match(exp) and isinstance(issued, str)
            and STAMP_RE.match(issued) and exp < issued):
        return ("feed 的 expires_at 早于 issued_at（" + GUIDE +
                "重签；手工改必破签名）")
    return ""


def _shape_issues(doc: dict[str, Any]) -> list[str]:
    """feed 可选字段的形状判定（在**签名校验之前**跑；返回问题文本，空 = 通过）。"""
    issues: list[str] = []
    for check in (_expires_issue, _ttl_issue, _status_uri_issue, _order_issue):
        msg = check(doc)
        if msg:
            issues.append(msg)
    return issues


@dataclass(frozen=True)
class SignOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    issuer: str = ''
    seq: int = 1
    prev: dict[str, Any] | None = None
    issued_at: str = ''
    expires_at: str = ''
    ttl: int | None = None
    status_uri: str = ''
    scheme: str = ALG


def sign(table: dict[str, Any], key: bytes, opts: SignOptions | None = None) -> dict[str, Any]:
    """把表包成签名 feed（seq 单调递增；prev 给出上一份 feed 以接链）。

    `expires_at` / `ttl` / `status_uri` 是**可选**新鲜度与分发指针字段：只在给出时写入
    （不写 null，免得无谓改变 digest）。签名体仍是「除 signature 外全部字段」，故它们
    自动进签名、改一个字节即破签名；本模块**不**根据 status_uri 联网取任何东西。
    """
    opts = opts if opts is not None else SignOptions()
    scheme = opts.scheme
    _validate_sign_inputs(key, scheme, opts.seq)
    stamp = opts.issued_at or attest.issue_stamp()
    _validate_feed_opts(opts.expires_at, opts.ttl, opts.status_uri, stamp)
    base: dict[str, Any] = {"schema": FEED_SCHEMA, "issuer": opts.issuer or "",
                            "seq": int(opts.seq),
                            "issued_at": stamp,
                            "prev_digest": digest(opts.prev) if isinstance(opts.prev, dict) else ZERO,
                            "table": table}
    _optional_fields(base, opts.expires_at, opts.ttl, opts.status_uri)
    _attach_signature(base, canonical_bytes(base), key, scheme)
    return base


def _validate_sign_inputs(key: bytes, scheme: str, seq: int) -> None:
    """密钥/方案/序号的前置校验（不符 → ValueError）。"""
    if not isinstance(key, bytes) or not key:
        raise ValueError("签名需要密钥（" + GUIDE + "请用 --key-file 指一个非空密钥文件）")
    if scheme not in (ALG, ALG_ED25519):
        raise ValueError(f"签名方案不支持：{scheme!r}（" + GUIDE +
                         f"只支持 {ALG} 或 {ALG_ED25519}）")
    if scheme == ALG_ED25519 and len(key) != 32:
        raise ValueError("Ed25519 签名需要 32 字节种子（" + GUIDE +
                         "用 openssl rand -out seed.bin 32 生成；公钥用 nf evidence "
                         "revocations pubkey 导出）")
    if int(seq) < 0:
        raise ValueError("seq 必须是非负整数（" + GUIDE + "首份用 0 或 1，之后逐份 +1）")


def _validate_feed_opts(expires_at, ttl, status_uri, stamp: str) -> None:
    """可选新鲜度字段的形状校验（不符 → ValueError）。"""
    if expires_at:
        if not STAMP_RE.match(str(expires_at)):
            raise ValueError("--expires-at 必须是 UTC 秒级 YYYY-MM-DDTHH:MM:SSZ（" + GUIDE +
                             "先换算成 UTC；格式与 nf attest 的 issued_at 同源）")
        if str(expires_at) < stamp:
            raise ValueError("--expires-at 早于 issued_at（" + GUIDE +
                             "有效期必须晚于签发时刻；或改用 --ttl）")
    if ttl is not None and not _valid_ttl(ttl):
        raise ValueError("--ttl 必须是正整数秒且 ≤31536000（" + GUIDE +
                         "给整数秒，例如 --ttl 86400）")
    if status_uri and not (isinstance(status_uri, str) and status_uri.strip()):
        raise ValueError("feed 的 status_uri 必须是非空字符串（" + GUIDE +
                         "填 URI 形式；本仓不会去取它）")


def _optional_fields(base: dict[str, Any], expires_at, ttl, status_uri) -> None:
    """可选字段只在给出时写入（不写 null）。"""
    if expires_at:
        base["expires_at"] = str(expires_at)
    if ttl is not None:
        base["ttl"] = int(ttl)
    if status_uri:
        base["status_uri"] = str(status_uri)


def _attach_signature(base: dict[str, Any], payload: bytes, key: bytes,
                      scheme: str) -> None:
    """按方案附 signature（ed25519 或 hmac-sha256）。"""
    if scheme == ALG_ED25519:
        from core import ed25519 as _ed
        base["signature"] = {"alg": ALG_ED25519, "pub": _ed.public_key(key).hex(),
                             "sig": _ed.sign(key, payload).hex()}
    else:
        mac = hmac.new(key, payload, hashlib.sha256).hexdigest()
        base["signature"] = {"alg": ALG, "mac": mac}
