"""Ingress 网关（最小实现）：认证 / 白名单 / 限流 / 同意 / 证据，一次调用全过一遍。

为什么（2026-11-08，方案 P6）：MCP 面此前只做参数与信任边界校验，没有「谁能调、能调几次、
要不要用户同意、调用留了什么证据」。合规网关必须 fail-closed：任何一条不满足就拒绝，不静默降级。

四道闸 + 一道记账：
1. 认证：策略要求 token 时，params._meta.ingress_token 必须命中白名单
   （默认只跑本机，不要求 token）；
2. 白名单：工具必须在 allow 列表内；deny 列表优先（工具可被下架）；
3. 限流：同工具调用次数超过 max_calls_per_run → 拒（防死循环/滥用）；
4. 同意：side_effect != none 的工具必须带 consent: true（写盘/出网要显式同意）；
5. 记账：每次放行的调用产一条 nf-call-receipt/1（args/result digest + prev 链），可重放。
"""
from __future__ import annotations

from typing import Any

from core import mcp_manifest as mf

SCHEMA = "nf-ingress-policy/1"
GUIDE = "修复指引："
AUTH_META_KEY = "ingress_token"
CONSENT_KEY = "consent"


class IngressDenied(ValueError):
    """网关拒绝（fail-closed）。消息必须带修复指引。"""


class Ingress:
    """调用闸门 + 回执账。policy 缺省 = 本机宽松模式（无 token、全工具放行、无强制同意）。"""

    def __init__(self, policy: dict[str, Any] | None = None,
                 side_effects: dict[str, str] | None = None) -> None:
        self.policy = normalize(policy or {})
        self.side_effects = dict(side_effects or {})
        self.counts: dict[str, int] = {}
        self.receipts: list[dict[str, Any]] = []

    # ---- 四道闸 ----
    def check_call(self, tool: str, args: Any, params: Any) -> None:
        name = str(tool)
        meta = params.get("_meta") if isinstance(params, dict) else None
        meta = meta if isinstance(meta, dict) else {}
        tokens = self.policy["tokens"]
        if tokens:
            got = str(meta.get(AUTH_META_KEY) or "")
            if got not in tokens:
                raise IngressDenied(
                    "网关拒绝：token 无效或缺失（" + GUIDE + "在 params._meta."
                    + AUTH_META_KEY + " 传本机一次性 token；无 token 一律拒绝）")
        deny = set(self.policy["deny"])
        allow = set(self.policy["allow"])
        if name in deny:
            raise IngressDenied("网关拒绝：工具已被下架 " + name
                                + "（" + GUIDE + "从 deny 列表移除需显式批准）")
        if allow and name not in allow:
            raise IngressDenied("网关拒绝：工具不在白名单 " + name
                                + "（" + GUIDE + "在策略 allow 里声明，或换工具）")
        max_calls = int(self.policy["max_calls_per_run"])
        if max_calls > 0 and self.counts.get(name, 0) >= max_calls:
            raise IngressDenied("网关拒绝：工具 " + name + " 超过单轮上限 "
                                + str(max_calls) + " 次（" + GUIDE + "拆批或换会话）")
        side_effect = self.side_effects.get(name, "none")
        needs_consent = (self.policy["require_consent_for_effects"]
                         and side_effect != "none")
        if needs_consent and meta.get(CONSENT_KEY) is not True:
            raise IngressDenied("网关拒绝：" + name + " 有副作用（" + side_effect
                                + "），需 params._meta." + CONSENT_KEY
                                + " = true（" + GUIDE + "写盘/出网必须显式同意）")
        max_bytes = int(self.policy["max_args_bytes"])
        if max_bytes > 0:
            raw = repr(args)
            if len(raw.encode("utf-8")) > max_bytes:
                raise IngressDenied("网关拒绝：参数超过 " + str(max_bytes)
                                    + " 字节（" + GUIDE + "缩小载荷或分批）")

    # ---- 记账 ----
    def record_call(self, tool: str, args: Any, result: Any,
                    verdict: str = "ok") -> dict[str, Any]:
        self.counts[str(tool)] = self.counts.get(str(tool), 0) + 1
        prev = self.receipts[-1]["digest"] if self.receipts else ""
        item = mf.receipt(str(tool), args, result, prev=prev, verdict=verdict)
        self.receipts.append(item)
        return item

    def replay(self) -> dict[str, Any]:
        return mf.replay_receipts(self.receipts)


def normalize(policy: Any) -> dict[str, Any]:
    """策略规范化（宽松缺省 + 显式字段），非法值直接拒。"""
    if not isinstance(policy, dict):
        raise ValueError("Ingress 策略必须是对象（" + GUIDE + "见 nf-ingress-policy/1）")
    return {"tokens": [str(t) for t in policy.get("tokens") or []],
            "allow": [str(t) for t in policy.get("allow") or []],
            "deny": [str(t) for t in policy.get("deny") or []],
            "max_calls_per_run": int(policy.get("max_calls_per_run") or 0),
            "require_consent_for_effects": bool(
                policy.get("require_consent_for_effects", False)),
            "max_args_bytes": int(policy.get("max_args_bytes") or 0)}


def validate_policy(policy: Any) -> list[str]:
    """策略校验 → 问题列表（空 = 合法）。"""
    try:
        norm = normalize(policy)
    except ValueError as exc:
        return [str(exc)]
    issues: list[str] = []
    if norm["max_calls_per_run"] < 0:
        issues.append("max_calls_per_run 不能为负（" + GUIDE + "0 表示不限）")
    if norm["max_args_bytes"] < 0:
        issues.append("max_args_bytes 不能为负（" + GUIDE + "0 表示不限）")
    overlap = set(norm["allow"]) & set(norm["deny"])
    if overlap:
        issues.append("allow 与 deny 冲突：" + "、".join(sorted(overlap))
                      + "（" + GUIDE + "deny 优先，应移除其一）")
    return issues
