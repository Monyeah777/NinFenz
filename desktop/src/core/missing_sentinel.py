"""缺位哨兵：解析缺段必须显式化且判非法（机制借鉴 Yollama types/model/name.go:30-36）。

解析不到字段时静默给空串，会把「缺件」混成「空值」；本模块用哨兵把缺位显式化，
并规定含哨兵的值必须判非法。
"""
from __future__ import annotations

from typing import Any, Tuple

SENTINEL = "!MISSING!"


def parse_marked(text: str, sentinel: str = SENTINEL) -> Tuple[Any, bool]:
    """→ (值, 是否缺位)。缺位返回哨兵本身 + True，不返回空串。"""
    s = "" if text is None else str(text)
    if not s.strip() or s.strip() == sentinel:
        return sentinel, True
    return s, False


def reject_missing(values) -> list:
    """含哨兵的值必须判非法（fail-closed）。"""
    out = []
    for v in values:
        if isinstance(v, str) and SENTINEL in v:
            out.append("值含缺位哨兵 %s（修复指引：补齐真实值或显式声明缺失字段）" % SENTINEL)
    return out
