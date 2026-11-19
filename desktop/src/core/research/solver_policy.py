"""Symbolic-first / LLM-fallback policy (ReaComp effi idea)."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "nf-solver-policy/1"


@dataclass
class Candidate:
    value: Any
    score: float
    source: str = "symbolic"


@dataclass
class Outcome:
    source: str
    best: Candidate | None
    candidates: list[Candidate] = field(default_factory=list)
    tokens: int = 0
    llm_called: bool = False


def solve(examples: Sequence[Any],
          symbolic: Callable[[Sequence[Any]], list[Candidate]],
          llm: Callable[[Sequence[Any]], tuple[list[Candidate], int]] | None = None,
          min_score: float = 1.0) -> Outcome:
    sym = [Candidate(c.value, c.score, "symbolic") for c in symbolic(examples)]
    best_sym = max(sym, key=lambda c: c.score) if sym else None
    if best_sym and best_sym.score >= min_score:
        return Outcome("symbolic", best_sym, sym, 0, False)
    if llm is None:
        return Outcome("symbolic_partial", best_sym, sym, 0, False)
    llm_cands, tokens = llm(examples)
    llm_cands = [Candidate(c.value, c.score, "llm") for c in llm_cands]
    pool = sym + llm_cands
    best = max(pool, key=lambda c: (c.score, c.source == "symbolic")) if pool else None
    source = "ensemble" if sym and llm_cands else ("llm" if llm_cands else "none")
    return Outcome(source, best, pool, tokens, True)
