"""Structured abstention and repair reporting for cockpit handoff."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import coherence, task_profile


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


_NEEDS = frozenset(
    {
        "structure",
        "relations",
        "risks",
        "synthesis",
        "grounding",
        "resolve",
    }
)
_EVIDENCE_GAPS = frozenset(
    {
        "evidence-without-excerpt",
        "unsupported-evidence",
        "domain-scope-only",
        "verified-without-grounded-evidence",
        "ungrounded-synthesis",
    }
)


def _facet_reason(facet: dict, gap: str) -> tuple[dict, list[str]]:
    facet_id = gap.split(":", 1)[1]
    item = next(
        (candidate for candidate in facet["items"] if candidate["facet"] == facet_id), None
    )
    keys = sorted(
        {key for witness in (item["witnesses"] if item else []) for key in witness["keys"]}
    )
    return {"gap": gap, "kind": "task-facet", "repair_keys": keys}, keys


def _gap_reason(state: dict, facet: dict, gap: str) -> tuple[dict, list[str]]:
    """单个 gap 的归因（kind + repair_keys），顺序与原分支链一致。"""
    if gap.startswith("task-facet:"):
        return _facet_reason(facet, gap)
    if gap.startswith("coherence:"):
        keys = coherence.repair_keys(state)
        return {"gap": gap, "kind": "coherence", "repair_keys": keys}, keys
    if gap in _NEEDS:
        return {"gap": gap, "kind": "cognitive-need", "repair_keys": []}, []
    if gap in _EVIDENCE_GAPS:
        return {"gap": gap, "kind": "evidence", "repair_keys": ["evidence"]}, ["evidence"]
    return {"gap": gap, "kind": "review", "repair_keys": []}, []


def _status_of(termination: str, reasons: list[dict]) -> str:
    if termination == "context-budget-exceeded":
        return "budget-exhausted"
    if termination in {"deadline", "deadline-exceeded"}:
        return "deadline-exceeded"
    if termination in {"blocked", "policy-stop", "no-progress", "state-cycle"}:
        return "blocked"
    if any(item["kind"] == "evidence" for item in reasons):
        return "evidence-required"
    if any(item["kind"] in {"task-facet", "coherence", "cognitive-need"} for item in reasons):
        return "repair-required"
    if reasons:
        return "review-required"
    return "none"


def build(state: dict, gaps: list[str], termination: str = "done") -> dict:
    reasons = []
    repair_keys: set[str] = set()
    facet = task_profile.build_facet_agenda(state)
    for gap in gaps:
        reason, keys = _gap_reason(state, facet, gap)
        repair_keys.update(keys)
        reasons.append(reason)
    status = _status_of(termination, reasons)
    result = {
        "schema": "nf-abstention/1",
        "status": status,
        "termination": termination,
        "repairable": status == "repair-required",
        "human_action_required": status
        in {
            "budget-exhausted",
            "deadline-exceeded",
            "blocked",
            "evidence-required",
            "review-required",
        },
        "repair_keys": sorted(repair_keys),
        "reasons": reasons,
        "semantic_verification": "pending-human-review",
        "no_scoring": True,
    }
    result["digest"] = _digest({key: value for key, value in result.items() if key != "digest"})
    return result
