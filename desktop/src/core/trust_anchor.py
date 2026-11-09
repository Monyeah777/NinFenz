"""吊销公钥的**信任锚** v0：固定根 + 委派链（不用证书链，不引 X.509）。

问题（2026-11-07）：ed25519 解决了「给验证能力 ≠ 给伪造能力」，但没解决「这把公钥是谁的」——
攻击者换一把公钥重签 feed，验证方照样验得过。要解决的**最小可证**形态是：
验证方手里钉一份信任清单（roots），组织公钥必须由某个根**签发委派**才能被承认。

为什么不上 X.509/证书链：那需要 CA 基础设施与策略面，本季没有；而「根集合 + 有界委派」在
离线、单组织/联盟场景里已经能挡住「换把公钥就冒充」的攻击，且全部可自证（判据在
desktop/tests/test_trust_anchor.py）。

形状（nf-revocation-trust/1）：
{
  "schema": "nf-revocation-trust/1",
  "roots": [{"id": "root-a", "pub": "<64 hex>"}],
  "delegations": [
    {"issuer": "<64 hex>", "subject": "<64 hex>", "scope": "revocations",
     "expires_at": "2027-01-01T00:00:00Z", "sig": "<128 hex>"}
  ]
}
- 委派签名体 = 规范化 JSON（issuer/subject/scope/expires_at，键排序、紧凑）；确定性签名便于进清单；
- 链条深度上限 **2 级委派**（root → org → team），超过判 invalid——有界比「随便转授」安全；
- expires_at 必须给（UTC 秒级），判定时点默认本机时钟，也可由调用方给（与证据判定同一口径）；
- 只允许 scope="revocations"：这把钥匙不能拿去签别的东西。
"""
from __future__ import annotations

import json
import re
from typing import Any

SCHEMA = "nf-revocation-trust/1"
SCOPE = "revocations"
MAX_DEPTH = 2
GUIDE = "修复指引："
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX128 = re.compile(r"^[0-9a-f]{128}$")
STAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def delegation_body(issuer: str, subject: str, scope: str, expires_at: str) -> bytes:
    return _canon({"issuer": issuer, "subject": subject, "scope": scope,
                   "expires_at": expires_at})


def make_delegation(issuer_seed: bytes, subject_pub: bytes, expires_at: str,
                    scope: str = SCOPE) -> tuple[dict[str, Any], str]:
    """根/中间方签发一条委派（ed25519 签名）→ (委派条目, 空串或错误)。"""
    from core import ed25519
    if scope != SCOPE:
        return {}, (f"委派 scope 只允许 {SCOPE!r}（" + GUIDE + "本季只支持吊销面，别扩域）")
    if not STAMP.match(str(expires_at or "")):
        return {}, ("expires_at 必须是 UTC 秒级 YYYY-MM-DDTHH:MM:SSZ（" + GUIDE
                    + "委派必须有失效期，不允许永久授权）")
    if len(subject_pub) != 32:
        return {}, ("被委派方公钥必须是 32 字节（" + GUIDE + "用 revocations pubkey 导出的公钥）")
    try:
        issuer_pub = ed25519.public_key(issuer_seed)
    except ValueError as exc:
        return {}, str(exc)
    body = delegation_body(issuer_pub.hex(), subject_pub.hex(), scope, expires_at)
    item = {"issuer": issuer_pub.hex(), "subject": subject_pub.hex(), "scope": scope,
            "expires_at": expires_at, "sig": ed25519.sign(issuer_seed, body).hex()}
    return item, ""


def make_manifest(root_pubs: list[bytes],
                  delegations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    roots = [{"id": f"root-{i + 1}", "pub": pub.hex()} for i, pub in enumerate(root_pubs)]
    return {"schema": SCHEMA, "roots": roots, "delegations": list(delegations or [])}


def _shape_issues(manifest: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(manifest, dict) or str(manifest.get("schema") or "") != SCHEMA:
        return ["信任清单 schema 不匹配（" + GUIDE + f"需要 {SCHEMA}）"]
    roots = manifest.get("roots")
    if not isinstance(roots, list) or not roots:
        issues.append("信任清单没有 roots（" + GUIDE + "至少钉一个根公钥，否则什么都证不了）")
    else:
        for item in roots:
            if not isinstance(item, dict) or not HEX64.match(str(item.get("pub") or "")):
                issues.append("root 公钥必须是 64 位十六进制（" + GUIDE
                              + "用 revocations pubkey 导出）")
                break
    dels = manifest.get("delegations")
    if dels is not None and not isinstance(dels, list):
        issues.append("delegations 必须是数组（" + GUIDE + "没有委派就给空数组）")
    return issues


def anchor(manifest: dict[str, Any], pub: bytes, at: str = "") -> dict[str, Any]:
    """把一把 ed25519 公钥解析到信任根 → {ok, root, path, issues, warnings}。"""
    res: dict[str, Any] = {"ok": False, "root": "", "path": [], "issues": [], "warnings": []}
    issues = _shape_issues(manifest)
    if issues:
        res["issues"].extend(issues)
        return res
    if len(pub) != 32:
        res["issues"].append("待锚定公钥必须是 32 字节（" + GUIDE + "别把种子当公钥）")
        return res
    now = at or ""
    roots = {str(r.get("pub")): str(r.get("id")) for r in manifest["roots"]}
    subject = pub.hex()
    if subject in roots:
        res.update({"ok": True, "root": roots[subject], "path": [roots[subject]]})
        return res
    # 广度优先找最短委派链（有界深度）
    frontier = [(subject, [subject])]
    seen = {subject}
    for _depth in range(MAX_DEPTH):
        nxt = []
        for node, path in frontier:
            for item in manifest.get("delegations") or []:
                if not isinstance(item, dict) or str(item.get("subject") or "") != node:
                    continue
                issuer = str(item.get("issuer") or "")
                if issuer in seen:
                    continue
                why = _delegation_issue(item, issuer, node, now)
                if why:
                    res["issues"].append(why)
                    continue
                if issuer in roots:
                    res.update({"ok": True, "root": roots[issuer],
                                "path": [roots[issuer]] + list(reversed(path))})
                    return res
                seen.add(issuer)
                nxt.append((issuer, path + [issuer]))
        frontier = nxt
        if not frontier:
            break
    res["issues"].append("公钥没有被信任根覆盖（" + GUIDE
                         + "该公钥不是 root，也没有到 root 的有效委派——"
                         "换把公钥就能冒充，正是这一层要挡的）")
    return res


def _delegation_issue(item: dict[str, Any], issuer: str, subject: str, at: str) -> str:
    """单条委派的自检 → 空串表示通过。"""
    from core import ed25519
    if str(item.get("scope") or "") != SCOPE:
        return "委派 scope 不匹配（" + GUIDE + f"只允许 {SCOPE}）"
    if not HEX64.match(issuer) or not HEX64.match(subject):
        return "委派公钥不是 64 位十六进制（" + GUIDE + "重签该委派）"
    exp = str(item.get("expires_at") or "")
    if not STAMP.match(exp):
        return "委派缺有效 expires_at（" + GUIDE + "重签并给出失效期）"
    if at and at > exp:
        return f"委派已过期（{exp}）（" + GUIDE + "重新签发委派）"
    sig = str(item.get("sig") or "")
    if not HEX128.match(sig):
        return "委派签名不是 128 位十六进制（" + GUIDE + "重签该委派）"
    body = delegation_body(issuer, subject, str(item.get("scope") or ""), exp)
    if not ed25519.verify(bytes.fromhex(issuer), body, bytes.fromhex(sig)):
        return "委派签名不匹配（" + GUIDE + "内容被改过或签发方不对——两者都不可信）"
    return ""
