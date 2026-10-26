"""被否决候选留档（机制借鉴 awesome-jev 00-methodology.md:9 rejected.jsonl 4,487 条）。

「看过但不吸收」必须留档并写明理由，否则同一候选会被反复重审。
"""
from __future__ import annotations

from typing import Any, Dict, List


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    """每条须有 candidate / reason / date；id 唯一。"""
    issues: List[str] = []
    seen = set()
    for e in entries:
        c = str(e.get("candidate") or "")
        if not c or not str(e.get("reason") or "").strip() or not str(e.get("date") or "").strip():
            issues.append("否决条目缺字段（candidate/reason/date）：%r（修复指引：补齐三字段）" % e)
        if c in seen:
            issues.append("否决条目重复：%s（修复指引：合并为一条）" % c)
        seen.add(c)
    return issues


def is_declined(entries: List[Dict[str, Any]], candidate: str) -> bool:
    return any(e.get("candidate") == candidate for e in entries)
