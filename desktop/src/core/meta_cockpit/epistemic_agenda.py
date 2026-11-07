"""Epistemic obligations for the live cockpit.

The agenda is deliberately not a score. It records whether the current
artifact contains the witness required to close a cognitive obligation.
Models may propose a bounded thought patch; this module validates its shape
and the runtime checks closure after applying it.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from . import live_selector as ls
from . import secret_guard

FORBIDDEN_KEYS = {"score", "grade", "rating", "receipt"}
MAX_PATCH_BYTES = 32_768
MAX_ITEMS = 32
MAX_ITEM_CHARS = 2_000

STRING_KEYS = {
    "representation",
    "abstract",
    "abstraction",
}
BOOLEAN_KEYS = {"verified", "check"}
LIST_KEYS = {
    "parts",
    "relations",
    "definitions",
    "risks",
    "trace",
    "evidence",
    "plan",
    "criteria",
    "selected",
    "order",
    "anomalies",
    "audit",
    "clusters",
    "hierarchy",
    "resolutions",
    "classes",
}
STRING_LIST_KEYS = {
    "parts",
    "relations",
    "definitions",
    "risks",
    "trace",
    "evidence",
    "plan",
    "anomalies",
    "audit",
    "hierarchy",
    "classes",
}
NUMBER_KEYS = {"confidence", "calibration"}
OBJECT_KEYS = {
    "reading",
    "diff",
    "allocation",
    "control_plan",
    "decision",
    "verdict",
    "measure",
    "standard",
    "transfer",
    "instance",
    "merged",
    "benchmark",
    "calibration",
    "confidence",
    "classes",
    "clusters",
    "criteria",
    "selected",
    "order",
}

CLOSURE_LABELS = {
    "structure": "至少一个非空 part 集合",
    "relations": "每个 part 至少进入一条关系，不得只列孤立关系词",
    "risks": "至少一条可复述的失败或反例义务",
    "synthesis": "计划必须覆盖当前全部 part",
    "grounding": "verified 必须同时带证据标记",
    "resolve": "所有开放问题必须被消解或显式关闭",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + "." + str(key)
            if key in FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def _parts(s: dict) -> list[str]:
    return _strings(s.get("artifact", {}).get("parts"))


def _all_parts_related(parts: list[str], relations: list[str]) -> bool:
    return (
        bool(parts)
        and bool(relations)
        and all(any(part in relation for relation in relations) for part in parts)
    )


def _plan_covers_parts(parts: list[str], plan: list[str]) -> bool:
    joined = "\n".join(plan)
    return bool(parts) and bool(plan) and all(part in joined for part in parts)


def obligation_status(s: dict, need: str) -> tuple[str, str]:
    artifact = s.get("artifact", {})
    parts = _parts(s)
    if need == "structure":
        return ("satisfied", "parts") if parts else ("open", "parts")
    if need == "relations":
        relations = _strings(artifact.get("relations"))
        if not relations:
            return "open", "relations"
        return ("satisfied" if _all_parts_related(parts, relations) else "weak", "relations")
    if need == "risks":
        risks = _strings(artifact.get("risks"))
        if not risks:
            return "open", "risks"
        return ("satisfied" if any(len(item) >= 12 for item in risks) else "weak", "risks")
    if need == "synthesis":
        plan = _strings(artifact.get("plan"))
        if not plan:
            return "open", "plan"
        return ("satisfied" if _plan_covers_parts(parts, plan) else "weak", "plan")
    if need == "grounding":
        evidence = _strings(artifact.get("evidence"))
        if artifact.get("verified") and evidence:
            return "satisfied", "evidence"
        if artifact.get("verified") or evidence:
            return "weak", "evidence"
        return "open", "verified"
    if need == "resolve":
        questions = _strings(s.get("open_questions"))
        return ("open", "open_questions") if questions else ("satisfied", "open_questions")
    raise ValueError(f"unknown need: {need}")


def build_agenda(s: dict) -> dict:
    obligations = []
    gaps = []
    for need in ls.NEEDS:
        status, witness = obligation_status(s, need)
        item = {
            "id": f"epistemic:{need}",
            "need": need,
            "status": status,
            "witness": witness,
            "closure": CLOSURE_LABELS[need],
        }
        obligations.append(item)
        if status != "satisfied":
            gaps.append(need)
    return {
        "schema": "nf-epistemic-agenda/1",
        "turn": int(s.get("turn", 0)),
        "obligations": obligations,
        "gaps": gaps,
        "digest": digest(obligations),
        "no_scoring": True,
    }


def unresolved_after(s: dict, predicted: list[str]) -> list[str]:
    return [need for need in predicted if obligation_status(s, need)[0] != "satisfied"]


def _value_issues(key: str, value: Any) -> list[str]:
    issues: list[str] = []
    if key in STRING_KEYS and not isinstance(value, str):
        issues.append(f"{key} must be a string")
    elif key in BOOLEAN_KEYS and not isinstance(value, bool):
        issues.append(f"{key} must be a boolean")
    elif key in LIST_KEYS and not isinstance(value, list):
        issues.append(f"{key} must be an array")
    elif key in OBJECT_KEYS and not isinstance(value, (dict, int, float)):
        issues.append(f"{key} must be an object or number")
    if isinstance(value, str) and len(value) > MAX_ITEM_CHARS:
        issues.append(f"{key} exceeds {MAX_ITEM_CHARS} characters")
    if isinstance(value, list):
        if len(value) > MAX_ITEMS:
            issues.append(f"{key} exceeds {MAX_ITEMS} items")
        for index, item in enumerate(value):
            if key in STRING_LIST_KEYS and not isinstance(item, str):
                issues.append(f"{key}[{index}] must be a string")
            if isinstance(item, str) and len(item) > MAX_ITEM_CHARS:
                issues.append(f"{key}[{index}] exceeds {MAX_ITEM_CHARS} characters")
            if not isinstance(item, (str, dict, int, float, bool, type(None))):
                issues.append(f"{key}[{index}] has unsupported type")
    if key in NUMBER_KEYS and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        issues.append(f"{key} must be a number")
    return issues


def validate_thought_patch(candidate: dict, patch: Any) -> list[str]:
    if not isinstance(patch, dict):
        return ["thought_patch must be an object"]
    if not patch:
        return ["thought_patch must not be empty"]
    encoded = json.dumps(patch, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_PATCH_BYTES:
        return ["thought_patch exceeds byte limit"]
    forbidden = _forbidden_paths(patch)
    if forbidden:
        return ["forbidden thought_patch keys: " + ",".join(forbidden)]
    secrets = secret_guard.find(patch, "$.thought_patch")
    if secrets:
        return [
            "sensitive data in thought_patch: {} ({})".format(item["path"], item["kind"])
            for item in secrets
        ]
    allowed = {key for atom_id in candidate["cluster"] for key in ls.CONTRACTS[atom_id]["adds"]}
    issues = []
    for key, value in patch.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            issues.append("invalid thought_patch key")
            continue
        if key not in allowed:
            issues.append(f"thought_patch key not produced by selected cluster: {key}")
            continue
        issues.extend(_value_issues(key, value))
    return issues
