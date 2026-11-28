"""多目标计划编译：共享前缀去重 + 独立分支并行阶段。"""

from __future__ import annotations

from . import atom_algebra as aa
from . import atom_planner as ap
from . import live_selector as ls


def writes(aid: str) -> set[str]:
    c = ls.CONTRACTS[aid]
    return set(c["adds"]) | set(c["removes"])


def _unique_atoms(plans: list[dict]) -> list[str]:
    atom_ids = []
    for p in plans:
        for a in p["cluster"]:
            if a not in atom_ids:
                atom_ids.append(a)
    return atom_ids


def _stage_build(ready: list[str]) -> list[str]:
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
    return stage or [ready[0]]


def _advance(produced: set[str], stage: list[str]) -> set[str]:
    updated = set(produced)
    for a in stage:
        updated |= set(ls.CONTRACTS[a]["adds"])
        updated -= set(ls.CONTRACTS[a]["removes"])
    return updated


def _stages(atom_ids: list[str], produced: set[str]) -> list[list[str]]:
    remaining = set(atom_ids)
    stages: list[list[str]] = []
    while remaining:
        ready = [a for a in sorted(remaining) if set(ls.CONTRACTS[a]["requires"]) <= produced]
        if not ready:
            raise ValueError(f"unreachable atoms: {sorted(remaining)}")
        stage = _stage_build(ready)
        produced = _advance(produced, stage)
        stages.append(stage)
        remaining -= set(stage)
    return stages


def compile_goals(s: dict, goals: list[str] | None = None, max_cost: int = 3) -> dict:
    plans = ap.plan_all(s, max_cost)
    if goals is not None:
        plans = [p for p in plans if p["goal"] in goals]
    atom_ids = _unique_atoms(plans)
    produced = ls.available_keys(s)
    stages = _stages(atom_ids, produced)
    expr = aa.IDENTITY
    if stages:
        parts = [
            aa.par(*[aa.atom(a) for a in st]) if len(st) > 1 else aa.atom(st[0]) for st in stages
        ]
        expr = aa.seq(*parts)
    return {"stages": stages, "expr": expr, "goals": [p["goal"] for p in plans]}
