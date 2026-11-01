"""词表外取值策略 unknown_policy（机制借鉴 tinychannels capabilities.rs:1-14,66-81）。

NF 有封闭词表与 FAIL；本模块给每个 scheme 一个显式 **unknown_policy**
（fail / warn / fallback），把「词表外怎么办」从隐式默认变成声明。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

POLICIES = ("fail", "warn", "fallback")


def validate(scheme: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if scheme.get("unknown_policy") not in POLICIES:
        issues.append("scheme %s 的 unknown_policy 越词表：%r（修复指引：取 %s）"
                      % (scheme.get("id"), scheme.get("unknown_policy"), "/".join(POLICIES)))
    if scheme.get("unknown_policy") == "fallback" and not scheme.get("fallback_value"):
        issues.append("scheme %s 选 fallback 却未给 fallback_value（修复指引：补默认值）" % scheme.get("id"))
    return issues


def resolve(scheme: Dict[str, Any], value: Any) -> Tuple[bool, Any, str]:
    """→ (是否在册, 采用值, 处置)。"""
    values = scheme.get("values") or []
    if value in values:
        return True, value, "ok"
    policy = scheme.get("unknown_policy")
    if policy == "fallback":
        return False, scheme.get("fallback_value"), "fallback"
    return False, None, str(policy)
