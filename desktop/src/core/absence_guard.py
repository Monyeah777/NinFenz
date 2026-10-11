"""「未知 ≠ 不存在」守卫（机制借鉴 axiomcodegraph SKILL.md:43-81 / nuke AGENTS.md:53-54）。

检索面为空、判据无法判定时，结论**不得升格为本体论断言**（不存在/没有/无）；
必须写明检索边界与未解点。两条独立外部证据同向收敛，NF 侧 06 §6 只管
「跳过要有理由」，无「空结果不许写成不存在」的判据——本模块补该句的机读面。
"""
from __future__ import annotations

import re
from typing import List

_ABSENCE = re.compile(r"(不存在|没有|无此|未找到|均无|查无)")
_BOUNDARY = re.compile(r"(检索面|检索范围|查询范围|覆盖范围|边界|未解|下界|len\(|共\s*\d+\s*条|扫描了)")

_FIX = "补检索边界与未解点，或把断言改写成「本次检索未命中（下界）」"


def absence_claims(text: str) -> List[str]:
    """列出疑似「不存在」断言所在的句（按中文/英文句读切）。"""
    out: List[str] = []
    for clause in re.split(r"[。！？；\n]+", text or ""):
        c = clause.strip()
        if c and _ABSENCE.search(c):
            out.append(c)
    return out


def has_boundary(text: str) -> bool:
    """正文是否声明了检索边界/覆盖下界。"""
    return bool(_BOUNDARY.search(text or ""))


def check(text: str) -> List[str]:
    """无边界声明的缺席断言 → issue（带修复指引）。"""
    if has_boundary(text):
        return []
    return ["缺席断言缺检索边界：%s（修复指引：%s）" % (c[:60], _FIX) for c in absence_claims(text)]
