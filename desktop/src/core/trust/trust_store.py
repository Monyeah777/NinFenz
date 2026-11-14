"""Trust store：policy × issuer registry × type registry 的一致性解析（G2 转入 G4 的收口项）。

为什么需要：verify 之前「policy 说 issuer 在册」与「keys registry 说 key 生命周期」是两套读取；
trust store 把它们**一次装配**成可解析的单一入口，缺一即拒：
- policy.issuers[].id 必须在 issuer registry 存在；
- policy.issuers[].alg 必须与 registry key.alg 一致，且在 policy.algorithms 白名单内；
- keyid 全表唯一（跨 issuer 重复即拒）；
- policy.issuers[].types 必须已在 type registry 注册；
- issuer kind 必须被其类型的 allowed_issuer_kinds 接受。

边界：store 只做「注册面一致性」；签名/生命周期仍在 keys.verify_envelope，准入在 entity。
"""
from __future__ import annotations

from core.trust import keys as tk

GUIDE = "修复指引："
REASON_STORE_INVALID = "TRUST-STORE-INVALID"


def build_store(policy: dict, issuer_registry: dict, type_registry: dict) -> dict:
    """装配 store → {issuers, keyids, types}；不一致即抛（带修复指引）。"""
    issues = build_store_issues(policy, issuer_registry, type_registry)
    if issues:
        raise ValueError(f"{REASON_STORE_INVALID}：{issues[0]}（{GUIDE}修三份注册面）")
    by_issuer = {}
    keyids = {}
    for item in (policy or {}).get("issuers") or []:
        resolved = tk.resolve_issuer(issuer_registry, str(item.get("id")))
        issuer = resolved.get("issuer") or {}
        keys = {str(k.get("keyid")): k for k in issuer.get("keys") or []}
        key = keys[str(item.get("keyid"))]
        if key["keyid"] in keyids:
            raise ValueError(f"keyid 重复：{key['keyid']}（{GUIDE}跨 issuer 不得复用 keyid）")
        keyids[key["keyid"]] = {"issuer_id": issuer["id"], "alg": key["alg"],
                                "kind": issuer.get("kind")}
        by_issuer[str(item.get("id"))] = {"id": issuer["id"], "kind": issuer.get("kind"),
                                          "types": list(item.get("types") or []),
                                          "keyid": key["keyid"]}
    types = {str(t.get("id")): t for t in (type_registry or {}).get("types") or []}
    return {"issuers": by_issuer, "keyids": keyids, "types": types}


def build_store_issues(policy: dict, issuer_registry: dict, type_registry: dict) -> list:
    """不抛的体检版：返回问题清单（空 = 一致）。"""
    issues: list = []
    if not isinstance(policy, dict) or not isinstance(issuer_registry, dict):
        return [f"policy/issuer registry 必须是对象（{GUIDE}按冻结 schema 传）"]
    algorithms = set(policy.get("algorithms") or [])
    types = {str(t.get("id")): t for t in (type_registry or {}).get("types") or []}
    seen_keyids = set()
    for item in policy.get("issuers") or []:
        iid = str(item.get("id"))
        resolved = tk.resolve_issuer(issuer_registry, iid)
        if not resolved.get("ok"):
            issues.append(f"policy issuer 不在 issuer registry：{iid}")
            continue
        issuer = resolved.get("issuer") or {}
        keys = {str(k.get("keyid")): k for k in issuer.get("keys") or []}
        keyid = str(item.get("keyid"))
        key = keys.get(keyid)
        if key is None:
            issues.append(f"policy issuer {iid} 的 keyid 不在 registry：{keyid}")
            continue
        if keyid in seen_keyids:
            issues.append(f"keyid 跨 issuer 重复：{keyid}")
        seen_keyids.add(keyid)
        if item.get("alg") != key.get("alg"):
            issues.append(f"{iid} 的 alg 与 registry key.alg 不一致"
                          f"（policy={item.get('alg')} / registry={key.get('alg')}）")
        if item.get("alg") not in algorithms:
            issues.append(f"{iid} 的 alg 不在 policy.algorithms：{item.get('alg')}")
        for type_id in item.get("types") or []:
            entry = types.get(str(type_id))
            if entry is None:
                issues.append(f"{iid} 声称类型 {type_id} 未在 type registry 注册")
                continue
            if str(issuer.get("kind")) not in (entry.get("allowed_issuer_kinds") or []):
                issues.append(f"issuer kind={issuer.get('kind')} 不被类型 {type_id} 接受")
    return issues


def lookup_keyid(store: dict, keyid: str, now: str | None = None,
                 issuer_registry: dict | None = None) -> dict:
    """按 store 解析 keyid（生命周期复用 keys.resolve_keyid；需 registry 原文）。"""
    if issuer_registry is None:
        return {"ok": False, "reason": "REGISTRY-REQUIRED"}
    resolved = tk.resolve_keyid(issuer_registry, keyid, now)
    if not resolved.get("ok"):
        return {"ok": False, "reason": resolved.get("reason")}
    entry = (store.get("keyids") or {}).get(keyid)
    if entry is None:
        return {"ok": False, "reason": "KEY-NOT-IN-STORE"}
    return {"ok": True, "issuer_id": entry["issuer_id"], "alg": entry["alg"],
            "kind": entry["kind"], "retired": resolved.get("retired", False)}
