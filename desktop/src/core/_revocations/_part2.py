"""core.revocations 私有实现分片 2/2（对外只经 core.revocations 门面导入）：verify、merge"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from typing import Any

from ._part1 import (
    ALG,
    ALG_ED25519,
    FEED_SCHEMA,
    GUIDE,
    TABLE_SCHEMA,
    _shape_issues,
    body,
    canonical_bytes,
    digest,
    freshness,
    make_table,
    table_of,
)


def verify(doc: dict[str, Any], key: bytes | None = None,
           prev: dict[str, Any] | None = None, at: str = "",
           trust: dict[str, Any] | None = None,
           require_trust: bool = False) -> dict[str, Any]:
    """校验 feed（或裸表）→ {ok, verdict, seq, digest, issues, warnings, freshness}。

    口径：签名在就必须过、且必须有密钥（**缺密钥不降级**）；没签名只给 warning
    （形状可判、来源不可判）。
    `prev` 给出时核对「序号 +1 且前序摘要接得上」——这是防回滚/分叉的那一步。
    `at` 只影响 `freshness`（缺省 = 现在），**不参与 verdict**。
    """
    res: dict[str, Any] = {"ok": False, "verdict": "invalid", "seq": None, "digest": "",
                           "issuer": "", "count": 0, "issues": [], "warnings": [],
                           "signed": False, "trust_root": "", "trust_path": [],
                           "freshness": {"state": "unknown", "expires_at": "", "basis": "none"}}
    if not isinstance(doc, dict):
        res["issues"].append("顶层应为对象（" + GUIDE + "给 feed 或 nf-revocation/1 表）")
        return res
    res["freshness"] = freshness(doc, at)
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
    # 可选字段形状（expires_at / ttl / status_uri）：**签名之前**判，坏形状即 invalid
    shape = _shape_issues(doc)
    if shape:
        res["issues"].extend(shape)
        return res
    res["seq"] = seq
    res["issuer"] = str(doc.get("issuer") or "")
    res["count"] = len(rev)
    res["digest"] = digest(doc)
    sig = doc.get("signature")
    if isinstance(sig, dict) and sig:
        res["signed"] = True
        alg = str(sig.get("alg") or "")
        if alg == ALG_ED25519:
            res["scheme"] = ALG_ED25519
            if key is None:
                res["issues"].append("feed 用 ed25519 签名但没给公钥（" + GUIDE +
                                     "缺公钥不降级：--key-file 指 32 字节公钥文件）")
                return res
            if len(key) != 32:
                res["issues"].append(f"ed25519 校验需要 32 字节公钥（{GUIDE}"
                                     f"现在是 {len(key)} 字节——别把种子当公钥给）")
                return res
            from core import ed25519 as _ed
            announced = str(sig.get("pub") or "")
            if announced and announced != key.hex():
                res["issues"].append("feed 声明的公钥与给定公钥不一致（" + GUIDE +
                                     "换密钥必须重签，不能只改声明）")
                return res
            try:
                raw = bytes.fromhex(str(sig.get("sig") or ""))
            except ValueError:
                res["issues"].append("ed25519 签名不是合法十六进制（" + GUIDE + "重签）")
                return res
            if not _ed.verify(key, canonical_bytes(body(doc)), raw):
                res["issues"].append("ed25519 签名不匹配（" + GUIDE +
                                     "内容被改过或公钥不对——两者都不可信）")
                return res
            if trust is None:
                if require_trust:
                    res["issues"].append("要求信任锚但没有给 --trust（" + GUIDE +
                                         "钉一份 trust 清单；不给就等于相信任意一把公钥）")
                    return res
                res["warnings"].append("未给信任锚：签名自洽只证明「同一把公钥签的」，"
                                       "不证明这把公钥属于谁（" + GUIDE +
                                       "用 --trust 钉根公钥 + 委派链）")
            else:
                from core import trust_anchor
                got = trust_anchor.anchor(trust, key, at)
                if not got["ok"]:
                    res["issues"].extend(got["issues"])
                    return res
                res["trust_root"] = got["root"]
                res["trust_path"] = got["path"]
        elif alg == ALG:
            if key is None:
                res["issues"].append("feed 已签名但没给密钥（" + GUIDE +
                                     "缺密钥不降级：请用签发方密钥 --key-file 校验，"
                                     "或只把它当形状核对）")
                return res
            want = hmac.new(key, canonical_bytes(body(doc)), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(want, str(sig.get("mac") or "")):
                res["issues"].append("签名不匹配（" + GUIDE +
                                     "内容被改过或密钥不对——两者都不可信）")
                return res
        else:
            res["issues"].append(f"签名算法不支持：{alg!r}（" + GUIDE +
                                 f"只认 {ALG} 或 {ALG_ED25519}）")
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


def _part_entry(doc: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    """单份 feed → 新鲜度分片（缺省 unknown）。"""
    return {"seq": int(doc.get("seq") or 0),
            "state": (res.get("freshness") or {}).get("state", "unknown")}


def _merge_state(states: list[str]) -> str:
    """多份新鲜度取最严：任一 stale；否则任一 unknown（或空）；否则 fresh。"""
    if "stale" in states:
        return "stale"
    if "unknown" in states or not states:
        return "unknown"
    return "fresh"


def merge(feeds: Sequence[dict[str, Any]], key: bytes | None = None,
          at: str = "") -> dict[str, Any]:
    """多份 feed → 合并后的 `nf-revocation/1` 表（按 seq 排序、逐份验链、取并集）。

    只要有任何一份验不过（签名/序号/前序），整次合并失败——半可信的合并结果比没有更危险。
    新鲜度取各份**最严**（任一 stale → stale；否则任一 unknown → unknown；全 fresh → fresh），
    逐份状态放在 `freshness.parts`；表本身 schema 不变（新鲜度只进输出）。
    """
    rows = sorted(feeds, key=lambda d: int(d.get("seq") or 0))
    issues: list[str] = []
    warnings: list[str] = []
    prev: dict[str, Any] | None = None
    items: list[dict[str, Any]] = []
    parts: list[dict[str, Any]] = []
    for doc in rows:
        res = verify(doc, key=key, prev=prev, at=at)
        issues.extend(res["issues"])
        warnings.extend(res["warnings"])
        parts.append(_part_entry(doc, res))
        if not res["ok"]:
            prev = None
            continue
        table = table_of(doc) or {}
        items.extend(table.get("revoked") or [])
        prev = doc
    merged = make_table(items)
    state = _merge_state([str(p["state"]) for p in parts])
    ok = not issues
    return {"ok": ok, "verdict": "ok" if ok else "invalid", "table": merged,
            "feeds": len(rows), "count": merged["count"], "issues": issues,
            "warnings": warnings, "freshness": {"state": state, "parts": parts}}
