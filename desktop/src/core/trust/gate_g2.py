"""check46（G2 收口）Trust 证据链门禁：DSSE + issuer registry + 链头签名 + 锚 的组合判定。

为什么单列：G1 的 check45 只判 bundle/process/等级；G2 新增了「谁签的、签名是否还算数、
链头/卡/事件语句绑定、外部锚是否绑对对象」——这些判据必须能在一处被机械复算，否则
「签名/锚已接线」只是叙事。本扫描用**固定输入的 in-memory 注册表/密钥材料**（测试用
HMAC key，不是秘密）跑真实模块组合，任何接线断裂/判据弱化即 FAIL。

边界：不联网、不依赖 openssl（TSA 真验在 test_trust_signature / test_trust_anchor_evidence）；
公开密钥算法（ed25519/ecdsa-p256）仍需外部回调，本门禁只验「回调接线与生命周期判定」。
"""
from __future__ import annotations

import copy
from pathlib import Path

from core import json_schema
from core.trust import anchor as ta
from core.trust import bundle as tb
from core.trust import canonical as tc
from core.trust import dsse
from core.trust import signature as tsig
from core.trust import verify as tv

GUIDE = "修复指引："
NOW = "2026-11-14T00:00:00Z"
HMAC_KEY = b"gate46-hmac-key-0123456789abcdef"
KEYID = "nf:gate:hmac:2026"
ISSUER = "nf:gate:issuer"
CLAIMS = [{"id": f"G46-{i:03d}", "type": "evidence",
           "subject_digest": "b" * 64, "payload_digest": "c" * 64} for i in range(3)]


def _registry(status: str = "active", **extra) -> dict:
    key = {"keyid": KEYID, "alg": "hmac-sha256", "status": status,
           "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
    key.update(extra)
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": "service", "keys": [key]}]}


def _material() -> dict:
    return {KEYID: {"hex": HMAC_KEY.hex()}}


def _policy(required: str = "T0") -> dict:
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
            "algorithms": ["hmac-sha256"], "tsa_roots": [], "required_level": required,
            "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}


def _load(root: str, rel: str, issues: list):
    path = Path(root) / rel
    if not path.is_file():
        issues.append(f"缺 {rel}（{GUIDE}先落冻结 schema/向量集）")
        return None
    try:
        return json_schema.__dict__ and __import__("core.json_doc", fromlist=["load"]).load(
            path, dict, what=rel)
    except ValueError as exc:
        issues.append(f"{rel} 不可读：{exc}")
        return None


def _check_schemas(root: str, issues: list, stats: dict) -> dict:
    schemas = {}
    for rel in ("protocol/trust/dsse.schema.json", "protocol/trust/keys.schema.json",
                "protocol/trust/chain-head.schema.json", "protocol/trust/anchor.schema.json",
                "protocol/trust/claim-bundle.schema.json"):
        doc = _load(root, rel, issues)
        if doc is not None:
            schemas[rel] = doc
            stats["schemas"] += 1
    return schemas


def _check_signature(root: str, schemas: dict, issues: list, stats: dict) -> dict | None:
    dsse_schema = schemas.get("protocol/trust/dsse.schema.json")
    head_schema = schemas.get("protocol/trust/chain-head.schema.json")
    bundle = tb.build_bundle("d" * 64, "protocol/trust/claim-bundle.schema.json",
                             copy.deepcopy(CLAIMS))
    digest = tc.digest_of(bundle)
    stats["bundle_digest"] = digest
    signers = [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(HMAC_KEY, data)}]
    envelope = tsig.sign_head("bundle", digest, signers, schema=head_schema, root=root)
    stats["signature_envelope"] = 1
    good = tsig.verify_head(envelope, "bundle", digest, _registry(), _material(),
                            dsse_schema, head_schema, now=NOW, root=root)
    if not good.get("ok"):
        issues.append(f"合法链头签名未通过：{good.get('reason')}（{GUIDE}签名/registry 接线断裂）")
    stats["signature_verified"] = 1 if good.get("ok") else 0
    wrong = tsig.verify_head(envelope, "bundle", "f" * 64, _registry(), _material(),
                             dsse_schema, head_schema, now=NOW, root=root)
    if wrong.get("ok"):
        issues.append(f"错摘要的链头签名未被拒（{GUIDE}语句绑定失效）")
    revoked = _registry(status="revoked", revoked_at=NOW, revocation_reason="gate probe")
    if tsig.verify_head(envelope, "bundle", digest, revoked, _material(),
                        dsse_schema, head_schema, now=NOW, root=root).get("ok"):
        issues.append(f"吊销 key 的签名未被拒（{GUIDE}registry 生命周期未接线）")
    return {"bundle": bundle, "digest": digest, "envelope": envelope}


def _check_anchor(anchor_digest: str, issues: list, stats: dict) -> None:
    try:
        doc = ta.build_anchor_set(anchor_digest, [
            {"kind": "git-commit", "repo": ".", "commit": "0" * 40}])
    except ValueError as exc:
        issues.append(f"锚件构建失败：{exc}")
        return
    verifier = {"git-commit": lambda item, digest: {"ok": True}}
    good = ta.verify_anchor_set(doc, anchor_digest, _policy(), verifier)
    if good["facts"]["public_anchor"] != "none":
        issues.append(f"T4 公共锚被擅自标 ok（{GUIDE}T4 属 G4，未建不得声称）")
    if good["details"][0]["status"] != "ok":
        issues.append(f"锚件核验未走通：{good['details'][0].get('reason')}（{GUIDE}接线断裂）")
    bad = copy.deepcopy(doc)
    bad["target_digest"] = "f" * 64
    bad_result = ta.verify_anchor_set(bad, anchor_digest, _policy(), verifier)
    if bad_result["facts"]["time_token"] != "invalid":
        issues.append(f"错 target 的锚件未被拒（{GUIDE}target_digest 绑定失效）")
    stats["anchors"] = 1


def _check_composition(bundle: dict, envelope: dict, issues: list, stats: dict) -> None:
    for required in ("T0", "T1"):
        result = tv.verify(bundle, _policy(required), ".", head_signature=envelope,
                           registry=_registry(), material=_material(), now=NOW)
        if result["exit_code"] != 0:
            issues.append(f"required={required} 时签名链未达等级：exit={result['exit_code']} "
                          f"{[i['code'] for i in result['report']['issues']]}"
                          f"（{GUIDE}signature 事实未接真）")
            continue
        achieved = result["report"]["level"]["achieved"]
        current = stats.get("achieved", "none")
        current_rank = -1 if current == "none" else tv.LEVELS.index(current)
        if tv.LEVELS.index(achieved) > current_rank:
            stats["achieved"] = achieved
    revoked = _registry(status="revoked", revoked_at=NOW, revocation_reason="gate probe")
    broken = tv.verify(bundle, _policy("T1"), ".", head_signature=envelope,
                       registry=revoked, material=_material(), now=NOW)
    if broken["exit_code"] != 1:
        issues.append(f"吊销 registry 的 T1 验证未判 invalid："
                      f"exit={broken['exit_code']}（{GUIDE}吊销必须 fail-closed）")


def scan(root: str = ".") -> tuple:
    issues: list = []
    stats = {"schemas": 0, "signature_envelope": 0, "signature_verified": 0,
             "anchors": 0, "achieved": "none"}
    schemas = _check_schemas(root, issues, stats)
    if all(rel in schemas for rel in ("protocol/trust/dsse.schema.json",
                                      "protocol/trust/keys.schema.json",
                                      "protocol/trust/chain-head.schema.json",
                                      "protocol/trust/anchor.schema.json")):
        built = _check_signature(root, schemas, issues, stats)
        if built:
            _check_anchor(built["digest"], issues, stats)
            _check_composition(built["bundle"], built["envelope"], issues, stats)
    else:
        issues.append("冻结 schema 不全，G2 组合判据无法复算"
                      f"（{GUIDE}补齐 protocol/trust/*.schema.json）")
    return issues, stats
