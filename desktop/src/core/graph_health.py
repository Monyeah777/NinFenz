"""图健康三判据：根可达 / 出度边界 / 删除集为空（机制借鉴 buddygotchi validate.mjs:5-15）。

NF 的 concept_graph 现只判无环/悬空/自环；本模块补三条可证判据：
① 每个节点从根可达；② 出度不超过声明上界（无「万能节点」）；③ 删除任一节点后仍连通（无割点）。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


def _reachable(roots: Iterable[str], out: Dict[str, Set[str]]) -> Set[str]:
    seen: Set[str] = set()
    stack = [r for r in roots if r in out]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(out.get(n, set()))
    return seen


def analyze(nodes: Iterable[str], edges: Iterable[Any], roots: Iterable[str],
            max_out: int = 0) -> Dict[str, List[str]]:
    """→ {unreachable, over_out, articulation}（各为节点名列表）。"""
    names = list(dict.fromkeys(str(n) for n in nodes))
    out: Dict[str, Set[str]] = {n: set() for n in names}
    for e in edges:
        src, dst = (e.get("from"), e.get("to")) if isinstance(e, dict) else (e[0], e[1])
        src, dst = str(src), str(dst)
        if src in out:
            out[src].add(dst)
    reach = _reachable(roots, out)
    unreachable = [n for n in names if n not in reach]
    over = ([n for n in names if len(out[n]) > max_out] if max_out else [])
    articulation: List[str] = []
    for n in names:
        sub = {k: set(v) for k, v in out.items() if k != n}
        for v in sub.values():
            v.discard(n)
        rr = _reachable([r for r in roots if r != n], sub)
        if any(x not in rr and x != n for x in names):
            articulation.append(n)
    return {"unreachable": unreachable, "over_out": over, "articulation": articulation}
