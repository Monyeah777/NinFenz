"""nf-issuer-registry/1（ADR-009 准入注册表）：issuer ↔ keyid ↔ alg ↔ 生命周期。

为什么需要它：DSSE 只证「信封 + 签名」，证不了「这个 keyid 现在还算不算数」。本模块把
issuer/keyid 的注册、轮换（retired + rotated_to）与吊销（revoked + revoked_at）接成
fail-closed 判定：未知 issuer/keyid、未来生效、已过期、已吊销一律拒；retired 只用于
**历史验签**（不再新签），且必须给出 rotated_to（轮换不断链）。

边界：本模块判「注册表口径 + 信封签名可验」，不判 issuer 是否可信（那是 trust store /
anchor 的职责，WP-22）；不读私钥、不生成密钥。
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import dsse

GUIDE = "修复指引："
SCHEMA = "nf-issuer-registry/1"
SCHEMA_REL = "protocol/trust/keys.schema.json"
ALGS = dsse.ALGS
STATUSES = ("active", "retired", "revoked")
ISSUER_KINDS = ("human", "service", "ai-agent", "institution")
TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
MAX_ISSUERS = 1024
MAX_KEYS = 64


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 keys schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def load_registry(path: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺 issuer registry：{path}（{GUIDE}传存在且 schema 正确的 JSON）")
    return json_doc.load(target, dict, what="issuer registry")


def _parse_ts(text: Any, where: str, issues: list) -> datetime | None:
    if not isinstance(text, str) or not TIMESTAMP.match(text):
        issues.append(f"{where} 时间必须是 UTC 秒级 ISO-8601（{GUIDE}YYYY-MM-DDTHH:MM:SSZ）")
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        issues.append(f"{where} 时间不可解析：{exc}")
        return None


def validate_registry(doc: Any, schema: dict | None = None,
                      root: str = ".") -> tuple:
    """注册表体检 → (issues, stats)。schema 结构 + 语义（唯一性/生命周期/轮换可寻址）。"""
    issues: list = []
    stats = {"issuers": 0, "keys": 0, "active": 0, "retired": 0, "revoked": 0}
    if schema is None:
        try:
            schema = load_schema(root)
        except ValueError as exc:
            return ([str(exc)], stats)
    problems = json_schema.json_schema_check(doc, schema)
    if problems:
        return ([f"schema：{problems[0]}"], stats)
    issuers = doc.get("issuers") or []
    if len(issuers) > MAX_ISSUERS:
        issues.append(f"issuers 超过上限 {MAX_ISSUERS}（{GUIDE}拆多注册表）")
    seen_issuers: dict = {}
    key_owner: dict = {}
    for index, issuer in enumerate(issuers):
        iid = str(issuer.get("id") or "")
        if iid in seen_issuers:
            issues.append(f"issuers[{index}] id 重复：{iid}（{GUIDE}issuer id 全局唯一）")
        seen_issuers[iid] = issuer
        if issuer.get("kind") not in ISSUER_KINDS:
            issues.append(f"issuers[{index}] kind 越界：{issuer.get('kind')}")
        keys = issuer.get("keys") or []
        if len(keys) > MAX_KEYS:
            issues.append(f"issuers[{index}] keys 超过上限 {MAX_KEYS}")
        stats["issuers"] += 1
        for k_index, key in enumerate(keys):
            where = f"{iid}#keys[{k_index}]"
            kid = str(key.get("keyid") or "")
            if kid in key_owner:
                issues.append(f"{where} keyid 重复：{kid}（{GUIDE}keyid 全表唯一）")
            key_owner[kid] = where
            alg = key.get("alg")
            if alg not in ALGS:
                issues.append(f"{where} alg 越界：{alg!r}")
            status = key.get("status")
            if status not in STATUSES:
                issues.append(f"{where} status 越界：{status!r}")
            start = _parse_ts(key.get("not_before"), f"{where}.not_before", issues)
            end = _parse_ts(key.get("not_after"), f"{where}.not_after", issues)
            if start and end and start > end:
                issues.append(f"{where} not_before 晚于 not_after")
            if status == "active":
                if key.get("revoked_at") or key.get("revocation_reason"):
                    issues.append(f"{where} active key 不得带吊销字段")
                if key.get("rotated_to"):
                    issues.append(f"{where} active key 不得带 rotated_to")
            if status == "retired":
                target = key.get("rotated_to")
                if not target:
                    issues.append(f"{where} retired key 必须给 rotated_to（轮换不断链）")
                elif target == kid:
                    issues.append(f"{where} rotated_to 不得指向自身")
            if status == "revoked":
                if not key.get("revoked_at"):
                    issues.append(f"{where} revoked key 必须给 revoked_at")
                if not str(key.get("revocation_reason") or "").strip():
                    issues.append(f"{where} revoked key 必须给 revocation_reason")
            stats["keys"] += 1
            stats[str(status)] = stats.get(str(status), 0) + 1
    for issuer in issuers:
        ref = issuer.get("delegated_by")
        if ref and ref not in seen_issuers:
            issues.append(f"{issuer.get('id')} delegated_by 指向不存在 issuer：{ref}"
                          f"（{GUIDE}先注册被委派方或删该字段）")
        for key in issuer.get("keys") or []:
            target = key.get("rotated_to")
            if target and target not in key_owner:
                issues.append(f"{issuer.get('id')} 的 rotated_to 指向不存在 keyid：{target}"
                              f"（{GUIDE}补目标 key 或删 rotated_to）")
    return issues, stats


def _index(doc: dict) -> dict:
    index = {}
    for issuer in doc.get("issuers") or []:
        for key in issuer.get("keys") or []:
            index[str(key.get("keyid"))] = (issuer, key)
    return index


def resolve_keyid(doc: dict, keyid: str, now: str | None = None) -> dict:
    """按注册表解析 keyid 的当前可得性（fail-closed）。"""
    issuer, key = _index(doc).get(keyid, (None, None))
    if key is None:
        return {"ok": False, "reason": "KEY-UNKNOWN"}
    if not isinstance(now, str) or not now:
        return {"ok": False, "reason": "NOW-REQUIRED"}
    moment = _parse_ts(now, "now", [])
    if moment is None:
        return {"ok": False, "reason": "NOW-INVALID"}
    start = _parse_ts(key.get("not_before"), "not_before", [])
    end = _parse_ts(key.get("not_after"), "not_after", [])
    if start is None or end is None:
        return {"ok": False, "reason": "KEY-TIME-INVALID"}
    if moment < start:
        return {"ok": False, "reason": "KEY-NOT-YET-VALID",
                "detail": str(key.get("not_before"))}
    if moment > end:
        return {"ok": False, "reason": "KEY-EXPIRED", "detail": str(key.get("not_after"))}
    status = key.get("status")
    if status == "revoked":
        return {"ok": False, "reason": "KEY-REVOKED",
                "detail": str(key.get("revocation_reason") or "")}
    return {"ok": True, "issuer": str(issuer.get("id")), "key": key,
            "retired": status == "retired"}


def resolve_issuer(doc: dict, issuer_id: str) -> dict:
    for issuer in doc.get("issuers") or []:
        if issuer.get("id") == issuer_id:
            return {"ok": True, "issuer": issuer}
    return {"ok": False, "reason": "ISSUER-UNKNOWN"}


def _build_verifier(entry: dict, material: dict) -> dict:
    """material[keyid] = {"hex": ...}（hmac）或 {"verify": callable}（非对称回调）。"""
    item = material.get(str(entry.get("keyid")))
    if not isinstance(item, dict):
        return {"ok": False, "reason": "KEY-MATERIAL-MISSING"}
    alg = entry.get("alg")
    if alg == "hmac-sha256":
        hex_text = str(item.get("hex") or "")
        try:
            key = bytes.fromhex(hex_text)
        except ValueError:
            return {"ok": False, "reason": "KEY-MATERIAL-INVALID"}
        if not key:
            return {"ok": False, "reason": "KEY-MATERIAL-INVALID"}
        return {"ok": True, "alg": alg, "verify": dsse.hmac_verifier(key)}
    verify = item.get("verify")
    if not callable(verify):
        return {"ok": False, "reason": "KEY-MATERIAL-MISSING"}
    return {"ok": True, "alg": alg, "verify": verify}


def verify_envelope(envelope: Any, registry: dict, material: dict,
                    schema: dict | None = None, now: str | None = None) -> dict:
    """注册表口径验信封：生命周期 + 签名一起判（未知/吊销/过期即拒，不降级）。"""
    issues, _stats = validate_registry(registry)
    if issues:
        return {"valid": False, "reason": "REGISTRY-INVALID", "detail": issues[0]}
    if not isinstance(now, str) or not now:
        return {"valid": False, "reason": "NOW-REQUIRED"}
    if not isinstance(envelope, dict):
        return {"valid": False, "reason": "ENVELOPE-NOT-OBJECT"}
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        return {"valid": False, "reason": "SIGNATURES-MISSING"}
    keys, issuers, retired = {}, {}, []
    for item in signatures:
        if not isinstance(item, dict):
            return {"valid": False, "reason": "SIGNATURE-INVALID"}
        keyid = str(item.get("keyid") or "")
        if not keyid:
            return {"valid": False, "reason": "SIGNATURE-INVALID"}
        resolved = resolve_keyid(registry, keyid, now)
        if not resolved["ok"]:
            return {"valid": False, "reason": resolved["reason"], "keyid": keyid,
                    "detail": resolved.get("detail", "")}
        if resolved.get("retired"):
            retired.append(keyid)
        built = _build_verifier(resolved["key"], material)
        if not built["ok"]:
            return {"valid": False, "reason": built["reason"], "keyid": keyid}
        if built["alg"] != resolved["key"].get("alg"):
            return {"valid": False, "reason": "KEY-ALG-MISMATCH", "keyid": keyid}
        keys[keyid] = {"alg": built["alg"], "verify": built["verify"]}
        issuers[keyid] = resolved["issuer"]
    merged = dsse.verify_envelope(envelope, keys, schema)
    if not merged.get("valid"):
        return merged
    merged["issuers"] = issuers
    merged["retired"] = retired
    return merged
