"""Revisioned query memo with backdating and durability (Salsa idea, tiny core).

A query is pure; dependencies are captured while it runs. On a new revision a
memo is reused only when every dependency's changed_at <= verified_at. If the
new value equals the old value, changed_at is backdated, so downstream queries
can still reuse their memo.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

SCHEMA = "nf-incremental/1"


class Durability(IntEnum):
    LOW = 0
    HIGH = 1


@dataclass
class _Memo:
    value: Any
    changed_at: int
    verified_at: int
    deps: set[tuple[Any, ...]] = field(default_factory=set)
    durability: Durability = Durability.LOW


class Database:
    def __init__(self) -> None:
        self.revision = 1
        self.inputs: dict[str, tuple[Any, int, Durability]] = {}
        self.memos: dict[tuple[Any, ...], _Memo] = {}
        self._stack: list[set[tuple[Any, ...]]] = []
        self.executions: list[str] = []
        self.backdated = 0

    def set_input(self, name: str, value: Any,
                  durability: Durability = Durability.LOW) -> None:
        old = self.inputs.get(name)
        if old and old[0] == value and old[2] == durability:
            return
        self.revision += 1
        self.inputs[name] = (value, self.revision, durability)

    def input(self, name: str) -> Any:
        self._record(("input", name))
        return self.inputs[name][0]

    def _record(self, dep: tuple[Any, ...]) -> None:
        if self._stack:
            self._stack[-1].add(dep)

    def query(self, name: str, fn: Callable[[Database, Any], Any], *args: Any,
              durability: Durability = Durability.LOW) -> Any:
        key = (name, repr(args))
        memo = self.memos.get(key)
        if memo and self._fresh(memo):
            return memo.value
        frame: set[tuple[Any, ...]] = set()
        self._stack.append(frame)
        try:
            value = fn(self, *args)
        finally:
            self._stack.pop()
        self.executions.append(name)
        if self._stack:
            self._stack[-1].add(("query", key))
        changed_at = self.revision
        if memo and memo.value == value:
            changed_at = memo.changed_at
            self.backdated += 1
        self.memos[key] = _Memo(value, changed_at, self.revision, frame, durability)
        return value

    def _fresh(self, memo: _Memo) -> bool:
        for dep in memo.deps:
            if dep[0] == "input":
                changed = self.inputs[dep[1]][1]
            else:
                other = self.memos.get(dep[1])
                changed = other.changed_at if other else 0
            if changed > memo.verified_at:
                return False
        memo.verified_at = self.revision
        return True

    def stats(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "revision": self.revision,
                "memos": len(self.memos), "executions": len(self.executions),
                "backdated": self.backdated}
