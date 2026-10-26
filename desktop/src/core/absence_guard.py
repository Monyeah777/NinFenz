"""「未知 ≠ 不存在」守卫（机制借鉴 axiomcodegraph SKILL.md:43-81 / nuke AGENTS.md:53-54）。

检索面为空、判据无法判定时，结论**不得升格为本体论断言**（不存在/没有/无）；
必须写明检索边界与未解点。两条独立外部证据同向收敛，NF 侧 06 §6 只管
「跳过要有理由」，无「空结果不许写成不存在」的判据——本模块补该句的机读面。
"""
from __future__ import annotations

import re
from typing import List

MAX_GUARD_CHARS = 1_000_000
_ABSENCE = re.compile(
    r"(不存在|没有|无此|未找到|均无|查无|\bnot\s+found\b|\bdoes(?:n't| not)\s+exist\b"
    r"|\bno\s+such\b|\babsent\b)", re.I)
_BOUNDARY = re.compile(r"(检索面|检索范围|查询范围|覆盖范围|边界|未解|下界|len\(|共\s*\d+\s*条|扫描了)")
_NEGATION = re.compile(
    r"(并非|不是|not\s+(?:really\s+)?(?:absent|missing|nonexistent|true))", re.I)

_FIX = "补检索边界与未解点，或把断言改写成「本次检索未命中（下界）」"


def absence_claims(text: str) -> List[str]:
    """列出疑似「不存在」断言所在的句（按中文/英文句读切）。"""
    out: List[str] = []
    for clause in _clauses(text):
        c = clause.strip()
        if c and _ABSENCE.search(c):
            out.append(c)
    return out


def _clauses(text: str) -> List[str]:
    return re.split(r"(?<=[.!?])\s+|[。！？；\n]+", text or "")


def has_boundary(text: str) -> bool:
    """正文是否声明了检索边界/覆盖下界。"""
    return bool(_BOUNDARY.search(text or ""))


def check(text: str) -> List[str]:
    """**按句上下文**判缺席断言：同句/相邻句有边界才放行（防全局豁免污染）。"""
    if not text:
        return []
    body = text[:MAX_GUARD_CHARS]
    clauses = _clauses(body)
    issues: List[str] = []
    for i, clause in enumerate(clauses):
        c = clause.strip()
        if not c or not _ABSENCE.search(c) or _NEGATION.search(c):
            continue
        window = " ".join(clauses[max(0, i - 1):i + 2])
        if has_boundary(window):
            continue
        issues.append("缺席断言缺检索边界：%s（修复指引：%s）" % (c[:60], _FIX))
    if len(text) > MAX_GUARD_CHARS:
        issues.append("正文超过 %d 字符，仅扫描前段（修复指引：分块提交或先声明检索边界）"
                      % MAX_GUARD_CHARS)
    return issues
