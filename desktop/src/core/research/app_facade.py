"""App-facing facade over the pure state machine and contracts.

The UI should not mutate snapshots directly. It calls these operations; each
returns a contract view or an explicit rejection. Export is gated by state, not
by a button's enabled flag.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.research import app_state, app_state_persist, contracts, tier_gate

SCHEMA = "nf-app-facade/1"


class AppFacade:
    def __init__(self, tier: str = "free", state_path: str | Path | None = None) -> None:
        if tier not in tier_gate.TIERS:
            raise ValueError("unknown tier: " + tier)
        self.tier = tier
        self.state_path = Path(state_path) if state_path else None
        self.state = app_state.Snapshot()

    def open_import(self, title: str, slots: list[dict[str, Any]],
                  issues: list[str] | None = None,
                  recipe_id: str | None = None) -> dict[str, Any]:
        step = app_state.reduce(self.state, {
            "type": "import_succeeded", "title": title, "slots": slots,
            "issues": issues or [], "recipe_id": recipe_id})
        if not step.accepted:
            return {"schema": SCHEMA, "ok": False, "error": step.error}
        self.state = step.snapshot
        return {"schema": SCHEMA, "ok": True, "view": self.view()}

    def edit_slot(self, slot_id: str, value: str,
                  issues: list[str] | None = None) -> dict[str, Any]:
        step = app_state.reduce(self.state, {
            "type": "edit_slot", "id": slot_id, "value": value,
            "issues": issues if issues is not None else self.state.issues})
        if not step.accepted:
            return {"schema": SCHEMA, "ok": False, "error": step.error}
        self.state = step.snapshot
        return {"schema": SCHEMA, "ok": True, "view": self.view()}

    def validate(self, issues: list[str]) -> dict[str, Any]:
        step = app_state.reduce(self.state, {"type": "validation_failed",
                                             "issues": issues})
        self.state = step.snapshot
        return {"schema": SCHEMA, "ok": True, "view": self.view()}

    def export(self) -> dict[str, Any]:
        gate = tier_gate.check(self.tier, "export")
        if not gate["allowed"]:
            return {"schema": SCHEMA, "ok": False, "error": gate["reason"]}
        step = app_state.reduce(self.state, {"type": "export_requested"})
        if not step.accepted:
            return {"schema": SCHEMA, "ok": False, "error": step.error}
        self.state = step.snapshot
        return {"schema": SCHEMA, "ok": True, "exported": True}

    def save(self) -> dict[str, Any]:
        if self.state_path is None:
            return {"schema": SCHEMA, "ok": False, "error": "no_state_path"}
        app_state_persist.save(self.state_path, self.state)
        step = app_state.reduce(self.state, {"type": "save_succeeded"})
        self.state = step.snapshot
        return {"schema": SCHEMA, "ok": True, "path": str(self.state_path)}

    def load(self) -> dict[str, Any]:
        if self.state_path is None:
            return {"schema": SCHEMA, "ok": False, "error": "no_state_path"}
        try:
            self.state = app_state_persist.load(self.state_path)
        except (OSError, ValueError) as exc:
            return {"schema": SCHEMA, "ok": False, "error": str(exc)}
        return {"schema": SCHEMA, "ok": True, "view": self.view()}

    def reset(self) -> dict[str, Any]:
        self.state = app_state.reduce(self.state, {"type": "reset"}).snapshot
        return {"schema": SCHEMA, "ok": True}

    def view(self) -> dict[str, Any]:
        payload = contracts.ImportView(
            self.state.status, self.state.title,
            tuple(contracts.SlotView(x.id, x.id, x.value) for x in self.state.slots),
            self.state.issues, self.state.recipe_id, None,
        )
        out = payload.to_dict()
        out["exported"] = self.state.exported
        out["saved"] = self.state.saved
        return out
