"""路径迁移映射表（机制借鉴 eunomia-bpf docs/MOVED.md:5034 行 old→new）。

NF 有 library 直链/llms.txt/site/GEO 导出，路径一改外部引用即断，而 NF 无路径面
迁移件（transform_log 管知识、§7 管实体 bump）。本模块给出映射并检出悬空/重复。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


def resolve(mapping: Dict[str, str], path: str) -> str:
    """沿映射链解析到终值（防自环）。"""
    seen = set()
    cur = path
    while cur in mapping and cur not in seen:
        seen.add(cur)
        cur = mapping[cur]
    return cur


def dangling(mapping: Dict[str, str], existing: Iterable[str]) -> List[str]:
    """新路径不在场 → 悬空。"""
    have = set(existing)
    return [("旧 %s → 新 %s（新路径不在场）" % (o, n)) for o, n in mapping.items() if n not in have]


def duplicates(mapping: Dict[str, str]) -> List[str]:
    """同一个新路径被多个旧路径指向 → 歧义。"""
    rev: Dict[str, List[str]] = {}
    for o, n in mapping.items():
        rev.setdefault(n, []).append(o)
    return ["新路径 %s 被多条旧路径指向：%s（修复指引：合并为一条）" % (n, ", ".join(olds))
            for n, olds in rev.items() if len(olds) > 1]


def cycles(mapping: Dict[str, str]) -> List[Tuple[str, ...]]:
    """映射链成环 → 排序/解析不确定。"""
    out: List[Tuple[str, ...]] = []
    for start in mapping:
        seen, cur, chain = set(), start, []
        while cur in mapping:
            if cur in seen:
                out.append(tuple(chain + [cur]))
                break
            seen.add(cur)
            chain.append(cur)
            cur = mapping[cur]
    return out
