"""值级重放：锁定派生件的期望值与容差（机制借鉴 311-analytics-agent 语义层 replay{expected,tolerance}）。

只对**可复算的派生值**判：|actual-expected| <= tolerance；越界即报，不阻断无关流程的语义靠调用方。
"""
from __future__ import annotations

from typing import Any, Dict, List


def replay(actual: float, expected: float, tolerance: float) -> bool:
    return abs(float(actual) - float(expected)) <= float(tolerance)


def check(cases: List[Dict[str, Any]]) -> List[str]:
    out = []
    for c in cases:
        for k in ("id", "actual", "expected", "tolerance"):
            if k not in c:
                out.append("值级重放条目缺 %s（修复指引：补该字段）" % k)
                break
        else:
            if not replay(c["actual"], c["expected"], c["tolerance"]):
                out.append("值级重放越界：%s actual=%s expected=%s tol=%s（修复指引：核算法或重签期望值）"
                           % (c["id"], c["actual"], c["expected"], c["tolerance"]))
    return out
