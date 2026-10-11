# -*- coding: utf-8 -*-
"""影响图（W-06/W-07）：core 模块导入图 → 反向可达闭包 → 专家影响集。

为什么复用 import_graph：导入图是**既有唯一实现**（含持久层与动态导入标记）；
本模块只在它上面加两件事——「反向算子」与「变更 → 受影响专家」，不另写一份解析。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set

from core import gate_faces as gf
from core import import_graph as ig


def module_deps(root: str = ".") -> Dict[str, FrozenSet[str]]:
    """core 模块导入图：{模块名: 依赖的 core 模块名集合}（解析不出者跳过）。"""
    out: Dict[str, FrozenSet[str]] = {}
    for fname, stamp in sorted(ig.listing(root).items()):
        stem = fname[:-3]
        got = ig.load_or_parse(root, stem, stamp)
        if got is None:
            continue
        _rel, deps, _dyn = got
        out[stem] = frozenset(deps)
    return out


def rdeps(dep_map: Dict[str, FrozenSet[str]], node: str) -> Set[str]:
    """反向依赖：直接依赖 node 的模块集合。"""
    return {m for m, ds in dep_map.items() if node in ds}


def closure(dep_map: Dict[str, FrozenSet[str]], seeds: Iterable[str]) -> Set[str]:
    """反向可达闭包：谁（传递地）依赖 seeds；含 seeds 自身（在图中者）。"""
    seen: Set[str] = {s for s in seeds if s in dep_map}
    queue: List[str] = sorted(seen)
    while queue:
        cur = queue.pop()
        for m in sorted(rdeps(dep_map, cur)):
            if m not in seen:
                seen.add(m)
                queue.append(m)
    return seen


def changed_modules(changed: Iterable[str]) -> Set[str]:
    """变更路径 → core 模块名（只认 desktop/src/core/<名>.py 这一种写法）。"""
    out: Set[str] = set()
    for c in (changed or []):
        parts = str(c).replace("\\", "/").split("/")
        if (len(parts) == 4 and parts[0] == "desktop" and parts[1] == "src"
                and parts[2] == "core" and parts[3].endswith(".py")):
            out.add(parts[3][:-3])
    return out


def affected_experts(root: str = ".", changed: Sequence[str] = (),
                     experts: Optional[Dict[str, Dict]] = None) -> Dict[str, str]:
    """→ {专家 id: 命中原因}；原因 ∈ 依赖闭包 / 读面命中。"""
    decl = experts if experts is not None else gf.load_manifest(root)
    affected_modules = closure(module_deps(root), changed_modules(changed))
    changed_n = [str(c).replace("\\", "/") for c in (changed or [])]
    out: Dict[str, str] = {}
    for eid, e in sorted(decl.items()):
        mod = str(e.get("module") or "").strip()
        stem = Path(mod).stem if mod else eid
        if stem in affected_modules:
            out[eid] = "依赖闭包"
            continue
        reads = [str(x) for x in (e.get("reads") or [])]
        if changed_n and any(gf.covered(c, reads) for c in changed_n):
            out[eid] = "读面命中"
    return out
