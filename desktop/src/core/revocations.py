"""吊销分发件 v0（G2 的可落地部分）：签名 + 单调序号 + 前序链 + 合并。

背景（`docs/ccos/threat-model.md` G2）：吊销表此前只能「包内嵌」或「侧载原始 JSON」——拿到一份表，
既证明不了**来源**，也防不住**回滚**（攻击者给你一份更早的吊销表，读起来完全合法）。本模块补三件事：

1. `nf-revocation-feed/1`：吊销表外面套一层信封（issuer / seq / prev_digest / hmac 签名）；
2. 校验：签名不过 = 不可信（**缺密钥不降级**）；序号与前序摘要必须接得上（防回滚/防分叉）；
3. 合并：多份 feed 按序号链验完再取并集，输出仍是 `nf-revocation/1` 表（喂给 `--revocations`）。

**边界**：本模块不做分发（没有服务器/订阅），也不解决「签发方撤销了但你没收到」这件事；它只把手头
这份表变成「来源可证、回滚可察」。仍未签名时只给 warning（形状可判、来源不可判）。
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Sequence
from typing import Any

from core import attest

FEED_SCHEMA = "nf-revocation-feed/1"
TABLE_SCHEMA = "nf-revocation/1"
ZERO = "0" * 64
GUIDE = "修复指引："
#: 签名算法（v0 只有一种；不是协商面）
ALG = "hmac-sha256"


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


def sign(table: dict[str, Any], key: bytes, issuer: str = "", seq: int = 1,
         prev: dict[str, Any] | None = None, issued_at: str = "") -> dict[str, Any]:
    """把表包成签名 feed（seq 单调递增；prev 给出上一份 feed 以接链）。"""
    if not isinstance(key, bytes) or not key:
        raise ValueError("签名需要密钥（" + GUIDE + "请用 --key-file 指一个非空密钥文件）")
    if int(seq) < 0:
        raise ValueError("seq 必须是非负整数（" + GUIDE + "首份用 0 或 1，之后逐份 +1）")
    base: dict[str, Any] = {"schema": FEED_SCHEMA, "issuer": issuer or "",
                            "seq": int(seq),
                            "issued_at": issued_at or attest.issue_stamp(),
                            "prev_digest": digest(prev) if isinstance(prev, dict) else ZERO,
                            "table": table}
    mac = hmac.new(key, canonical_bytes(base), hashlib.sha256).hexdigest()
    base["signature"] = {"alg": ALG, "mac": mac}
    return base


def verify(doc: dict[str, Any], key: bytes | None = None,
           prev: dict[str, Any] | None = None) -> dict[str, Any]:
    """校验 feed（或裸表）→ {ok, verdict, seq, digest, issues, warnings}。

    口径：签名在就必须过、且必须有密钥（**缺密钥不降级**）；没签名只给 warning
    （形状可判、来源不可判）。
    `prev` 给出时核对「序号 +1 且前序摘要接得上」——这是防回滚/分叉的那一步。
    """
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "seq": None, "digest": "",
                           "issuer": "", "count": 0, "issues": [], "warnings": [],
                           "signed": False}
    if not isinstance(doc, dict):
        res["issues"].append("顶层应为对象（" + GUIDE + "给 feed 或 nf-revocation/1 表）")
        return res
    schema = str(doc.get("schema") or "")
    if schema == TABLE_SCHEMA:
        table = table_of(doc)
        rev = table.get("revoked") if isinstance(table, dict) else None
        if not isinstance(rev, list):
            res["issues"].append("裸表的 revoked 必须是数组（" + GUIDE + "见 nf-revocation/1）")
            return res
        res["count"] = len(rev)
        res["warnings"].append("未签名：只能判形状，判不了来源与回滚（" + GUIDE + "请用签发方的"
                               "签名 feed 并 nf evidence revocations merge）")
        res["ok"] = True
        res["verdict"] = "ok"
        return res
    if schema != FEED_SCHEMA:
        res["issues"].append(f"schema 不匹配：{schema!r}（" + GUIDE +
                             f"期望 {FEED_SCHEMA} 或 {TABLE_SCHEMA}）")
        return res
    table = table_of(doc)
    if table is None:
        res["issues"].append("缺 table（" + GUIDE +
                             "feed 里要带 nf-revocation/1 表；只放条目不算）")
        return res
    seq = doc.get("seq")
    if not isinstance(seq, int) or seq < 0:
        res["issues"].append("seq 必须是非负整数（" + GUIDE + "签发方按发布顺序 +1）")
        return res
    prev_digest = str(doc.get("prev_digest") or "")
    if len(prev_digest) != 64:
        res["issues"].append("prev_digest 必须是 64 位十六进制（" + GUIDE +
                             "首份用 64 个 0，之后填上一份 feed 的摘要）")
        return res
    rev = table.get("revoked")
    if not isinstance(rev, list) or not all(isinstance(i, dict) for i in rev):
        res["issues"].append("table.revoked 必须是对象数组（" + GUIDE +
                             "每条至少给 digest 或 path）")
        return res
    res["seq"] = seq
    res["issuer"] = str(doc.get("issuer") or "")
    res["count"] = len(rev)
    res["digest"] = digest(doc)
    sig = doc.get("signature")
    if isinstance(sig, dict) and sig:
        res["signed"] = True
        if sig.get("alg") != ALG:
            res["issues"].append(f"签名算法不支持：{sig.get('alg')!r}（" + GUIDE +
                                 f"v0 只认 {ALG}）")
            return res
        if key is None:
            res["issues"].append("feed 已签名但没给密钥（" + GUIDE +
                                 "缺密钥不降级：请用签发方密钥 --key-file 校验，"
                                 "或只把它当形状核对）")
            return res
        want = hmac.new(key, canonical_bytes(body(doc)), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, str(sig.get("mac") or "")):
            res["issues"].append("签名不匹配（" + GUIDE + "内容被改过或密钥不对——两者都不可信）")
            return res
    else:
        res["warnings"].append("feed 未签名：形状可判、来源与防回滚都判不了（" + GUIDE +
                               "要求签发方出签名 feed）")
    if isinstance(prev, dict):
        prev_seq = prev.get("seq")
        if int(seq) != int(prev_seq or 0) + 1:
            res["issues"].append(f"序号不连续：本份 {seq}，上一份 {prev_seq}（" + GUIDE +
                                 "只接受紧接上一份的 +1；跳号可能是丢件或被回滚）")
            return res
        if prev_digest != digest(prev):
            res["issues"].append("前序摘要对不上（" + GUIDE +
                                 "这份 feed 不是接在上一份后面——历史被改写或来自另一条线）")
            return res
    res["ok"] = True
    res["verdict"] = "ok"
    return res


def merge(feeds: Sequence[dict[str, Any]], key: bytes | None = None) -> dict[str, Any]:
    """多份 feed → 合并后的 `nf-revocation/1` 表（按 seq 排序、逐份验链、取并集）。

    只要有任何一份验不过（签名/序号/前序），整次合并失败——半可信的合并结果比没有更危险。
    """
    rows = sorted(feeds, key=lambda d: int(d.get("seq") or 0))
    issues: list[str] = []
    warnings: list[str] = []
    prev: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    for doc in rows:
        res = verify(doc, key=key, prev=prev)
        issues.extend(res["issues"])
        warnings.extend(res["warnings"])
        if not res["ok"]:
            prev = None
            continue
        table = table_of(doc) or {}
        items.extend(table.get("revoked") or [])
        prev = doc
    merged = make_table(items)
    ok = not issues
    return {"ok": ok, "verdict": "ok" if ok else "invalid", "table": merged,
            "feeds": len(rows), "count": merged["count"], "issues": issues,
            "warnings": warnings}
