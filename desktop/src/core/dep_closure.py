"""传递依赖闭包 ⊆ 白名单（机制借鉴 tinychannels scripts/check-bus-purity.py）。

R5 只登记**直接** import 面；本模块补**传递闭包**：某层的依赖闭包里出现白名单外的
节点即报（含经由中间模块间接引入的情形）。纯函数，依赖图由调用方注入（单一来源）。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple


def closure(deps: Dict[str, Iterable[str]], roots: Iterable[str]) -> Set[str]:
    """roots 可达的全部节点（不含 roots 自身，除非被别的节点依赖）。"""
    out: Set[str] = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        for d in deps.get(n, ()):
            if d not in out:
                out.add(d)
                stack.append(d)
    return out


def offenders(deps: Dict[str, Iterable[str]], roots: Iterable[str],
              allowed: Iterable[str]) -> List[Tuple[str, str]]:
    """→ [(节点, 路径说明)]；路径说明给出「经由哪条链」以便修复。"""
    ok = set(allowed)
    bad: List[Tuple[str, str]] = []
    for root in roots:
        stack = [(root, [root])]
        seen = set()
        while stack:
            node, path = stack.pop()
            for d in deps.get(node, ()):
                if d in seen:
                    continue
                seen.add(d)
                if d not in ok:                      # 白名单节点仍要**继续下钻**，只是不报
                    bad.append((d, " → ".join(path + [d])))
                stack.append((d, path + [d]))
    return bad
