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
import re
from collections.abc import Iterable, Sequence
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


def _shape_issues(doc: dict[str, Any]) -> list[str]:
    """feed 可选字段的形状判定（在**签名校验之前**跑；返回问题文本，空 = 通过）。"""
    issues: list[str] = []
    exp = doc.get("expires_at")
    if "expires_at" in doc and not (isinstance(exp, str) and STAMP_RE.match(exp)):
        issues.append(f"feed 的 expires_at 形状不对：{exp!r}（" + GUIDE +
                      "UTC 秒级 YYYY-MM-DDTHH:MM:SSZ）")
    if "ttl" in doc and not _valid_ttl(doc.get("ttl")):
        issues.append("feed 的 ttl 必须是正整数秒且 ≤31536000（" + GUIDE +
                      "重签该 feed；不要手工改已签名件）")
    uri = doc.get("status_uri")
    if "status_uri" in doc and not (isinstance(uri, str) and uri.strip()):
        issues.append("feed 的 status_uri 必须是非空字符串（" + GUIDE +
                      "填 URI 形式；本仓不会去取它）")
    issued = doc.get("issued_at")
    if (isinstance(exp, str) and STAMP_RE.match(exp) and isinstance(issued, str)
            and STAMP_RE.match(issued) and exp < issued):
        issues.append("feed 的 expires_at 早于 issued_at（" + GUIDE +
                      "重签；手工改必破签名）")
    return issues


def sign(table: dict[str, Any], key: bytes, issuer: str = "", seq: int = 1,
         prev: dict[str, Any] | None = None, issued_at: str = "",
         expires_at: str = "", ttl: int | None = None,
         status_uri: str = "", scheme: str = ALG) -> dict[str, Any]:
    """把表包成签名 feed（seq 单调递增；prev 给出上一份 feed 以接链）。

    `expires_at` / `ttl` / `status_uri` 是**可选**新鲜度与分发指针字段：只在给出时写入
    （不写 null，免得无谓改变 digest）。签名体仍是「除 signature 外全部字段」，故它们
    自动进签名、改一个字节即破签名；本模块**不**根据 status_uri 联网取任何东西。
    """
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
    stamp = issued_at or attest.issue_stamp()
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
    base: dict[str, Any] = {"schema": FEED_SCHEMA, "issuer": issuer or "",
                            "seq": int(seq),
                            "issued_at": stamp,
                            "prev_digest": digest(prev) if isinstance(prev, dict) else ZERO,
                            "table": table}
    if expires_at:
        base["expires_at"] = str(expires_at)
    if ttl is not None:
        base["ttl"] = int(ttl)
    if status_uri:
        base["status_uri"] = str(status_uri)
    payload = canonical_bytes(base)
    if scheme == ALG_ED25519:
        from core import ed25519 as _ed
        base["signature"] = {"alg": ALG_ED25519, "pub": _ed.public_key(key).hex(),
                             "sig": _ed.sign(key, payload).hex()}
    else:
        mac = hmac.new(key, payload, hashlib.sha256).hexdigest()
        base["signature"] = {"alg": ALG, "mac": mac}
    return base


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
        parts.append({"seq": int(doc.get("seq") or 0),
                      "state": (res.get("freshness") or {}).get("state", "unknown")})
        if not res["ok"]:
            prev = None
            continue
        table = table_of(doc) or {}
        items.extend(table.get("revoked") or [])
        prev = doc
    merged = make_table(items)
    states = [str(p["state"]) for p in parts]
    if "stale" in states:
        state = "stale"
    elif "unknown" in states or not states:
        state = "unknown"
    else:
        state = "fresh"
    ok = not issues
    return {"ok": ok, "verdict": "ok" if ok else "invalid", "table": merged,
            "feeds": len(rows), "count": merged["count"], "issues": issues,
            "warnings": warnings, "freshness": {"state": state, "parts": parts}}
