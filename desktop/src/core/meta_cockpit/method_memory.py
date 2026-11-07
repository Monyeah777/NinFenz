"""Bounded cross-turn method memory and cognitive-state cycle detection."""

from __future__ import annotations

import hashlib
import json
from typing import Any

MAX_HISTORY = 8
DIGEST_RE = frozenset("0123456789abcdef")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= DIGEST_RE


def core_signature(state: dict) -> str:
    """Hash cognitive content while excluding clocks, budgets spent and history."""
    payload = {
        "goal": state.get("goal"),
        "artifact": state.get("artifact", {}),
        "open_questions": state.get("open_questions", []),
        "reference": state.get("reference", []),
        "budget": state.get("budget", {}),
        "budget_state": state.get("budget_state", {}),
        "fallback": state.get("fallback", {}),
        "task_type": state.get("task_type"),
        "frame": state.get("frame"),
        "library": state.get("library"),
    }
    return digest(payload)


def normalize_history(state: dict) -> list[dict]:
    history = state.get("history")
    if not isinstance(history, list):
        return []
    valid = []
    for item in history[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        if not _valid_digest(item.get("state_signature")):
            continue
        valid.append(item)
    return valid


def visited_signatures(state: dict) -> set[str]:
    found = {core_signature(state)}
    root = state.get("history_root")
    if _valid_digest(root):
        found.add(str(root))
    for item in normalize_history(state):
        signature = item.get("state_signature")
        if _valid_digest(signature):
            found.add(str(signature))
    return found


def record_turn(
    state: dict,
    turn: int,
    cluster: list[str],
    resolved: list[str],
    changed_keys: list[str],
    kind: str,
) -> str:
    signature = core_signature(state)
    history = normalize_history(state)
    history.append(
        {
            "turn": int(turn),
            "cluster": list(cluster),
            "resolved": sorted(set(resolved)),
            "changed_keys": sorted(set(changed_keys)),
            "kind": kind,
            "state_signature": signature,
        }
    )
    state["history"] = history[-MAX_HISTORY:]
    if not _valid_digest(state.get("history_root")):
        state["history_root"] = signature
    return signature


def is_cycle(state: dict, candidate_state: dict) -> bool:
    return core_signature(candidate_state) in visited_signatures(state)
