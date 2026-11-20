"""Persist/restore the pure App snapshot with an explicit schema.

No auto-restore: callers must load explicitly. Corrupt/unknown schema fails
closed instead of silently starting empty.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from core.research.app_state import Slot, Snapshot

STATE_SCHEMA = "nf-app-state-file/1"


def to_dict(s: Snapshot) -> dict[str, Any]:
    return {"schema": STATE_SCHEMA, "status": s.status, "title": s.title,
            "slots": [{"id": x.id, "value": x.value} for x in s.slots],
            "issues": list(s.issues), "recipe_id": s.recipe_id,
            "exported": s.exported, "saved": s.saved, "error": s.error}


def from_dict(data: dict[str, Any]) -> Snapshot:
    if data.get("schema") != STATE_SCHEMA:
        raise ValueError("bad app state schema")
    status = str(data.get("status", ""))
    if status not in {"empty", "ready", "error"}:
        raise ValueError("bad app status: " + status)
    slots = tuple(Slot(str(x["id"]), str(x.get("value", "")))
                  for x in data.get("slots", []))
    if status == "empty" and slots:
        raise ValueError("empty state cannot carry slots")
    return Snapshot(status, str(data.get("title", "")), slots,
                    tuple(str(x) for x in data.get("issues", [])),
                    data.get("recipe_id"), bool(data.get("exported", False)),
                    data.get("error"), bool(data.get("saved", False)))


def save(path: str | Path, s: Snapshot) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".nf-app-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(to_dict(s), fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(path: str | Path) -> Snapshot:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("app state must be an object")
    return from_dict(data)
