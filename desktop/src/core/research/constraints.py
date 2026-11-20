"""Small constraint assignment: one section -> one slot, required coverage.

Exhaustive for small inputs (n <= 8), greedy fallback after that. Scores are
maximized; unsat returns the required slot ids that cannot be covered.
"""
from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

SCHEMA = "nf-constraint-assignment/1"


@dataclass(frozen=True)
class Slot:
    id: str
    required: bool = True


def assign(sections: Sequence[str], slots: Sequence[Slot],
           scores: dict[tuple[str, str], float] | None = None) -> dict[str, Any]:
    if not sections or not slots:
        return {"schema": SCHEMA, "status": "error",
                "error": {"code": "EMPTY_INPUT"}}
    score = scores or {}
    required = [s.id for s in slots if s.required]
    if len(required) > len(sections):
        return {"schema": SCHEMA, "status": "unsat", "core": required}
    if len(sections) <= 8:
        best: tuple[float, dict[str, str]] | None = None
        for combo in itertools.permutations([s.id for s in slots], len(sections)):
            mapping = dict(zip(sections, combo, strict=True))
            if not all(r in mapping.values() for r in required):
                continue
            total = sum(score.get((a, b), 0.0) for a, b in mapping.items())
            if best is None or total > best[0]:
                best = (total, mapping)
        if best is None:
            return {"schema": SCHEMA, "status": "unsat", "core": required}
        return {"schema": SCHEMA, "status": "sat", "assignment": best[1],
                "score": round(best[0], 6)}
    mapping: dict[str, str] = {}
    available = [s.id for s in slots]
    for sec in sections:
        if not available:
            break
        choice = max(available, key=lambda sid: score.get((sec, sid), 0.0))
        mapping[sec] = choice
        available.remove(choice)
    if not all(r in mapping.values() for r in required):
        return {"schema": SCHEMA, "status": "unsat", "core": required}
    return {"schema": SCHEMA, "status": "sat", "assignment": mapping,
            "score": round(sum(score.get((a, b), 0.0) for a, b in mapping.items()), 6)}
