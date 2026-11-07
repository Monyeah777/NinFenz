"""Deterministic, versioned task-shape profiling without scoring."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import evidence_roles, json_asset
from . import schema_compat as jsonschema

BASE = Path(__file__).parent
PROFILE_BYTES = (BASE / "task_profiles.json").read_bytes()
PROFILE_DOC = json_asset.load_bytes(PROFILE_BYTES)
PROFILES = {item["id"]: item for item in PROFILE_DOC["profiles"]}
WITNESSES = PROFILE_DOC["facet_witnesses"]
PROFILE_DIGEST = hashlib.sha256(PROFILE_BYTES).hexdigest()
SCHEMA = json_asset.load(BASE / "task_profiles.schema.json")
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
ATOM_IDS = {item["id"] for item in json_asset.load(BASE / "meta_atoms.json")["atoms"]}


def validate_catalog(document: dict | None = None) -> list[str]:
    document = document or PROFILE_DOC
    witnesses = document["facet_witnesses"]
    issues = [error.message for error in VALIDATOR.iter_errors(document)]
    ids = [item["id"] for item in document["profiles"]]
    if len(ids) != len(set(ids)):
        issues.append("duplicate profile id")
    entries = list(document["profiles"]) + [document["general"]]
    for entry in entries:
        label = entry.get("id", "general")
        if not set(entry["required_facets"]) <= set(entry["facets"]):
            issues.append("required facet missing from facets: " + label)
        for facet in entry["facets"]:
            if facet not in witnesses:
                issues.append(f"facet witness missing: {label}/{facet}")
        missing_atoms = set(entry["preferred_atoms"]) - ATOM_IDS
        if missing_atoms:
            issues.append(
                "unknown preferred atoms {}: {}".format(label, ",".join(sorted(missing_atoms)))
            )
        unknown_roles = set(entry["context_roles"]) - evidence_roles.KNOWN_ROLES
        if unknown_roles:
            issues.append(
                "unknown context roles {}: {}".format(label, ",".join(sorted(unknown_roles)))
            )
        if entry.get("id") is not None:
            strong = set(entry["strong_triggers"])
            weak = set(entry["weak_triggers"])
            if strong & weak:
                issues.append("overlapping triggers: " + label)
    return issues


CATALOG_ISSUES = validate_catalog(PROFILE_DOC)
if CATALOG_ISSUES:
    raise RuntimeError("invalid task profile catalog: " + "; ".join(CATALOG_ISSUES))


def _matches(text: str, trigger: str) -> bool:
    needle = trigger.casefold()
    if needle.isascii() and needle.replace("-", "").isalnum():
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text) is not None
    return needle in text


def build(goal: str) -> dict:
    text = goal.casefold()
    strong_modes = [
        item["id"]
        for item in PROFILE_DOC["profiles"]
        if any(_matches(text, trigger) for trigger in item["strong_triggers"])
    ]
    weak_modes = [
        item["id"]
        for item in PROFILE_DOC["profiles"]
        if any(_matches(text, trigger) for trigger in item["weak_triggers"])
    ]
    modes = strong_modes or weak_modes
    if modes:
        selected = [PROFILES[item] for item in modes]
        facets = []
        required = []
        functions = []
        roles = []
        preferred_atoms = []
        for item in selected:
            facets.extend(item["facets"])
            required.extend(item["required_facets"])
            functions.extend(item["functions"])
            roles.extend(item["context_roles"])
            preferred_atoms.extend(item["preferred_atoms"])
        primary = modes[0]
    else:
        fallback = PROFILE_DOC["general"]
        facets = list(fallback["facets"])
        required = list(fallback["required_facets"])
        functions = list(fallback["functions"])
        roles = list(fallback["context_roles"])
        preferred_atoms = list(fallback["preferred_atoms"])
        primary = "general"
    return {
        "schema": "nf-task-profile/1",
        "catalog_version": PROFILE_DOC["version"],
        "catalog_digest": PROFILE_DIGEST,
        "primary": primary,
        "modes": modes or ["general"],
        "facets": list(dict.fromkeys(facets)),
        "required_facets": list(dict.fromkeys(required)),
        "functions": list(dict.fromkeys(functions)),
        "context_roles": list(dict.fromkeys(roles)),
        "preferred_atoms": list(dict.fromkeys(preferred_atoms)),
        "no_scoring": True,
    }


def _state_value(state: dict, key: str):
    artifact = state.get("artifact", {})
    if key in artifact:
        return artifact.get(key)
    return state.get(key)


def _present(
    value, min_items: int = 1, min_chars: int = 0, item_keys: list[str] | None = None
) -> bool:
    if isinstance(value, list):
        if len(value) < min_items:
            return False
        if item_keys:
            return all(
                isinstance(item, dict) and all(key in item for key in item_keys) for item in value
            )
        if min_chars:
            return all(isinstance(item, str) and len(item) >= min_chars for item in value)
        return True
    if isinstance(value, dict):
        if not value or len(value) < min_items:
            return False
        return not item_keys or all(key in value for key in item_keys)
    if isinstance(value, str):
        return bool(value) and len(value) >= min_chars
    return value not in (None, False)


def _witness_closed(state: dict, witness: dict) -> bool:
    minimum = int(witness.get("min_items", 1))
    min_chars = int(witness.get("min_chars", 0))
    item_keys = witness.get("item_keys")
    allow_empty = set(witness.get("allow_empty", []))
    for key in witness["keys"]:
        value = _state_value(state, key)
        if value == [] and key in allow_empty:
            continue
        if not _present(value, minimum, min_chars, item_keys):
            return False
    return True


def facet_obligations(state: dict, profile: dict | None = None) -> list[dict]:
    profile = profile or build(state.get("goal", ""))
    out = []
    for facet in profile["required_facets"]:
        witnesses = WITNESSES[facet]
        closed = any(_witness_closed(state, item) for item in witnesses)
        out.append(
            {
                "facet": facet,
                "status": "closed" if closed else "open",
                "witnesses": witnesses,
            }
        )
    return out


def repair_keys(state: dict, profile: dict | None = None) -> list[str]:
    keys = {
        key
        for item in facet_obligations(state, profile)
        if item["status"] == "open"
        for witness in item["witnesses"]
        for key in witness["keys"]
    }
    return sorted(keys)


def build_facet_agenda(state: dict, profile: dict | None = None) -> dict:
    profile = profile or build(state.get("goal", ""))
    items = facet_obligations(state, profile)
    gaps = [item["facet"] for item in items if item["status"] == "open"]
    keys = sorted(
        {
            key
            for item in items
            if item["status"] == "open"
            for witness in item["witnesses"]
            for key in witness["keys"]
        }
    )
    payload = {
        "schema": "nf-task-facets/1",
        "items": items,
        "gaps": gaps,
        "repair_keys": keys,
        "no_scoring": True,
    }
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return payload
