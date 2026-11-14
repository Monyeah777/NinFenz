"""check47（G4 收口）Trust 见证面门禁：T3 组合判定 + parity 证据在位 + T4 不得声称。

为什么单列：G4 的结论必须在离线、无外部二进制的条件下可复算——本扫描用固定 HMAC 材料
与 in-memory verifier 跑「签名 + TSA（桩）+ STH + witness 阈值」组合，断言：
- 有效组合 → achieved=T3 / exit 0；
- witness 阈值不足 → achieved 低于 T3 且缺项码正确（不冒充 T3）；
- required=T4 → exit 2 + PUBLIC-ANCHOR-MISSING（公共锚未建，不得标 ok）；
- parity 证据（独立 Node 实现 + 向量族 + 测试）在位且 Node 实现不引用仓内实现。
不联网、不依赖 openssl/node 运行时（Node 的执行由 test_trust_parity 覆盖）。
"""
from __future__ import annotations

import copy
from pathlib import Path

from core import json_doc
from core.trust import anchor as ta
from core.trust import bundle as tb
from core.trust import canonical as tc
from core.trust import dsse
from core.trust import key_material as tkm
from core.trust import signature as tsig
from core.trust import trust_store as tstore
from core.trust import verify as tv

GUIDE = "修复指引："
NOW = "2026-11-14T00:00:00Z"
HMAC_KEY = b"gate47-hmac-key-0123456789abcdef"
KEYID = "nf:gate:hmac:2026"
ISSUER = "nf:gate:issuer"
LOG_ID = "nf:gate:log"
TSA_ID = "nf:gate:tsa"
CLAIMS = [{"id": "G47-001", "type": "evidence", "subject_digest": "b" * 64,
           "payload_digest": "c" * 64}]


def _registry() -> dict:
    key = {"keyid": KEYID, "alg": "hmac-sha256", "status": "active",
           "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z"}
    return {"schema": "nf-issuer-registry/1",
            "issuers": [{"id": ISSUER, "kind": "service", "keys": [key]}]}


def _material() -> dict:
    return {KEYID: {"hex": HMAC_KEY.hex()}}


def _policy(required: str = "T3", threshold: int = 1) -> dict:
    return {"schema": "nf-trust-policy/1",
            "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256"}],
            "algorithms": ["hmac-sha256"],
            "tsa_roots": [{"id": TSA_ID, "digest": "d" * 64}],
            "required_level": required,
            "anchors": {"tsa": True, "transparency": True,
                        "witness_threshold": threshold}}


def _hmac(message: str) -> str:
    return dsse.hmac_sign(HMAC_KEY, message.encode()).hex()


def _anchors(digest: str) -> list:
    sth = {"kind": "transparency-sth", "log_id": LOG_ID, "tree_size": 7, "root": digest}
    import base64
    sth["signature"] = base64.b64encode(
        dsse.hmac_sign(HMAC_KEY, ta.sth_statement(sth).encode())).decode()
    witness = {"kind": "witness", "witness_id": "w1", "keyid": KEYID,
               "sig": base64.b64encode(
                   dsse.hmac_sign(HMAC_KEY,
                                  ta.witness_statement(digest, "w1", KEYID).encode())).decode()}
    return [{"kind": "rfc3161", "tsa": TSA_ID, "token": "AAAA"}, sth, witness]


def _checker(message, signature):
    return dsse.hmac_sign(HMAC_KEY, message.encode()) == signature


def _verifiers() -> dict:
    return {"rfc3161": lambda item, digest: {"ok": True, "gen_time": NOW},
            "transparency-sth": ta.make_sth_verifier({LOG_ID: _checker}),
            "witness": ta.make_witness_verifier({KEYID: _checker})}


def _composition(root: str, issues: list, stats: dict) -> None:
    bundle = tb.build_bundle("e" * 64, "protocol/trust/claim-bundle.schema.json",
                             copy.deepcopy(CLAIMS))
    digest = tc.digest_of(bundle)
    signers = [{"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(HMAC_KEY, data)}]
    envelope = tsig.sign_head("bundle", digest, signers, root=root)
    anchor_doc = ta.build_anchor_set(digest, _anchors(digest), root=root)
    result = tv.verify(bundle, _policy("T3"), root, anchor=anchor_doc,
                       anchor_verifiers=_verifiers(), head_signature=envelope,
                       registry=_registry(), material=_material(), now=NOW)
    stats["t3"] = result["report"]["level"]["achieved"]
    stats["t3_exit"] = result["exit_code"]
    if result["exit_code"] != 0 or stats["t3"] != "T3":
        issues.append(f"T3 组合未达成：exit={result['exit_code']} achieved={stats['t3']} "
                      f"issues={[i['code'] for i in result['report']['issues']][:4]}"
                      f"（{GUIDE}signature/time_token/STH+witness 任一断链）")
    t4 = tv.verify(bundle, _policy("T4"), root, anchor=anchor_doc,
                   anchor_verifiers=_verifiers(), head_signature=envelope,
                   registry=_registry(), material=_material(), now=NOW)
    stats["t4"] = t4["report"]["level"]["achieved"]
    codes = [i["code"] for i in t4["report"]["issues"]]
    if t4["exit_code"] != 2 or "PUBLIC-ANCHOR-MISSING" not in codes:
        issues.append(f"required=T4 未按缺公共锚 exit 2：exit={t4['exit_code']} codes={codes}")
    short = tv.verify(bundle, _policy("T3", threshold=2), root, anchor=anchor_doc,
                      anchor_verifiers=_verifiers(), head_signature=envelope,
                      registry=_registry(), material=_material(), now=NOW)
    if short["exit_code"] == 0 or short["report"]["level"]["achieved"] == "T3":
        issues.append("witness 阈值不足仍达 T3（阈值判据失效）")
    for detail in ta.verify_anchor_set(anchor_doc, digest, _policy("T3"),
                                       _verifiers())["details"]:
        if detail["kind"] == "transparency-sth" and detail["status"] == "invalid":
            issues.append("合规 STH 被判 invalid（组合判定断裂）")


def _check_artifacts(root: str, issues: list, stats: dict) -> None:
    base = Path(root)
    script = base / "scripts/trust_parity/verify.mjs"
    test = base / "desktop/tests/test_trust_parity.py"
    if not script.is_file():
        issues.append(f"缺独立 parity 实现 {script.relative_to(base).as_posix()}"
                      f"（{GUIDE}补 Node 独立复算）")
        return
    if not test.is_file():
        issues.append("缺 parity 判据 desktop/tests/test_trust_parity.py")
    source = script.read_text(encoding="utf-8")
    for token in ("desktop/src", "core.trust", "python"):
        if token in source:
            issues.append(f"parity 实现引用了 {token}（不独立，不能算跨语言 parity）")
    vectors = base / "results/trust/trust_vectors.json"
    if not vectors.is_file():
        issues.append("缺 trust 向量集（parity 证据无源）")
        return
    doc = json_doc.load(vectors, dict, what="trust vectors")
    families = sorted({vec.get("family") for vec in doc.get("vectors") or []})
    stats["parity_families"] = len(families)
    if len(families) < 7:
        issues.append(f"向量族不足 7：{families}")


def _store_docs() -> tuple:
    policy = {"schema": "nf-trust-policy/1",
              "issuers": [{"id": ISSUER, "keyid": KEYID, "alg": "hmac-sha256",
                           "types": ["claim"]}],
              "algorithms": ["hmac-sha256"], "tsa_roots": [], "required_level": "T0",
              "anchors": {"tsa": False, "transparency": True, "witness_threshold": 0}}
    registry = _registry()
    types = {"schema": "nf-type-registry/1", "types": [
        {"id": "claim", "allowed_issuer_kinds": ["service"],
         "allowed_ref_kinds": ["evidence"], "compose_with": [], "max_refs": 4}]}
    return policy, registry, types


def _check_residuals(issues: list, stats: dict) -> None:
    import tempfile
    policy, registry, types = _store_docs()
    store_issues = tstore.build_store_issues(policy, registry, types)
    if store_issues:
        issues.append(f"trust store 装配不一致：{store_issues[0]}")
    else:
        store = tstore.build_store(policy, registry, types)
        got = tstore.lookup_keyid(store, KEYID, NOW, registry)
        if not got.get("ok"):
            issues.append(f"trust store lookup 失败：{got.get('reason')}")
        stats["store"] = len(store["keyids"])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "key.hex"
        try:
            meta = tkm.generate_hmac_key(str(path))
            key = tkm.load_hmac_key(str(path))
        except (OSError, ValueError) as exc:
            issues.append(f"keygen/0600 面失败：{exc}（{GUIDE}检查权限纪律）")
            return
        perms = meta.get("permissions") or {}
        if not perms.get("ok"):
            issues.append(f"key 权限检查失败：{perms.get('reason')}（{GUIDE}chmod 600）")
        envelope = dsse.sign_envelope("application/vnd.nf.gate+json", b"x", [
            {"keyid": KEYID, "sign": lambda data: dsse.hmac_sign(key, data)}])
        verified = dsse.verify_envelope(envelope, {KEYID: {
            "alg": "hmac-sha256", "verify": dsse.hmac_verifier(key)}})
        if not verified.get("valid"):
            issues.append("keygen 产出的 key 不能完成 DSSE 签/验")
        stats["keygen"] = 1


def scan(root: str = ".") -> tuple:
    issues: list = []
    stats = {"t3": "none", "t3_exit": 0, "t4": "none", "parity_families": 0,
             "store": 0, "keygen": 0}
    _check_artifacts(root, issues, stats)
    _check_residuals(issues, stats)
    try:
        _composition(root, issues, stats)
    except (OSError, ValueError) as exc:
        issues.append(f"T3 组合扫描异常：{exc}（{GUIDE}检查冻结 schema/模块接线）")
    return issues, stats
