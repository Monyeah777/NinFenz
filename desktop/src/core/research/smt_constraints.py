"""Optional SMT assignment (Z3 when available; backtracking fallback).

Z3 is a soft third-party import: the core stays stdlib-only when it is absent,
and the fallback uses the same required/one-to-one semantics.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.research import constraints

try:  # soft dependency: optional, never a hard core import
    import z3
    HAS_Z3 = True
except Exception:  # pragma: no cover
    z3 = None
    HAS_Z3 = False

SCHEMA = "nf-smt-assignment/1"


def assign_sections(sections: Sequence[str], slots: Sequence[constraints.Slot],
                    scores: dict[tuple[str, str], float] | None = None) -> dict[str, Any]:
    if not HAS_Z3:
        out = constraints.assign(sections, slots, scores)
        out["engine"] = "backtracking"
        return out
    if not sections or not slots:
        return {"schema": SCHEMA, "status": "error",
                "engine": "z3", "error": {"code": "EMPTY_INPUT"}}
    score = scores or {}
    x = {(i, j): z3.Bool(f"x_{i}_{j}") for i in range(len(sections))
         for j in range(len(slots))}
    opt = z3.Optimize()
    named = []
    for i in range(len(sections)):
        expr = z3.PbLe([(x[(i, j)], 1) for j in range(len(slots))], 1)
        opt.add(expr)
        named.append((f"section:{sections[i]}:one", expr))
    for j, slot in enumerate(slots):
        expr = z3.PbLe([(x[(i, j)], 1) for i in range(len(sections))], 1)
        opt.add(expr)
        named.append((f"slot:{slot.id}:one", expr))
        if slot.required:
            expr = z3.PbEq([(x[(i, j)], 1) for i in range(len(sections))], 1)
            opt.add(expr)
            named.append((f"slot:{slot.id}:required", expr))
    terms = [z3.If(x[(i, j)], z3.RealVal(round(score.get((sections[i], slots[j].id), 0.0), 4)),
                   z3.RealVal(0))
             for i in range(len(sections)) for j in range(len(slots))]
    opt.maximize(z3.Sum(terms))
    if opt.check() != z3.sat:
        probe = z3.Solver()
        probe.set(unsat_core=True)
        for name, expr in named:
            probe.assert_and_track(expr, name)
        core = ([str(c) for c in probe.unsat_core()]
                if probe.check() == z3.unsat else [])
        return {"schema": SCHEMA, "status": "unsat", "engine": "z3", "core": core}
    model = opt.model()
    mapping = {}
    for i, sec in enumerate(sections):
        for j, slot in enumerate(slots):
            if z3.is_true(model.eval(x[(i, j)], model_completion=True)):
                mapping[sec] = slot.id
    return {"schema": SCHEMA, "status": "sat", "engine": "z3",
            "assignment": mapping,
            "score": round(sum(score.get((s, t), 0.0) for s, t in mapping.items()), 6)}
