"""Cross-field coherence invariants for the cognitive cockpit.

These checks establish internal consistency only. They do not estimate
semantic quality or rank alternatives.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _state_value(state: dict, key: str):
    artifact = state.get("artifact", {})
    return artifact.get(key, state.get(key))


def _invariant(name: str, issues: list[str]) -> dict:
    return {
        "id": name,
        "status": "fail" if issues else "pass",
        "issues": issues,
    }


def _parts_invariant(parts: list[str]) -> dict:
    return _invariant(
        "parts_distinct", [] if len(parts) == len(set(parts)) else ["duplicate parts"]
    )


def _relations_invariant(parts: list[str], relations: list[str]) -> dict:
    issues = [
        f"unanchored part: {part}"
        for part in parts
        if relations and not any(part in relation for relation in relations)
    ]
    return _invariant("relations_anchor_parts", issues)


def _plan_invariant(parts: list[str], plan: list[str]) -> dict:
    joined = "\n".join(plan)
    issues = [f"plan does not cover: {part}" for part in parts if plan and part not in joined]
    return _invariant("plan_covers_parts", issues)


def _verified_invariant(artifact: dict, evidence: list[str]) -> dict:
    issues = ["verified without evidence"] if artifact.get("verified") and not evidence else []
    return _invariant("verified_has_evidence", issues)


def _criteria_invariant(criteria) -> dict:
    if criteria is not None and not isinstance(criteria, list):
        return _invariant("criteria_shape", ["criteria must be an array"])
    issues = []
    for index, item in enumerate(criteria or []):
        if not isinstance(item, dict):
            issues.append(f"criteria[{index}] must be an object")
            continue
        if not item.get("dimension"):
            issues.append(f"criteria[{index}] missing dimension")
        if "threshold" not in item:
            issues.append(f"criteria[{index}] missing threshold")
    return _invariant("criteria_shape", issues)


def _verdict_invariant(audit, check, verdict) -> dict:
    issues = []
    if isinstance(verdict, dict):
        status = verdict.get("status")
        audit_issues = _strings(audit)
        if status not in {"pass", "fail"}:
            issues.append("verdict status must be pass or fail")
        if status == "pass" and check is not True:
            issues.append("pass verdict requires check=true")
        if status == "pass" and audit_issues:
            issues.append("pass verdict conflicts with audit issues")
        if status == "fail" and check is True and not audit_issues:
            issues.append("fail verdict lacks audit evidence")
    elif verdict is not None:
        issues.append("verdict must be an object")
    return _invariant("verdict_consistent", issues)


def _selection_invariant(options, selected) -> dict:
    issues = []
    if isinstance(selected, list) and isinstance(options, list):
        option_ids = {
            item.get("id")
            for item in options
            if isinstance(item, dict) and item.get("id") is not None
        }
        selected_ids = {
            item.get("id")
            for item in selected
            if isinstance(item, dict) and item.get("id") is not None
        }
        missing = sorted(str(item) for item in selected_ids - option_ids)
        if missing:
            issues.append("selected ids not in options: " + ",".join(missing))
    return _invariant("selection_from_options", issues)


def evaluate(state: dict) -> dict:
    artifact = state.get("artifact", {})
    parts = _strings(artifact.get("parts"))
    relations = _strings(artifact.get("relations"))
    plan = _strings(artifact.get("plan"))
    evidence = _strings(artifact.get("evidence"))
    invariants = [
        _parts_invariant(parts),
        _relations_invariant(parts, relations),
        _plan_invariant(parts, plan),
        _verified_invariant(artifact, evidence),
        _criteria_invariant(artifact.get("criteria")),
        _verdict_invariant(artifact.get("audit"), artifact.get("check"), artifact.get("verdict")),
        _selection_invariant(_state_value(state, "options"), artifact.get("selected")),
    ]

    result = {
        "schema": "nf-coherence/1",
        "status": "pass" if all(item["status"] == "pass" for item in invariants) else "fail",
        "invariants": invariants,
        "issues": [
            {"id": item["id"], "issue": issue}
            for item in invariants
            if item["status"] == "fail"
            for issue in item["issues"]
        ],
        "no_scoring": True,
    }
    result["digest"] = _digest({key: value for key, value in result.items() if key != "digest"})
    return result


def issues(state: dict) -> list[dict]:
    return evaluate(state)["issues"]


REPAIR_KEYS = {
    "parts_distinct": {"parts"},
    "relations_anchor_parts": {"relations"},
    "plan_covers_parts": {"plan"},
    "verified_has_evidence": {"evidence", "verified"},
    "criteria_shape": {"criteria"},
    "verdict_consistent": {"audit", "check", "verdict"},
    "selection_from_options": {"options", "selected"},
}


def repair_keys(state: dict) -> list[str]:
    return sorted({key for issue in issues(state) for key in REPAIR_KEYS.get(issue["id"], set())})


def new_issue_ids(before: dict, after: dict) -> list[str]:
    before_ids = {item["id"] for item in issues(before)}
    return sorted({item["id"] for item in issues(after) if item["id"] not in before_ids})
