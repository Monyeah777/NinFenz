"""Pure App import/edit/export state machine.

The App must not show "success" for a state that was never persisted or for
an export that is not valid. This reducer is intentionally UI-free: Kotlin can
mirror it, tests pin the transitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

SCHEMA = "nf-app-state/1"


@dataclass(frozen=True)
class Slot:
    id: str
    value: str


@dataclass(frozen=True)
class Snapshot:
    status: str = "empty"  # empty|ready|error
    title: str = ""
    slots: tuple[Slot, ...] = ()
    issues: tuple[str, ...] = ()
    recipe_id: str | None = None
    exported: bool = False
    error: str | None = None
    saved: bool = False
    history: tuple[tuple[Slot, ...], ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class Step:
    snapshot: Snapshot
    accepted: bool
    error: str | None = None


def can_export(s: Snapshot) -> bool:
    return s.status == "ready" and bool(s.slots) and not s.issues


def reduce(s: Snapshot, event: dict[str, Any]) -> Step:
    kind = str(event.get("type", ""))
    if kind == "import_succeeded":
        slots = tuple(Slot(str(x["id"]), str(x.get("value", "")))
                      for x in event.get("slots", []))
        if not slots:
            return Step(s, False, "no_slots")
        return Step(Snapshot("ready", str(event.get("title", "")), slots,
                             tuple(str(x) for x in event.get("issues", [])),
                             event.get("recipe_id")), True)
    if kind == "edit_slot":
        sid = str(event.get("id", ""))
        if s.status != "ready" or not any(x.id == sid for x in s.slots):
            return Step(s, False, "unknown_slot")
        updated = tuple(Slot(x.id, str(event["value"])) if x.id == sid else x
                        for x in s.slots)
        return Step(replace(s, slots=updated, exported=False, saved=False,
                            issues=tuple(str(x) for x in event.get("issues", s.issues)),
                            history=s.history + (s.slots,)), True)
    if kind == "validation_failed":
        return Step(replace(s, issues=tuple(str(x) for x in event.get("issues", [])),
                            exported=False), True)
    if kind == "export_requested":
        if not can_export(s):
            return Step(s, False, "invalid")
        return Step(replace(s, exported=True), True)
    if kind == "save_succeeded":
        return Step(replace(s, saved=True), True)
    if kind == "undo":
        if not s.history:
            return Step(s, False, "no_history")
        return Step(replace(s, slots=s.history[-1], history=s.history[:-1],
                            exported=False, saved=False), True)
    if kind == "reset":
        return Step(Snapshot(), True)
    return Step(s, False, "unknown_event")
