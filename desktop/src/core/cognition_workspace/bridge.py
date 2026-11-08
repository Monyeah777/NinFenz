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
    # 同构判据 #1（第 49 轮）：commitment 绑定契约侧的外部时点引用（如 TSA token digest）。
    # 两侧若指向不同 token，本字段不同 → 同构判据可判定；缺时点则留空串（字段集保持恒定）。
    ts_digest = str(cc_result.get("ts_digest") or "")
    # 资源层记账（第 92 轮）：两本账**并列记、不合并**——认知侧记步数、契约侧记毫秒成本。
    # 合并成一个分数就等于把「预算」变成「评分」，本仓禁止。
    # 缺值用 None，不填 0（0 会被误读为「没花」）。
    steps = (state.get("budget") or {}).get("steps_used")
    cost = cc_result.get("cost_ms")
    payload = {"schema": COMMIT_SCHEMA, "bridge_version": BRIDGE_VERSION,
               "cog_digest": str(state["digest"]),
               "claim_digest": str(claim_doc["digest"]),
               "cc_digest": digest_of({"verdict": verdict, "subject": cc_result.get("subject"),
                                       "detail": cc_result.get("detail"),
                                       "ts_digest": ts_digest}),
               "cc_verdict": verdict,
               "ts_digest": ts_digest,
               "cost": {"cog_steps": None if steps is None else int(steps),
                        "cc_cost_ms": None if cost is None else int(cost)},
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
                          "detail": cc_result.get("detail"),
                          "ts_digest": str(commitment.get("ts_digest") or "")})
    if str(commitment.get("cc_digest")) != expected:
        res["issues"].append("契约侧 digest 不匹配——cc 结果变了")
    if str(commitment.get("cc_verdict")) != verdict:
        res["issues"].append("commitment 记录的判定与当前 cc 结果不同")
    ts_now = str(cc_result.get("ts_digest") or "")
    if str(commitment.get("ts_digest") or "") != ts_now:
        res["issues"].append("时点引用不匹配——两侧没有指向同一 token")
    # 资源层（第 105 轮）：核对时顺带核两本账的形状——判据必须被生产路径调用才有用。
    res["issues"].extend(resource_accounting_issues(commitment))
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


def resource_accounting_issues(commitment: Any) -> list[str]:
    """核对 commitment 的「两本账」（资源层同构判据 #7 的可复用核）。

    规则（第 92 轮）：认知侧步数与契约侧毫秒成本必须**并列记**，不得合并成单一分数；
    缺值用 None（不填 0——0 会被误读成「没花」）；负值非法。

    为什么这条算同构：两侧量的不是同一量纲，同构点不在「数值相等」，而在**两本账都到场且不混记**。
    混记（出现 total / score 之类聚合键）即红——那等于把预算变成评分。
    """
    issues: list[str] = []
    if not isinstance(commitment, dict):
        return ["commitment 不是对象（" + GUIDE + "用 bridge.commit 的产出）"]
    cost = commitment.get("cost")
    if not isinstance(cost, dict):
        return ["缺 cost 两本账（" + GUIDE + "commitment.cost 必须是对象）"]
    allowed = {"cog_steps", "cc_cost_ms"}
    extra = sorted(set(cost) - allowed)
    if extra:
        issues.append("两本账混记了额外键 " + str(extra) + "（" + GUIDE
                      + "只允许 cog_steps / cc_cost_ms 并列）")
    for key in ("cog_steps", "cc_cost_ms"):
        if key not in cost:
            issues.append("缺 " + key + "（" + GUIDE + "两本账都要记，缺值写 None）")
            continue
        value = cost[key]
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool):
            issues.append(key + " 必须是整数或 None（" + GUIDE + "别用浮点/字符串）")
        elif value < 0:
            issues.append(key + " 不能为负：" + str(value))
    return issues


def obligation_record_issues(record: dict[str, Any], obligation_doc: dict[str, Any],
                             ) -> list[str]:
    """核对「回灌记录」与「回灌消息」是否逐项对应（同构判据 #3 的可复用核）。

    为什么抽成函数（第 74 轮）：判据要能被变异打死——只有把核对逻辑单独拿出来，
    才可能用一条「故意改坏」的记录证明它真的会红。三条：来源标记、失败集同序相等、证人可复算。
    """
    issues: list[str] = []
    if not isinstance(record, dict):
        return ["记录不是对象（" + GUIDE + "用 apply_obligation 的产出）"]
    if str(record.get("trigger") or "") != "bridge-obligation":
        issues.append("来源标记不是 bridge-obligation（" + GUIDE + "回灌必须写明来自桥）")
    want = list(obligation_doc.get("failed") or []) + list(obligation_doc.get("unknown") or [])
    got = list((record.get("witness") or {}).get("evidence") or [])
    if [str(x) for x in got] != [str(x) for x in want]:
        issues.append("失败集与回灌消息不一致（" + GUIDE + "两侧必须逐项同序）")
    if str(record.get("witness_digest") or "") != digest_of(record.get("witness") or {}):
        issues.append("证人 digest 不可复算（" + GUIDE + "记录被改过）")
    return issues


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

#: nf evidence verify 的四词判定（docs/ccos/abi-v0.md §4）→ 桥的 pass/fail 归类
VERIFY_PASS = ("ok",)
VERIFY_FAIL = ("revoked", "expired", "invalid")
VERIFY_WORDS = VERIFY_PASS + VERIFY_FAIL


def cc_result_from_verify(verify_doc: dict[str, Any]) -> dict[str, Any]:
    """把 nf evidence verify --json 的真实输出转成桥认的 cc 结果。

    映射规则（不猜）：四词判定保留原词；subject 取证据链头（head），detail 带 root/level/count。
    """
    if not isinstance(verify_doc, dict):
        raise ValueError("verify 输出必须是对象（" + GUIDE + "nf evidence verify --json）")
    verdict = str(verify_doc.get("verdict") or "").lower()
    if not verdict and str(verify_doc.get("error") or ""):
        # 真 CLI 在「包读不开/结构坏」时给的是 error 对象，不是四词判定：
        # 桥必须把它当 invalid（fail-closed），而不是抛错或当没看见。
        verdict = "invalid"
        verify_doc = dict(verify_doc, issues=[str(verify_doc["error"])],
                          root=verify_doc.get("root"), head=verify_doc.get("head"))
    if verdict not in VERIFY_WORDS:
        raise ValueError("未知证据判定：" + verdict
                         + "（" + GUIDE + "四词判定：ok/revoked/expired/invalid）")
    # 时点引用（同构判据 #1 的契约侧来源）：verify 输出若带时间戳 token 摘要，就带进 cc 结果；
    # 没有就留空串——**不伪造时点**。字段恒定，便于 bridge 侧按「两侧是否指向同一 token」判定。
    detail = {"root": verify_doc.get("root"), "level": verify_doc.get("level"),
              "count": verify_doc.get("count"),
              "issues": list(verify_doc.get("issues") or [])}
    ts = verify_doc.get("ts_digest") or verify_doc.get("timestamp_digest") or ""
    return {"verdict": verdict,
            "subject": str(verify_doc.get("head") or verify_doc.get("root") or ""),
            "ts_digest": str(ts),
            "detail": detail}


def commit_from_verify(bundle: dict[str, Any], claim_doc: dict[str, Any],
                       verify_doc: dict[str, Any],
                       roles: list[str] | None = None) -> dict[str, Any]:
    """用真实证据包复验结果建 commitment（闭环里 cc 侧的真输入）。"""
    return commit(bundle, claim_doc, cc_result_from_verify(verify_doc), roles=roles)


def obligation_from_verify(commitment: dict[str, Any],
                           verify_doc: dict[str, Any]) -> dict[str, Any]:
    """证据复验不过 → 直接把 issues 编成回灌消息（unknown 保留供后续补证）。"""
    cc = cc_result_from_verify(verify_doc)
    issues = [str(x) for x in (verify_doc.get("issues") or [])]
    failed = issues if cc["verdict"] in VERIFY_FAIL else []
    return obligation(commitment, cc, failed=failed)
