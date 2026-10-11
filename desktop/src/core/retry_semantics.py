"""可重试性语义 + lint 退出码分档（机制借鉴 iskills retry 语义 / instar 0/1/2 分档）。

错误面统一给两件机读事实：**retry 语义**（safe / after-fix / inspect-state）与
**退出码分档**（0=通过，1=发现问题，2=我没能看）。「我看不了」不得与「没问题」混同。
"""
from __future__ import annotations

SAFE = "safe"                # 幂等，可安全重试
AFTER_FIX = "after-fix"      # 修好前置条件后重试
INSPECT = "inspect-state"    # 副作用状态未知，先查明再动

_TABLE = {
    "RATE_LIMITED": SAFE,
    "NETWORK": SAFE,
    "PRECONDITION": AFTER_FIX,
    "VALIDATION": AFTER_FIX,
    "PARTIAL_APPLY": INSPECT,
    "UNKNOWN_STATE": INSPECT,
    "PARSER_UNAVAILABLE": INSPECT,
}

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_COULD_NOT_CHECK = 2


def semantics(code: str) -> str:
    """未知码一律 inspect-state（未知不得假设可重试）。"""
    return _TABLE.get(str(code), INSPECT)


def exit_tier(status: str) -> int:
    """status ∈ {ok, findings, could-not-check}。"""
    return {"ok": EXIT_OK, "findings": EXIT_FINDINGS,
            "could-not-check": EXIT_COULD_NOT_CHECK}.get(str(status), EXIT_COULD_NOT_CHECK)
