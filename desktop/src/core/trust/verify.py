"""nf-verify/1 验证判定与报告（cc_verify 骨架；FR-V-01 / 计划 §7.3/§8.2）。

判定表（与向量集 level 族逐条一致，冻结在 results/trust/trust_vectors.json）：
- 事实四态：hash 只有 ok/invalid；signature/time_token/transparency_sth/public_anchor ∈
  ok/none/invalid；
- 任一 invalid → exit 1（验证失败）；achieved 从 T0 起按等级连续成立往上走；
- achieved < required → exit 2（不可判定，报告写清缺什么）；否则 exit 0；
- 策略非法（schema 不过 / required_level 非 T0-T4）→ exit 2，缺项码 POLICY-INVALID。

**骨架边界（不夸大）**：本轮只能把 hash 事实算成真值；T1 签名/DSSE、T2 RFC 3161 token、
T3 STH/witness、T4 公共锚的核验在 G2/G3 接线，四者恒为 "none"——报告如实写缺项并 exit 2，
不把「没验」写成「验过」。
"""
from __future__ import annotations

from pathlib import Path

from core import json_doc, json_schema
from core.trust import anchor as ta
from core.trust import bundle as tb
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
           anchor_verifiers: dict | None = None) -> dict:
    """验证 claim bundle：返回 {"report","decision","exit_code"}（不打印、不退出）。

    anchor 给了就走 nf-anchor/1 核验：target 必须等于 bundle.merkle_root，事实
    （time_token/transparency_sth）由 core.trust.anchor 投影；缺 verifier 记 none。
    """
    policy_schema = load_schema(root, POLICY_SCHEMA_REL)
    bundle_schema = tb.load_schema(root)
    policy_problems = json_schema.json_schema_check(policy, policy_schema)
    raw_required = str((policy or {}).get("required_level") or "")
    required = raw_required if raw_required in LEVELS else "T0"
    policy_ok = not policy_problems and raw_required in LEVELS
    run = tb.verify_bundle(bundle, bundle_schema)
    hash_ok = bool(run["ok"])
    facts = skeleton_facts(hash_ok)
    checks = [
        {"id": "A1-bundle-integrity", "ok": hash_ok,
         "detail": "bundle 结构/Merkle 根/逐叶 proof 全过" if hash_ok
                   else "bundle 校验失败：" + "；".join(run["issues"][:2])},
    ]
    anchor_issues: list = []
    if anchor is not None:
        merged = ta.verify_anchor_set(anchor, str(bundle.get("merkle_root") or ""),
                                      policy, anchor_verifiers, root=root)
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
    decision = decide(facts, required, policy_ok=policy_ok)
    decision["required"] = required
    issues = _missing_issues(decision["missing"])
    issues.extend(anchor_issues)
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
    subject_digest = digest_of(bundle)
    if not is_digest(subject_digest):
        raise ValueError(f"无法计算 subject digest（{GUIDE}检查 canonical 编码）")
    report = build_report("bundle", subject_digest, decision, checks, issues, trust_roots,
                          root=root)
    return {"report": report, "decision": decision, "exit_code": decision["exit_code"]}
