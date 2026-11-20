"""Bounded string extraction from examples: after/before/between markers + regex.

The candidate set is explicit and small; a program is only returned when it
reproduces every example. No LLM, no network, no eval.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

Extractor = Callable[[str], str]


@dataclass(frozen=True)
class ExtractExample:
    source: str
    expected: str


@dataclass(frozen=True)
class ExtractProgram:
    kind: str
    args: tuple[str, ...]

    def apply(self, text: str) -> str:
        if self.kind == "after":
            marker = self.args[0]
            pos = text.find(marker)
            return "" if pos < 0 else text[pos + len(marker):]
        if self.kind == "before":
            pos = text.find(self.args[0])
            return "" if pos < 0 else text[:pos]
        if self.kind == "between":
            left, right = self.args
            i = text.find(left)
            j = text.find(right, i + len(left)) if i >= 0 else -1
            return "" if i < 0 or j < 0 else text[i + len(left):j]
        if self.kind == "regex":
            m = re.search(self.args[0], text)
            return m.group(0) if m else ""
        raise ValueError("unknown extractor " + self.kind)

    @property
    def name(self) -> str:
        return self.kind + "(" + ", ".join(repr(a) for a in self.args) + ")"


def _markers(examples: Sequence[ExtractExample]) -> list[str]:
    found = set()
    for ex in examples:
        for ch in ex.source + ex.expected:
            if not ch.isalnum() and not ch.isspace():
                found.add(ch)
    return sorted(found)


def candidates(examples: Sequence[ExtractExample]) -> list[ExtractProgram]:
    marks = _markers(examples) + [":", ": ", "\n", "："]
    out: list[ExtractProgram] = []
    for m in dict.fromkeys(marks):
        out.append(ExtractProgram("after", (m,)))
        out.append(ExtractProgram("before", (m,)))
    for a in dict.fromkeys(marks):
        for b in dict.fromkeys(marks):
            if a != b:
                out.append(ExtractProgram("between", (a, b)))
    for pattern in (r"\d+", r"[A-Za-z]+", r"[\w]+"):
        out.append(ExtractProgram("regex", (pattern,)))
    return out


def learn(examples: Iterable[ExtractExample]) -> dict[str, Any]:
    ex = list(examples)
    if not ex:
        raise ValueError("examples must not be empty")
    for prog in candidates(ex):
        if all(prog.apply(e.source) == e.expected for e in ex):
            return {"schema": "nf-string-extract/1", "status": "ok",
                    "program": prog.name, "examples": len(ex),
                    "outputs": [prog.apply(e.source) for e in ex]}
    return {"schema": "nf-string-extract/1", "status": "no_solution",
            "examples": len(ex)}
