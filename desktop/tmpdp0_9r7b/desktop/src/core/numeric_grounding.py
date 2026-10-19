"""数字接地检查：答案里的数字须能在来源里找到（机制借鉴 311-analytics-agent number_check.py:28-64）。

越界数字只标注不丢件（与 grounding 同一哲学：不丢件，先暴露）。
"""
from __future__ import annotations

import re
from typing import Iterable, List, Set

_NUM = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> Set[str]:
    return set(_NUM.findall(text or ""))


def ungrounded(text: str, sources: Iterable[str]) -> List[str]:
    """正文里出现、但所有来源中都不出现的数字。"""
    have: Set[str] = set()
    for s in sources:
        have |= _numbers(s)
    return sorted(_numbers(text) - have)


def check(text: str, sources: Iterable[str]) -> List[str]:
    return ["数字未接地：%s（修复指引：给出计算来源或改写成非具体数）" % n for n in ungrounded(text, sources)]
