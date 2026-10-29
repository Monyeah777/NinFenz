"""Structured abstention and repair reporting for cockpit handoff."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from . import coherence, task_profile

STATUS_ORDER = (
    "budget-exhausted",
    "deadline-exceeded",
    "blocked",
    "evidence-required",
    "repair-required",
    "review-required",
    "none",
)


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build(state: dict, gaps: list[str], termination: str = "done") -> dict:
    reasons = []
    repair_keys: set[str] = set()
    facet = task_profile.build_facet_agenda(state)
    needs = {
        "structure",
        "relations",
        "risks",
        "synthesis",
        "grounding",
        "resolve",
    }
    for gap in gaps:
        if gap.startswith("task-facet:"):
            facet_id = gap.split(":", 1)[1]
            item = next(
                (candidate for candidate in facet["items"] if candidate["facet"] == facet_id), None
            )
            keys = sorted(
                {key for witness in (item["witnesses"] if item else []) for key in witness["keys"]}
            )
            repair_keys.update(keys)
            reasons.append(
                {
                    "gap": gap,
                    "kind": "task-facet",
                    "repair_keys": keys,
                }
            )
        elif gap.startswith("coherence:"):
            keys = coherence.repair_keys(state)
            repair_keys.update(keys)
            reasons.append(
                {
                    "gap": gap,
                    "kind": "coherence",
                    "repair_keys": keys,
                }
            )
        elif gap in needs:
            reasons.append(
                {
                    "gap": gap,
                    "kind": "cognitive-need",
                    "repair_keys": [],
                }
            )
        elif gap in {
            "evidence-without-excerpt",
            "unsupported-evidence",
            "domain-scope-only",
            "verified-without-grounded-evidence",
            "ungrounded-synthesis",
        }:
            reasons.append(
                {
                    "gap": gap,
                    "kind": "evidence",
                    "repair_keys": ["evidence"],
                }
            )
            repair_keys.add("evidence")
        else:
            reasons.append(
                {
                    "gap": gap,
                    "kind": "review",
                    "repair_keys": [],
                }
            )

    if termination == "context-budget-exceeded":
        status = "budget-exhausted"
    elif termination in {"deadline", "deadline-exceeded"}:
        status = "deadline-exceeded"
    elif termination in {"blocked", "policy-stop", "no-progress", "state-cycle"}:
        status = "blocked"
    elif any(item["kind"] == "evidence" for item in reasons):
        status = "evidence-required"
    elif any(item["kind"] in {"task-facet", "coherence", "cognitive-need"} for item in reasons):
        status = "repair-required"
    elif reasons:
        status = "review-required"
    else:
        status = "none"

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
