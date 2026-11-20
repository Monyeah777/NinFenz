"""Capability tiers: Free / Pro / CCOS / Studio / TUI.

Free must never lock the daily path (import, preview, edit, export, share,
reset). Pro adds depth/scale/team/assurance. CCOS adds execution. Studio/TUI
are inspection/authoring hosts, not a separate entitlement.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "nf-tier-gate/1"
TIERS = ("free", "pro", "ccos", "studio", "tui")
FREE_ALWAYS = frozenset({
    "import", "preview", "edit", "validate_basic", "export", "share", "reset",
    "templates_basic", "ai_basic", "history_basic", "ocr_basic", "focus_mode",
})

PRO_ONLY = frozenset({
    "protocol_author", "pipeline_edit", "graph_edit", "pack_author",
    "bulk_projects", "constraints", "property_test", "lineage_audit",
    "experiments", "team_review", "prompt_compile", "ci_gate_tuning",
})

CCOS_ONLY = frozenset({
    "execute_task", "batch_execute", "provider_call", "scheduler",
    "evidence_trace", "budget_policy",
})

STUDIO_ONLY = frozenset({"studio_inspect", "tui_inspect"})


def _tier_set(tier: str) -> set[str]:
    if tier not in TIERS:
        raise ValueError("unknown tier: " + tier)
    base = set(FREE_ALWAYS)
    if tier in {"pro", "studio", "tui"}:
        base |= PRO_ONLY
    if tier == "ccos":
        base |= CCOS_ONLY
    if tier == "studio":
        base |= STUDIO_ONLY
    if tier == "tui":
        base |= {"tui_inspect"}
    return base


def check(tier: str, capability: str) -> dict[str, Any]:
    allowed = _tier_set(tier)
    ok = capability in allowed
    reason = "ok" if ok else ("free_path" if capability in FREE_ALWAYS
                              else "requires_higher_tier")
    return {"schema": SCHEMA, "tier": tier, "capability": capability,
            "allowed": ok, "reason": reason}


def require(tier: str, capability: str) -> None:
    out = check(tier, capability)
    if not out["allowed"]:
        raise PermissionError(tier + " cannot use " + capability)


def visible(tier: str) -> list[str]:
    return sorted(_tier_set(tier))
