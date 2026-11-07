"""双核桥（commitment）：唯一共享对象 + 双向闭环。

为什么只有这一个共享对象：两核若互相读内部状态，独立性与可替换性立刻消失
（认知核会被契约核的门禁定义，契约核会被话语状态污染）。所以桥只交换
commitment{cog_digest, cc_digest, claim_digest, bridge_version, roles}，
两侧各自用 digest 证明「我认可这一版」，再各自留自己的记录。

闭环（方案 P5）：cog_commit → cc_check → obligation（失败项回灌）→ cog 侧 detect/revise
→ 新 claim → 再 commit → cc_attest → receipt。

两条硬判据：
- **双向**：cc 判 fail 必须真的改变认知侧状态（控制面记录增加），不是单向审计；
- **fail-closed**：cc 不可用/不可解析时，认知侧状态**一点不改**（没有半成品 commitment）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from core.cognition_workspace import control as ct
from core.cognition_workspace import discourse as dc

COMMIT_SCHEMA = "nf-bridge-commitment/1"
OBLIGATION_SCHEMA = "nf-bridge-obligation/1"
BRIDGE_VERSION = "b0"
GUIDE = "修复指引："
VERDICT_PASS = ("pass", "ok", "verified", "valid")
VERDICT_FAIL = ("fail", "invalid", "revoked", "expired", "tampered", "missing")


def digest_of(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cc_verdict(cc_result: Any) -> str:
    if not isinstance(cc_result, dict):
        raise ValueError("契约核结果必须是对象（" + GUIDE + "传 nf evidence verify --json 的输出）")
    verdict = str(cc_result.get("verdict") or "").lower()
    if not verdict and isinstance(cc_result.get("ok"), bool):
        verdict = "pass" if cc_result["ok"] else "fail"
    if not verdict:
        raise ValueError("契约核结果缺 verdict（" + GUIDE +
                "四词判定：pass/fail/revoked/expired…）")
    return verdict


def commit(bundle: dict[str, Any], claim_doc: dict[str, Any], cc_result: dict[str, Any],
           roles: list[str] | None = None) -> dict[str, Any]:
    """生成 commitment（不改认知侧状态）。任一侧不合法即抛错（fail-closed）。"""
    state = bundle.get("state") or {}
    bad = dc.validate(state)
    if bad:
        raise ValueError("认知侧状态不合法：" + "；".join(bad[:2]))
    if not isinstance(claim_doc, dict) or not str(claim_doc.get("digest") or ""):
        raise ValueError("主张文件缺 digest（" + GUIDE + "用 nf cog claim --out 生成）")
    verdict = _cc_verdict(cc_result)
    if verdict not in VERDICT_PASS + VERDICT_FAIL:
        raise ValueError("未知契约核判定：" + verdict + "（" + GUIDE + "见 VERDICT_PASS/FAIL）")
    payload = {"schema": COMMIT_SCHEMA, "bridge_version": BRIDGE_VERSION,
               "cog_digest": str(state["digest"]),
               "claim_digest": str(claim_doc["digest"]),
               "cc_digest": digest_of({"verdict": verdict, "subject": cc_result.get("subject"),
                                       "detail": cc_result.get("detail")}),
               "cc_verdict": verdict,
               "roles": list(roles or ["local-trusted"]),
               "prev": str((bundle.get("commitments") or [{}])[-1].get("digest") or "")}
    payload["digest"] = digest_of(payload)
    return payload


def verify_commitment(commitment: Any, bundle: dict[str, Any], claim_doc: dict[str, Any],
                      cc_result: dict[str, Any]) -> dict[str, Any]:
    """核对 commitment 与两侧当前状态是否一致 → {ok, issues}。"""
    res: dict[str, Any] = {"ok": False, "issues": []}
    if not isinstance(commitment, dict) or str(commitment.get("schema")) != COMMIT_SCHEMA:
        res["issues"].append("commitment schema 不匹配（" + GUIDE + "需要 " + COMMIT_SCHEMA + "）")
        return res
    body = {k: v for k, v in commitment.items() if k != "digest"}
    if digest_of(body) != commitment.get("digest"):
        res["issues"].append("commitment 自身 digest 不符（" + GUIDE + "被改过）")
        return res
    state = bundle.get("state") or {}
    if str(commitment.get("cog_digest")) != str(state.get("digest")):
        res["issues"].append("认知侧 digest 不匹配——commitment 之后 discourse 又变了")
    if str(commitment.get("claim_digest")) != str(claim_doc.get("digest")):
        res["issues"].append("主张 digest 不匹配——commitment 之后 claim 变了")
    verdict = _cc_verdict(cc_result)
    expected = digest_of({"verdict": verdict, "subject": cc_result.get("subject"),
                          "detail": cc_result.get("detail")})
    if str(commitment.get("cc_digest")) != expected:
        res["issues"].append("契约侧 digest 不匹配——cc 结果变了")
    if str(commitment.get("cc_verdict")) != verdict:
        res["issues"].append("commitment 记录的判定与当前 cc 结果不同")
    res["ok"] = not res["issues"]
    return res


def obligation(commitment: dict[str, Any], cc_result: dict[str, Any],
               failed: list[str] | None = None,
               unknown: list[str] | None = None) -> dict[str, Any]:
    """把 cc 侧未通过的项编成回灌消息（x_obligation）。"""
    verdict = _cc_verdict(cc_result)
    items = [str(x) for x in (failed or [])]
    unknowns = [str(x) for x in (unknown or [])]
    if verdict in VERDICT_FAIL and not items:
        items = ["cc_verdict=" + verdict]
    body = {"schema": OBLIGATION_SCHEMA, "commitment_digest": str(commitment.get("digest")),
            "cc_verdict": verdict, "failed": items, "unknown": unknowns,
            "next_actions": ([{"op": "detect", "why": "契约核未通过，需要先定位失败面"}]
                             + ([{"op": "request_context", "why": "存在未知项，需补输入"}]
                                if unknowns else []))}
    body["digest"] = digest_of(body)
    return body


def apply_obligation(bundle: dict[str, Any], obligation_doc: dict[str, Any]) -> dict[str, Any]:
    """把回灌消息落到认知侧：控制面记一条 detect（真副作用），discourse 不动。

    为什么不动 discourse：discourse 的变化必须由 meta move 产生，否则就是「桥直接改内容」，
    违反三层分离。桥只负责把「契约核说不行」变成「控制面已知的异常」，后续 revise 仍由人/策略发起。
    """
    if (not isinstance(obligation_doc, dict)
            or str(obligation_doc.get("schema")) != OBLIGATION_SCHEMA):
        raise ValueError("回灌消息 schema 不匹配（" + GUIDE + "需要 " + OBLIGATION_SCHEMA + "）")
    body = {k: v for k, v in obligation_doc.items() if k != "digest"}
    if digest_of(body) != obligation_doc.get("digest"):
        raise ValueError("回灌消息 digest 不符（" + GUIDE + "被改过）")
    control = bundle.get("control") or ct.new()
    witness = {"anomaly": "cc_check 未通过：" + str(obligation_doc.get("cc_verdict")),
               "evidence": list(obligation_doc.get("failed") or []) +
                           list(obligation_doc.get("unknown") or [])}
    new_control, _out = ct.apply(control, "detect", witness, trigger="bridge-obligation")
    new_bundle = dict(bundle)
    new_bundle["control"] = new_control
    new_bundle["commitments"] = list(bundle.get("commitments") or [])
    return new_bundle


def append_commitment(bundle: dict[str, Any], commitment: dict[str, Any]) -> dict[str, Any]:
    """把 commitment 挂到会话上（只追加，prev 链）。"""
    chain = list(bundle.get("commitments") or [])
    if chain and str(commitment.get("prev")) != str(chain[-1].get("digest")):
        raise ValueError("commitment 链断：prev 与上一条不符（" + GUIDE + "按序追加）")
    new_bundle = dict(bundle)
    new_bundle["commitments"] = chain + [commitment]
    return new_bundle


def replay_commitments(commitments: Any) -> dict[str, Any]:
    """commitment 链重放 → {ok, issues}。"""
    res: dict[str, Any] = {"ok": True, "issues": []}
    if not isinstance(commitments, list):
        res.update({"ok": False, "issues": ["commitments 必须是数组"]})
        return res
    prev = ""
    for item in commitments:
        if str(item.get("prev") or "") != prev:
            res["issues"].append("第 " + str(len(res["issues"]) + 1) + " 条 prev 不符")
        if digest_of({k: v for k, v in item.items() if k != "digest"}) != item.get("digest"):
            res["issues"].append("第 " + str(len(res["issues"]) + 1) + " 条 digest 不符")
        prev = str(item.get("digest") or "")
    res["ok"] = not res["issues"]
    return res
