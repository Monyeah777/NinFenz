"""删除文本前必须有可复原证据 + 保留事故疤痕（机制借鉴 oh-my-pi tool-prompt-optimization/SKILL.md:59-71）。

删改不可逆：本模块要求每次删除登记**可复原证据**（备份 / 版本库 / 原文引用），
并可选要求 blame 记录（谁在何时为何删）。
"""
from __future__ import annotations

from typing import Any, Dict, List

KINDS = ("backup", "vcs", "quote")


def check(removals: List[Dict[str, Any]]) -> List[str]:
    """removals: {target, kind, ref, blame?}。kind 越词表或缺 ref → issue。"""
    issues: List[str] = []
    for r in removals:
        tgt = str(r.get("target"))
        kind = r.get("kind")
        if kind not in KINDS:
            issues.append("删除 %s 缺可复原证据类型（修复指引：kind 取 %s）" % (tgt, "/".join(KINDS)))
        if not str(r.get("ref") or "").strip():
            issues.append("删除 %s 缺证据引用 ref（修复指引：给出备份/commit/原文位置）" % tgt)
    return issues


def missing_blame(removals: List[Dict[str, Any]], require_blame: bool = False) -> List[str]:
    """可选：要求事故疤痕（blame 记录）。"""
    if not require_blame:
        return []
    return ["删除 %s 缺 blame 记录（修复指引：写明谁在何时为何删，保留事故疤痕）" % r.get("target")
            for r in removals if not str(r.get("blame") or "").strip()]
