"""nf-verify/1 验证判定与报告（cc_verify 骨架；FR-V-01 / 计划 §7.3/§8.2）。

判定表（与向量集 level 族逐条一致，冻结在 results/trust/trust_vectors.json）：
- 事实四态：hash 只有 ok/invalid；signature/time_token/transparency_sth/public_anchor ∈
  ok/none/invalid；
- 任一 invalid → exit 1（验证失败）；achieved 从 T0 起按等级连续成立往上走；
- achieved < required → exit 2（不可判定，报告写清缺什么）；否则 exit 0；
- 策略非法（schema 不过 / required_level 非 T0-T4）→ exit 2，缺项码 POLICY-INVALID。

**接线边界（不夸大）**：hash 恒为真值；给了 head_signature（DSSE + issuer registry）才核
signature 事实；给了 nf-anchor/1（+ verifier）才核 time_token / transparency_sth 事实；
T4 公共锚仍未建（G4）。缺材料一律记 "none" 并如实报缺项，不把「没验/没材料」写成「验过」。
"""
from __future__ import annotations

from pathlib import Path

from core import json_doc, json_schema
from core.trust import anchor as ta
from core.trust import bundle as tb
from core.trust import human_review as hrev
from core.trust import public_anchor as pua
from core.trust import signature as tsig
from core.trust.canonical import digest_of, is_digest

GUIDE = "修复指引："
SCHEMA = "nf-verify/1"
SCHEMA_REL = "protocol/trust/verify.schema.json"
POLICY_SCHEMA_REL = "protocol/trust/policy.schema.json"
LEVELS = ("T0", "T1", "T2", "T3", "T4")
FACT_OF_LEVEL = {"T1": "signature", "T2": "time_token",
                 "T3": "transparency_sth", "T4": "public_anchor"}
MISSING_CODES = {"T1": "SIGNATURE-MISSING", "T2": "ANCHOR-MISSING",
                 "T3": "WITNESS-MISSING", "T4": "PUBLIC-ANCHOR-MISSING"}
EXIT_OK = 0
EXIT_INVALID = 1
EXIT_UNDECIDABLE = 2
POLICY_INVALID_CODE = "POLICY-INVALID"
#: 各缺项码的 message/fix（NFR-AUDIT-01：缺什么/补什么/示例）。
MISSING_GUIDE = {
    "T1": ("缺可信签名（DSSE 或等价信封）",
           "对链头/bundle root 做 DSSE 签名并挂 issuer registry 后重验（G2）"),
    "T2": ("缺 RFC 3161 时间戳覆盖",
           "对 target_digest 跑 nf evidence timestamp stamp，把 token 挂进 nf-anchor/1（G2）"),
    "T3": ("缺透明日志 STH 与 witness 签名",
           "发布 STH 并收集达到 policy.anchors.witness_threshold 的 witness 签名（G4）"),
    "T4": ("缺公共锚（Sigstore/Rekor/公共 TSA）",
           "用公共日志/公共 TSA 对链头做 T4 锚（G4）"),
}


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    """读冻结的 verify/policy schema（缺件/坏 JSON 直接抛，不静默降级）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    return json_doc.load(path, dict, what=rel)


def decide(facts: dict, required_level: str, policy_ok: bool = True) -> dict:
    """等级判定：返回与向量族一致的 {"achieved","exit_code","missing"}。"""
    if required_level not in LEVELS:
        raise ValueError(f"required_level 非法：{required_level!r}（{GUIDE}取 T0-T4）")
    if not policy_ok:
        return {"achieved": "none", "exit_code": EXIT_UNDECIDABLE,
                "missing": [POLICY_INVALID_CODE]}
    if facts.get("hash") != "ok" or any(
            facts.get(key) == "invalid" for key in FACT_OF_LEVEL.values()):
        return {"achieved": "none", "exit_code": EXIT_INVALID, "missing": []}
    achieved = "T0"
    for level in LEVELS[1:]:
        if facts.get(FACT_OF_LEVEL[level]) != "ok":
            break
        achieved = level
    if LEVELS.index(achieved) >= LEVELS.index(required_level):
        return {"achieved": achieved, "exit_code": EXIT_OK, "missing": []}
    missing = [MISSING_CODES[level]
               for level in LEVELS[LEVELS.index(achieved) + 1:LEVELS.index(required_level) + 1]]
    return {"achieved": achieved, "exit_code": EXIT_UNDECIDABLE, "missing": missing}


def skeleton_facts(hash_ok: bool) -> dict:
    """骨架事实：hash 取真值，其余四项为 none（G2/G3 未接线，如实标缺）。"""
    return {"hash": "ok" if hash_ok else "invalid", "signature": "none",
            "time_token": "none", "transparency_sth": "none", "public_anchor": "none"}


def build_report(subject_kind: str, subject_digest: str, decision: dict,
                 checks: list, issues: list, trust_roots: dict,
                 root: str = ".") -> dict:
    """组装 nf-verify/1 报告；结构不过 schema 即抛（不产出半截报告）。"""
    report = {
        "schema": SCHEMA,
        "subject": {"kind": subject_kind, "digest": subject_digest},
        "level": {"required": decision["required"], "achieved": decision["achieved"]},
        "checks": checks,
        "issues": issues,
        "trust_roots": trust_roots,
        "no_scoring": True,
    }
    problems = json_schema.json_schema_check(report, load_schema(root))
    if problems:
        raise ValueError(f"报告结构不合 nf-verify/1：{problems[:3]}（{GUIDE}按冻结 schema 修）")
    return report


def _missing_issues(codes: list) -> list:
    out = []
    for code in codes:
        message, fix = MISSING_GUIDE.get(code, (code, "补齐对应证据后重验"))
        if code == POLICY_INVALID_CODE:
            message = "策略非法或不可解析"
            fix = "按 nf-trust-policy/1 修策略：issuers/algorithms/required_level/anchors 必填"
        out.append({"code": code, "message": message, "fix": fix})
    return out


def verify(bundle: dict, policy: dict, root: str = ".", anchor: dict | None = None,
           anchor_verifiers: dict | None = None, head_signature: dict | None = None,
           registry: dict | None = None, material: dict | None = None,
           now: str | None = None, human_review: dict | None = None,
           public_anchor: dict | None = None,
           public_anchor_verifier=None, public_log_id: str = "") -> dict:
    """验证 claim bundle：返回 {"report","decision","exit_code"}（不打印、不退出）。

    head_signature 给了就核链头签名（nf-chain-head/1 + DSSE + registry）→ signature 事实；
    anchor 给了就核 nf-anchor/1 → time_token/transparency_sth 事实，target = subject_digest
    （bundle 的规范摘要；锚必须绑这个对象）。缺 registry/material/verifier 记 none，不假装验过。
    """
    policy_schema = load_schema(root, POLICY_SCHEMA_REL)
    bundle_schema = tb.load_schema(root)
    policy_problems = json_schema.json_schema_check(policy, policy_schema)
    raw_required = str((policy or {}).get("required_level") or "")
    required = raw_required if raw_required in LEVELS else "T0"
    policy_ok = not policy_problems and raw_required in LEVELS
    run = tb.verify_bundle(bundle, bundle_schema)
    hash_ok = bool(run["ok"])
    subject_digest = digest_of(bundle)
    if not is_digest(subject_digest):
        raise ValueError(f"无法计算 subject digest（{GUIDE}检查 canonical 编码）")
    facts = skeleton_facts(hash_ok)
    checks = [
        {"id": "A1-bundle-integrity", "ok": hash_ok,
         "detail": "bundle 结构/Merkle 根/逐叶 proof 全过" if hash_ok
                   else "bundle 校验失败：" + "；".join(run["issues"][:2])},
    ]
    anchor_issues: list = []
    if anchor is not None:
        merged = ta.verify_anchor_set(anchor, subject_digest, policy,
                                      anchor_verifiers, root=root)
        facts.update(merged["facts"])
        anchor_issues = merged["issues"]
        checks.append({"id": "A2-anchor-facts", "ok": not anchor_issues,
                       "detail": "anchor 事实：" + "；".join(
                           f"{k}={v}" for k, v in sorted(merged["facts"].items()))})
        checks.append({"id": "A2-anchor-details", "ok": not anchor_issues,
                       "detail": "；".join(f"{d['kind']}:{d['status']}"
                                          for d in merged["details"]) or "无锚"})
    else:
        checks.append({"id": "A2-anchor-facts", "ok": False,
                       "detail": "未提供 nf-anchor/1；T2 及以上只报缺项，不冒充等级"})
    signature_issues: list = []
    if head_signature is not None:
        if not registry or not isinstance(material, dict):
            checks.append({"id": "A1-head-signature", "ok": False,
                           "detail": "给了签名信封但缺 registry/material，签名事实记 none"})
        else:
            try:
                envelope_schema = json_doc.load(
                    Path(root) / "protocol/trust/dsse.schema.json", dict,
                    what="dsse schema")
            except (OSError, ValueError):
                envelope_schema = None
            verified = tsig.verify_head(head_signature, "bundle", subject_digest,
                                        registry, material, envelope_schema,
                                        now=now, root=root)
            if verified.get("ok"):
                facts["signature"] = "ok"
                checks.append({"id": "A1-head-signature", "ok": True,
                               "detail": "链头签名有效：signers=" + ",".join(
                                   verified.get("signers") or [])})
            elif verified.get("reason") in ("KEY-UNKNOWN", "VERIFIER-MISSING"):
                checks.append({"id": "A1-head-signature", "ok": False,
                               "detail": "签名无法判定：" + str(verified.get("reason"))})
            else:
                facts["signature"] = "invalid"
                reason = str(verified.get("reason") or "SIGNATURE-INVALID")
                signature_issues.append({
                    "code": reason, "message": "链头签名校验失败",
                    "fix": "重签链头并确认 issuer registry 生命周期（吊销/过期/轮换）"})
                checks.append({"id": "A1-head-signature", "ok": False,
                               "detail": "链头签名失败：" + reason})
    else:
        checks.append({"id": "A1-head-signature", "ok": False,
                       "detail": "未提供链头签名；T1 及以上只报缺项，不冒充等级"})
    public_issues: list = []
    if public_anchor is not None:
        resolved = pua.verify_public_anchor(public_anchor, public_anchor_verifier,
                                            public_log_id, subject_digest, root=root)
        if resolved.get("ok"):
            facts["public_anchor"] = "ok"
            checks.append({"id": "A5-public-anchor", "ok": True,
                           "detail": f"public anchor ok：log={resolved.get('log_id')} "
                                     f"tree={resolved.get('tree_size')}"})
        else:
            facts["public_anchor"] = "invalid"
            public_issues.append({"code": str(resolved.get("reason") or "PUBLIC-ANCHOR-INVALID"),
                                  "message": "公共锚校验失败",
                                  "fix": "核对 pinned log id/公钥、inclusion proof 与目标摘要"})
            checks.append({"id": "A5-public-anchor", "ok": False,
                           "detail": str(resolved.get("reason"))})
    else:
        checks.append({"id": "A5-public-anchor", "ok": False,
                       "detail": "未提供公共锚（T4 只报缺项，不冒充已锚）"})
    review_state = hrev.STATE_PENDING
    review_issues: list = []
    if human_review is not None and registry and isinstance(material, dict):
        try:
            envelope_schema = json_doc.load(
                Path(root) / "protocol/trust/dsse.schema.json", dict, what="dsse schema")
        except (OSError, ValueError):
            envelope_schema = None
        reviewed = hrev.verify_review(human_review, "bundle", subject_digest, registry,
                                      material, envelope_schema, now=now, root=root)
        review_state = hrev.review_state(reviewed)
        review_detail = f"human review state={review_state}"
        if reviewed.get("reason"):
            review_detail += f"（{reviewed.get('reason')}）"
        checks.append({"id": "A4-human-review",
                       "ok": review_state == hrev.STATE_APPROVED,
                       "detail": review_detail})
        if review_state in (hrev.STATE_REJECTED, hrev.STATE_ESCALATED, hrev.STATE_INVALID):
            review_issues.append({"code": str(reviewed.get("reason") or "REVIEW-INVALID"),
                                  "message": f"人类复核未通过（state={review_state}）",
                                  "fix": "重走复核并签 approve，或不要附上被拒记录"})
    else:
        checks.append({"id": "A4-human-review", "ok": False,
                       "detail": "human review state=PENDING"
                                 "（未提供复核记录；PENDING 不等于通过）"})
    decision = decide(facts, required, policy_ok=policy_ok)
    decision["required"] = required
    issues = _missing_issues(decision["missing"])
    issues.extend(anchor_issues)
    issues.extend(signature_issues)
    issues.extend(review_issues)
    issues.extend(public_issues)
    if not hash_ok:
        issues.insert(0, {"code": "BUNDLE-INVALID",
                          "message": "bundle 自洽性校验失败（" +
                                     "；".join(run["issues"][:2]) + "）",
                          "fix": "重算 bundle，或修复被证数据后重新打包"})
    trust_roots = {
        "issuers": [str(item.get("id")) for item in (policy or {}).get("issuers") or []
                    if isinstance(item, dict)],
        "tsa": [str(item.get("id")) for item in (policy or {}).get("tsa_roots") or []
                if isinstance(item, dict)],
    }
    report = build_report("bundle", subject_digest, decision, checks, issues, trust_roots,
                          root=root)
    return {"report": report, "decision": decision, "exit_code": decision["exit_code"]}
