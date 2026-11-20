"""PROV-style entity/activity/agent graph with directional lineage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA = "nf-lineage/1"


@dataclass
class ProvGraph:
    entities: set[str] = field(default_factory=set)
    activities: set[str] = field(default_factory=set)
    agents: set[str] = field(default_factory=set)
    relations: list[dict[str, str]] = field(default_factory=list)

    def entity(self, ident: str) -> str:
        self.entities.add(ident)
        return ident

    def activity(self, ident: str) -> str:
        self.activities.add(ident)
        return ident

    def agent(self, ident: str) -> str:
        self.agents.add(ident)
        return ident

    def used(self, activity: str, entity: str) -> None:
        self.relations.append({"type": "used", "from": activity, "to": entity})

    def generated(self, entity: str, activity: str) -> None:
        self.relations.append({"type": "wasGeneratedBy", "from": entity, "to": activity})

    def derived(self, generated: str, used: str) -> None:
        self.relations.append({"type": "wasDerivedFrom", "from": generated, "to": used})

    def attributed(self, entity: str, agent: str) -> None:
        self.relations.append({"type": "wasAttributedTo", "from": entity, "to": agent})

    def nodes(self) -> set[str]:
        return self.entities | self.activities | self.agents

    def lineage(self, start: str, direction: str = "backward",
                depth: int | None = None) -> dict[str, Any]:
        if start not in self.nodes():
            return {"schema": SCHEMA, "status": "error", "error": "unknown node"}
        adj: dict[str, list[dict[str, str]]] = {}
        for rel in self.relations:
            a, b = rel["from"], rel["to"]
            if direction == "forward":
                a, b = b, a
            adj.setdefault(a, []).append({"from": a, "to": b, "type": rel["type"]})
        seen, frontier, queue = {start}, set(), [(start, 0)]
        edges: list[dict[str, str]] = []
        while queue:
            node, dist = queue.pop(0)
            if depth is not None and dist >= depth:
                frontier.add(node)
                continue
            for edge in adj.get(node, []):
                if edge not in edges:
                    edges.append(edge)
                nxt = edge["to"]
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
        return {"schema": SCHEMA, "status": "ok", "start": start,
                "direction": direction, "nodes": sorted(seen),
                "edges": edges, "frontier": sorted(frontier)}
