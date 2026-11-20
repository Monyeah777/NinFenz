"""Human/agent collaboration session: shared log, public/private, confirmation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "nf-collab/1"
SENSITIVE = {"publish", "export", "share", "delete"}


@dataclass
class Session:
    participants: list[str]
    events: list[dict[str, Any]] = field(default_factory=list)
    pending: dict[int, dict[str, Any]] = field(default_factory=dict)
    asked: int = 0
    answered: int = 0
    interventions: int = 0
    _next: int = 1

    def step(self, role: str, kind: str, payload: Any = None,
             private: bool = False) -> dict[str, Any]:
        if role not in self.participants:
            return {"status": "error", "error": "unknown role"}
        if kind in SENSITIVE:
            pid = self._next
            self._next += 1
            self.pending[pid] = {"role": role, "kind": kind, "payload": payload}
            self.asked += 1
            self._record(role, "confirmation_request", {"id": pid, "kind": kind})
            return {"status": "needs_confirmation", "id": pid}
        self._record(role, kind, payload, private)
        return {"status": "ok"}

    def confirm(self, role: str, action_id: int, approve: bool = True) -> dict[str, Any]:
        item = self.pending.pop(action_id, None)
        if not item:
            return {"status": "error", "error": "no pending"}
        self.answered += 1
        if not approve:
            self._record(role, "rejected", {"id": action_id})
            return {"status": "rejected"}
        self._record(role, "confirmed", {"id": action_id})
        self._record(item["role"], item["kind"], item["payload"])
        return {"status": "ok"}

    def intervene(self, role: str, reason: str) -> dict[str, Any]:
        if role not in self.participants:
            return {"status": "error", "error": "unknown role"}
        self.interventions += 1
        self._record(role, "intervention", reason)
        return {"status": "ok"}

    def _record(self, role: str, kind: str, payload: Any = None,
                private: bool = False) -> None:
        self.events.append({"seq": len(self.events) + 1, "role": role,
                            "kind": kind, "payload": payload, "private": private})

    def visible_to(self, role: str) -> list[dict[str, Any]]:
        return [e for e in self.events if not e["private"] or e["role"] == role]

    def initiative_entropy(self) -> float:
        counts: dict[str, int] = {}
        for e in self.events:
            if e["kind"] in {"confirmation_request", "confirmed", "rejected", "intervention"}:
                continue
            counts[e["role"]] = counts.get(e["role"], 0) + 1
        total = sum(counts.values())
        if total == 0 or len(counts) <= 1:
            return 0.0
        h = -sum((c / total) * math.log(c / total) for c in counts.values())
        return h / math.log(len(counts))

    def controlled_autonomy(self) -> dict[str, int]:
        return {"confirmations_asked": self.asked,
                "confirmations_answered": self.answered,
                "interventions": self.interventions}
