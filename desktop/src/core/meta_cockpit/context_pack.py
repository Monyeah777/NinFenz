"""驾驶上下文包：候选相关方法卡、状态视图、来源摘要与无损预算。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from . import cognitive_cockpit as cc
from . import domain_sources, json_asset, method_memory, source_excerpts
from . import live_selector as ls

BASE = Path(__file__).parent
META_BYTES = (BASE / "meta_atoms.json").read_bytes()
CATALOG_DOC = json_asset.load_bytes(META_BYTES)
CATALOG = {item["id"]: item for item in CATALOG_DOC["atoms"]}
UNIT_LIMIT = 8000
PARTITION_LIMITS = {
    "method_cards": 1300,
    "state_view": 1800,
    "graph_slice": 2000,
    "references": 1000,
}
CARD_FIELDS = (
    "name",
    "function",
    "level_min",
    "level_max",
    "input",
    "output",
    "trigger",
    "failure_mode",
)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def estimate_units(value) -> int:
    """确定性 UTF-8/4 近似，只用于本地硬预算，不冒充厂商 tokenizer。"""
    return math.ceil(len(canonical(value)) / 4)


def compact_state(s: dict) -> dict:
    artifact = {
        key: value
        for key, value in s.get("artifact", {}).items()
        if value not in ("", [], {}, None, False) or key in ls.PRESENT_WHEN_EMPTY
    }
    return {
        "turn": int(s.get("turn", 0)),
        "artifact": artifact,
        "open_questions": list(s.get("open_questions", [])),
        "available_keys": sorted(ls.available_keys(s)),
        "unmet": ls.unmet(s),
        "method_history": method_memory.normalize_history(s),
    }


def method_cards(candidates: list[dict]) -> list[dict]:
    atom_ids = sorted({atom_id for candidate in candidates for atom_id in candidate["cluster"]})
    cards = []
    for atom_id in atom_ids:
        atom = CATALOG[atom_id]
        cards.append({"id": atom_id, **{key: atom[key] for key in CARD_FIELDS}})
    return cards


def graph_slice(s: dict) -> dict:
    parts = [str(item) for item in s.get("artifact", {}).get("parts", [])]
    anchors = sorted(set(parts))
    edges = []
    for part in anchors:
        for target in cc.REL_MAP.get(part, []):
            edges.append({"from": part, "to": target, "kind": "nf-mapping", "source": "REL_MAP"})
    for relation in s.get("artifact", {}).get("relations", []):
        text = str(relation)
        if "→" in text:
            left, right = [item.strip() for item in text.split("→", 1)]
            if left in anchors or right in anchors:
                edges.append(
                    {"from": left, "to": right, "kind": "state-relation", "source": "session-state"}
                )
    domain_entries = [
        domain_sources.BY_ID[reference["source"]]
        for reference in s.get("reference", [])
        if reference.get("source") in domain_sources.BY_ID
    ]
    domain_graph = domain_sources.graph_slice_for_text(s.get("goal", ""), domain_entries)
    edges += domain_graph["edges"]
    unique = {(edge["from"], edge["to"], edge["kind"], edge["source"]): edge for edge in edges}
    ordered_edges = [unique[key] for key in sorted(unique)]
    nodes = sorted(
        {edge["from"] for edge in ordered_edges}
        | {edge["to"] for edge in ordered_edges}
        | {node["concept"] for node in domain_graph["nodes"]}
    )
    return {
        "anchors": anchors,
        "nodes": nodes,
        "edges": ordered_edges,
        "matched_concepts": domain_graph["matched_concepts"],
        "domain_nodes": domain_graph["nodes"],
        "warnings": domain_graph["warnings"],
        "sources": domain_graph["sources"],
        "omission": {
            "reason": "one-hop NF neighborhood only",
            "unmapped_anchors": sorted(anchor for anchor in anchors if anchor not in cc.REL_MAP),
        },
    }


def build_context_pack(
    goal: str,
    s: dict,
    candidates: list[dict],
    providers: list | None = None,
    requested_roles: list[str] | None = None,
) -> dict:
    state = compact_state(s)
    cards = method_cards(candidates)
    graph = graph_slice(s)
    reference_ids = s.get("reference") or [
        {"source": "P03", "ref": "§1"},
        {"source": "NF-1", "ref": "§2"},
        {"source": "techdoc", "ref": "§1"},
    ]
    local_references = source_excerpts.select(s, reference_ids, requested_roles=requested_roles)
    provider_references = []
    provider_sources = []
    for provider in providers or []:
        provider_references += provider.search(goal, limit=1)
        provider_sources.append(
            {
                "id": provider.provider_id,
                "kind": "mcp-context-provider",
                "digest": provider.digest,
            }
        )
    references = (
        local_references[:3] + provider_references[:1] if provider_references else local_references
    )
    stable_prefix = {
        "schema": "nf-cockpit-prefix/1",
        "goal": goal,
        "choice_schema": "nf-constrained-choice/1",
        "constraints": {
            "max_atoms": 3,
            "max_cost": 3,
            "no_scoring": True,
            "no_full_plan": True,
            "thought_patch_mode": "optional",
        },
    }
    dynamic = {
        "state": state,
        "candidate_clusters": [candidate["cluster"] for candidate in candidates],
        "method_cards": [card["id"] for card in cards],
        "graph_slice": graph,
        "references": references,
    }
    sources = [
        {"id": "state", "kind": "session-state", "digest": digest(state)},
        {
            "id": "meta_atoms",
            "kind": "local-asset",
            "digest": hashlib.sha256(META_BYTES).hexdigest(),
        },
        {"id": "references", "kind": "nf-evidence-excerpts", "digest": digest(references)},
        {"id": "nf_relation_graph", "kind": "local-graph", "digest": digest(cc.REL_MAP)},
        {"id": "domain_index", "kind": "local-index", "digest": domain_sources.INDEX_DIGEST},
    ]
    sources += provider_sources
    partitions = {}
    for name, value in (
        ("method_cards", cards),
        ("state_view", state),
        ("graph_slice", graph),
        ("references", references),
    ):
        used = estimate_units(value)
        limit = PARTITION_LIMITS[name]
        if used > limit:
            raise ValueError(f"context budget exceeded: {name} partition {used} > {limit}")
        partitions[name] = {"estimated_units": used, "limit": limit}
    return {
        "schema": "nf-cockpit-context/1",
        "state_view": state,
        "method_cards": cards,
        "graph_slice": graph,
        "references": references,
        "stable_prefix_digest": digest(stable_prefix),
        "dynamic_digest": digest(dynamic),
        "sources": sources,
        "budget": {
            "unit": "utf8_bytes_div_4",
            "limit": UNIT_LIMIT,
            "estimated_units": 0,
            "lossless": True,
            "partitions": partitions,
        },
        "cache": {
            "prefix_eligible": True,
            "prefix_scope": "goal+protocol+constraints",
        },
    }


def enforce_budget(payload: dict, limit: int = UNIT_LIMIT) -> int:
    used = estimate_units(payload)
    if used > limit:
        raise ValueError(f"context budget exceeded: {used} > {limit}")
    return used
