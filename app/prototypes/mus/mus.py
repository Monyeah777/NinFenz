"""M12 Constraint Satisfiability/MUS 参考原型。

只覆盖可判定的白名单约束；冲突用最小不可满足子集（MUS）表示。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable


@dataclass(frozen=True)
class Constraint:
    id: str
    kind: str
    field: str = ""
    value: object = None


def _by_field(constraints: list[Constraint]) -> dict[str, list[Constraint]]:
    out: dict[str, list[Constraint]] = {}
    for c in constraints:
        out.setdefault(c.field, []).append(c)
    return out


def satisfiable(constraints: Iterable[Constraint]) -> bool:
    items = list(constraints)
    for field, group in _by_field(items).items():
        min_chars = [c.value for c in group if c.kind == "min_chars"]
        max_chars = [c.value for c in group if c.kind == "max_chars"]
        required = any(c.kind == "required" for c in group)
        forbidden_empty = any(c.kind == "forbidden_empty" for c in group)
        includes = {c.value for c in group if c.kind == "must_include"}
        avoids = {c.value for c in group if c.kind == "must_avoid"}
        if required and forbidden_empty:
            return False
        if min_chars and max_chars and max(min_chars) > min(max_chars):
            return False
        if includes & avoids:
            return False
    return True


def minimal_conflicts(constraints: Iterable[Constraint]) -> list[tuple[Constraint, ...]]:
    items = list(constraints)
    if satisfiable(items):
        return []
    mus: list[tuple[Constraint, ...]] = []
    for size in range(1, len(items) + 1):
        for subset in combinations(items, size):
            if satisfiable(subset):
                continue
            if any(set(existing).issubset(set(subset)) for existing in mus):
                continue
            if all(satisfiable([c for c in subset if c != drop]) for drop in subset):
                mus.append(subset)
    return mus
