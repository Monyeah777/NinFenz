"""Frozen view contracts for App/core boundaries.

These are the Python side of the App view model: immutable, JSON-roundtrip,
and explicit about required fields. Kotlin/TS types should be generated from
this shape rather than hand-maintained.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

IMPORT_SCHEMA = "nf-import-view/1"
PROJECT_SCHEMA = "nf-project-summary/1"


@dataclass(frozen=True)
class SlotView:
    id: str
    label: str
    value: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label,
                "value": self.value, "required": self.required}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlotView:
        return cls(str(data["id"]), str(data["label"]), str(data.get("value", "")),
                   bool(data.get("required", True)))


@dataclass(frozen=True)
class ImportView:
    state: str
    title: str
    slots: tuple[SlotView, ...] = ()
    issues: tuple[str, ...] = ()
    recipe_id: str | None = None
    recipe_version: int | None = None
    schema: str = field(default=IMPORT_SCHEMA, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "state": self.state, "title": self.title,
                "slots": [s.to_dict() for s in self.slots],
                "issues": list(self.issues),
                "recipe": ({"id": self.recipe_id, "version": self.recipe_version}
                           if self.recipe_id else None)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportView:
        if data.get("schema") != IMPORT_SCHEMA:
            raise ValueError("bad import view schema")
        recipe = data.get("recipe") or {}
        return cls(str(data["state"]), str(data["title"]),
                   tuple(SlotView.from_dict(s) for s in data.get("slots", [])),
                   tuple(str(x) for x in data.get("issues", [])),
                   recipe.get("id"), recipe.get("version"))


@dataclass(frozen=True)
class ProjectSummary:
    project_id: str
    title: str
    state: str
    mapped: int = 0
    recipe_id: str | None = None
    schema: str = field(default=PROJECT_SCHEMA, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "project_id": self.project_id,
                "title": self.title, "state": self.state,
                "mapped": self.mapped, "recipe_id": self.recipe_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectSummary:
        if data.get("schema") != PROJECT_SCHEMA:
            raise ValueError("bad project summary schema")
        return cls(str(data["project_id"]), str(data["title"]), str(data["state"]),
                   int(data.get("mapped", 0)), data.get("recipe_id"))
