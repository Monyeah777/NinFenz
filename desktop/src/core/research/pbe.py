"""Example-driven text-transform recipes (typed PBE slice).

The recipe is a chain of named Text -> Text ops learned from examples. Search is
bounded; candidates are ranked by matches, then length, then name, and deduped by
behaviour on the examples. This is the base-layer version of the slot PBE work:
it produces a small auditable program, not free-form model output.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)、])\s+")


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def bullets_to_semicolon(text: str) -> str:
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    items = [_BULLET.sub("", x).strip() for x in lines if _BULLET.match(x)]
    return "；".join(x for x in items if x) if items else collapse_ws(text)


def bullets_to_newline(text: str) -> str:
    lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
    items = [_BULLET.sub("", x).strip() for x in lines if _BULLET.match(x)]
    return "\n".join(x for x in items if x) if items else collapse_ws(text)


def first_sentence(text: str) -> str:
    clean = collapse_ws(text)
    m = re.search(r"^(.+?[。！？!?])", clean)
    return m.group(1).strip() if m else clean


def strip_bullets(text: str) -> str:
    return "\n".join(_BULLET.sub("", x.strip()).strip()
                     for x in (text or "").splitlines() if x.strip())


OPS = {
    "collapse_ws": collapse_ws,
    "bullets_to_semicolon": bullets_to_semicolon,
    "bullets_to_newline": bullets_to_newline,
    "first_sentence": first_sentence,
    "strip_bullets": strip_bullets,
}


@dataclass(frozen=True)
class Example:
    source: str
    expected: str


@dataclass(frozen=True)
class Program:
    ops: tuple[str, ...]

    def apply(self, text: str) -> str:
        value = text
        for name in self.ops:
            value = OPS[name](value)
        return value

    @property
    def name(self) -> str:
        return " → ".join(self.ops)


@dataclass(frozen=True)
class Result:
    program: Program | None
    matched: int
    total: int
    candidates: int

    @property
    def exact(self) -> bool:
        return self.program is not None and self.matched == self.total


def _evaluate(program: Program, examples: Sequence[Example]) -> tuple[int, tuple[str, ...]]:
    outputs = tuple(collapse_ws(program.apply(ex.source)) for ex in examples)
    matched = sum(1 for ex, out in zip(examples, outputs, strict=True)
                  if out == collapse_ws(ex.expected))
    return matched, outputs


def learn(examples: Iterable[Example], max_length: int = 2) -> Result:
    ex = list(examples)
    if not ex:
        raise ValueError("examples must not be empty")
    if max_length < 1:
        raise ValueError("max_length must be >= 1")
    names = list(OPS)
    programs: list[Program] = [Program((n,)) for n in names]
    if max_length >= 2:
        programs += [Program((a, b)) for a in names for b in names if a != b]
    scored = []
    seen: set[tuple[str, ...]] = set()
    for prog in programs:
        matched, behavior = _evaluate(prog, ex)
        if behavior in seen:
            continue
        seen.add(behavior)
        scored.append((matched, prog))
    scored.sort(key=lambda x: (-x[0], len(x[1].ops), x[1].name))
    best = scored[0][1] if scored else None
    matched = scored[0][0] if scored else 0
    return Result(best, matched, len(ex), len(scored))


def to_recipe(result: Result) -> dict[str, Any]:
    if not result.exact:
        raise ValueError("cannot serialize a non-exact recipe")
    return {"schema": "nf-pbe-recipe/1", "ops": list(result.program.ops),
            "examples": result.total, "matched": result.matched}
