"""超限输出的可恢复截断信封（机制借鉴 yolop context_cost_control.rs:49-123）。

截断不得静默丢内容：信封带 truncated 标记与 full_output 指针（可找回全文）。
"""
from __future__ import annotations

from typing import Any, Dict, List


def envelope(text: str, limit: int, full_output_ref: str = "") -> Dict[str, Any]:
    t = text or ""
    if len(t) <= limit:
        return {"truncated": False, "text": t, "full_output": None, "total_len": len(t)}
    return {"truncated": True, "text": t[:limit], "full_output": full_output_ref or None,
            "total_len": len(t)}


def validate(env: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if env.get("truncated") and not env.get("full_output"):
        issues.append("截断信封缺 full_output 指针（修复指引：给出可取回全文的引用，勿静默丢内容）")
    if not isinstance(env.get("total_len"), int):
        issues.append("截断信封缺 total_len（修复指引：写明原始长度）")
    return issues
