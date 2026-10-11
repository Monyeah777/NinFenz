"""特性生命周期：弃用窗 + 破坏性变更换标识符（机制借鉴 MCP SEP feature-lifecycle / SEP-2133）。

三态 + 最短弃用窗（自弃用声明起算）+ 破坏性变更必须换新标识符；
单条不合格即 FAIL，避免「悄悄删掉」与「破坏性改动沿用旧名」。
"""
from __future__ import annotations

from typing import Any, Dict, List

STATES = ("active", "deprecated", "removed")
DEFAULT_MIN_WINDOW_DAYS = 365


def check(entries: List[Dict[str, Any]], as_of: str, min_window_days: int = DEFAULT_MIN_WINDOW_DAYS) -> List[str]:
    """entries: {name, state, deprecated_at?, removed_at?, breaking?, new_identifier?}。"""
    issues: List[str] = []
    for e in entries:
        name = str(e.get("name"))
        state = e.get("state")
        if state not in STATES:
            issues.append("特性 %s 状态越词表：%r（修复指引：取 %s）" % (name, state, "/".join(STATES)))
            continue
        dep = str(e.get("deprecated_at") or "")
        if state in ("deprecated", "removed"):
            if not dep:
                issues.append("特性 %s 缺 deprecated_at（修复指引：补弃用日期，起算弃用窗）" % name)
                continue
            if state == "removed":
                gap = _days(dep, as_of)
                if gap is not None and gap < min_window_days:
                    issues.append("特性 %s 弃用窗不足：%d 天 < %d 天（修复指引：满窗后再移除）"
                                  % (name, gap, min_window_days))
        if e.get("breaking") and not str(e.get("new_identifier") or "").strip():
            issues.append("特性 %s 属破坏性变更却沿用旧标识符（修复指引：换新标识符，禁止原地改义）" % name)
    return issues


def _days(a: str, b: str):
    from datetime import date
    try:
        ya, ma, da = (int(x) for x in a.split("-"))
        yb, mb, db = (int(x) for x in b.split("-"))
        return (date(yb, mb, db) - date(ya, ma, da)).days
    except (ValueError, TypeError):
        return None
