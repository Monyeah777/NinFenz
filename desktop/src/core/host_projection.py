"""多宿主投影：一份真源 → 多宿主副本，逐副本字节 parity（机制借鉴 MemVault check-rule-parity.sh）。

NF 的 agents-rules 出口与 check31 是**整体** golden；本模块补**逐宿主**比对：
每份副本必须与真源逐字节一致（或在显式允许差异清单内），且不得残留占位符。
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

_PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}|<TODO>|__PLACEHOLDER__")


def render(source: str, begin: str, end: str, body: str) -> str:
    """把 source 中 begin..end 区域替换为 body（marker 缺失 → raise）。"""
    if begin not in source or end not in source or source.index(begin) > source.index(end):
        raise ValueError("缺生成区标记或次序颠倒（修复指引：补 %s/%s 且 begin 在前）" % (begin, end))
    head = source[:source.index(begin) + len(begin)]
    tail = source[source.index(end):]
    return head + body + tail


def parity(canonical: str, mirrors: Dict[str, str], allow: Iterable[str] = ()) -> List[str]:
    """→ 与真源不一致（且不在 allow 内）或残留占位符的宿主清单。"""
    allowed = set(allow)
    issues: List[str] = []
    for host, text in mirrors.items():
        if _PLACEHOLDER.search(text):
            issues.append("宿主 %s 残留占位符（修复指引：渲染时替换全部占位符）" % host)
        if host in allowed:
            continue
        if text != canonical:
            issues.append("宿主 %s 与真源不一致（修复指引：重跑渲染；确属差异须登记进允许清单）" % host)
    return issues
