"""反孤立门：定义必须被引用（机制借鉴 gdd check-references.mjs:57-70）。

NF 有「引用须在册」（judgement_coverage），本模块补**反向**：定义件/模块/模板
从未被任何件引用 → 孤立（死内容风险）。
"""
from __future__ import annotations

from typing import Dict, Iterable, List


def orphans(definitions: Iterable[str], references: Dict[str, List[str]]) -> List[str]:
    """definitions 中被引用次数为 0 的项。"""
    out = []
    for d in definitions:
        if not references.get(str(d)):
            out.append(str(d))
    return out


def dangling(references: Dict[str, List[str]], known: Iterable[str]) -> List[str]:
    """引用了不存在定义 → 悬空。"""
    have = {str(x) for x in known}
    return ["%s 引用了不存在的定义 %s（修复指引：补定义或改引用）" % (src, ref)
            for src, refs in references.items() for ref in refs if str(ref) not in have]
