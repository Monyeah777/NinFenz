"""多目标计划编译：共享前缀去重 + 独立分支并行阶段。"""

from __future__ import annotations

from . import atom_algebra as aa
from . import atom_planner as ap
from . import live_selector as ls


def writes(aid: str) -> set[str]:
    c = ls.CONTRACTS[aid]
    return set(c["adds"]) | set(c["removes"])


def compile_goals(s: dict, goals: list[str] | None = None, max_cost: int = 3) -> dict:
    plans = ap.plan_all(s, max_cost)
    if goals is not None:
        plans = [p for p in plans if p["goal"] in goals]
    atom_ids = []
    for p in plans:
        for a in p["cluster"]:
            if a not in atom_ids:
                atom_ids.append(a)

    produced = ls.available_keys(s)
    remaining = set(atom_ids)
    stages: list[list[str]] = []
    while remaining:
        ready = [a for a in sorted(remaining) if set(ls.CONTRACTS[a]["requires"]) <= produced]
        if not ready:
            raise ValueError(f"unreachable atoms: {sorted(remaining)}")
        stage: list[str] = []
        used_writes: set[str] = set()
        for a in ready:
            w = writes(a)
            if w & used_writes:
                continue
            if stage and not ap.compatible(tuple(stage + [a])):
                continue
            stage.append(a)
            used_writes |= w
        if not stage:
            stage = [ready[0]]
        for a in stage:
            produced |= set(ls.CONTRACTS[a]["adds"])
            produced -= set(ls.CONTRACTS[a]["removes"])
        stages.append(stage)
        remaining -= set(stage)

    expr = aa.IDENTITY
    if stages:
        parts = [
            aa.par(*[aa.atom(a) for a in st]) if len(st) > 1 else aa.atom(st[0]) for st in stages
        ]
        expr = aa.seq(*parts)
    return {"stages": stages, "expr": expr, "goals": [p["goal"] for p in plans]}
