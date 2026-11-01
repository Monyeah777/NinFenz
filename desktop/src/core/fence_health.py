"""围栏机读块「在场但坏」判别（机制借鉴 objectui unevaluablePredicate / ADR-0137 D4）。

共享解析器把「未命中」与「解析失败」都收敛成空值；这对大多数消费方是对的
（它们只问「有没有可用的块」），但对**契约面**不够：
「围栏在场却解析不出该块」不得折叠成「本件无该块」——否则坏掉的机读块会被
静默当成 L0/未声明。本模块把该判别独立出来，供契约面消费。

边界（诚实声明）：本模块自带围栏正则以保持**叶子件**（不 import core 兄弟），
避免给 conformance_scan 增加消费者而压低其稳定度（见 patterns/dependency-direction）。
重构波次应把它收敛为 conformance_scan::FENCE 的单一来源。
"""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple

#: 与 conformance_scan::FENCE 同形（见模块边界声明）
_FENCE = re.compile(r"(?ms)\u0060\u0060\u0060yaml\s*(.*?)\u0060\u0060\u0060")

#: 状态词表（封闭）
ABSENT = "absent"            # 本件未声明该块
OK = "ok"                    # 块在场且可解析
BAD = "bad"                  # 块在场但解析不出（不得折叠成 ABSENT）
UNAVAILABLE = "unavailable"  # 解析器不可用（PyYAML 缺席）——不判死


def fence_present(text: str, marker: str) -> bool:
    """围栏里是否**出现**该 marker（只看在不在，不看能否解析）。"""
    return any(marker in m.group(1) for m in _FENCE.finditer(text or ""))


def classify(text: str, marker: str, parsed: Any, parser_available: bool = True
             ) -> Tuple[str, Any]:
    """→ (state, value)。parsed 由调用方用自己的解析器给出（保持解析单一来源）。

    state ∈ {absent, ok, bad, unavailable}。bad 只在**解析器可用**且围栏在场时给出。
    """
    if isinstance(parsed, dict) and marker in parsed:
        return OK, parsed[marker]
    if not fence_present(text, marker):
        return ABSENT, None
    if not parser_available:
        return UNAVAILABLE, None
    return BAD, None


def bad_fence_issue(rel: str, text: str, parsed: Any, marker: str = "machine_contract",
                    parser_available: bool = True) -> Optional[str]:
    """「在场但坏」→ 一条带修复指引的 issue；其余状态 → None。"""
    state, _ = classify(text, marker, parsed, parser_available)
    if state != BAD:
        return None
    return ("%s: %s 围栏在场但不可解析（不得等价于「本件无该块」）"
            "（修复指引：修 YAML 语法后重跑；机读块契约见 01 §1.1）" % (rel, marker))
