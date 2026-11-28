from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from pathlib import Path

from core.meta_cockpit import (
    calibration_ledger as cl,
)
from core.meta_cockpit import (
    calibration_store as cs,
)
from core.meta_cockpit import (
    cognitive_cockpit as cc,
)
from core.meta_cockpit import live_selector as ls
from core.meta_cockpit import (
    secret_guard,
)
from core.meta_cockpit import session_journal as journal
from core.meta_cockpit._constrained_loop._base import LoopOptions


def _invalid(state, issues: list, turns: int = 0) -> dict:
    return {
        "status": "fail",
        "state": copy.deepcopy(state),
        "trace": [{"turn": 0, "action": "error", "issues": issues}],
        "turns": turns,
        "complete": False,
        "termination": "invalid-input",
    }


def _bad_turns(max_turns) -> bool:
    return not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 0


def _bad_seconds(max_seconds) -> bool:
    if max_seconds is None:
        return False
    return not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool) or max_seconds < 0


def _bad_context_units(max_context_units) -> bool:
    if max_context_units is None:
        return False
    return not isinstance(max_context_units, int) or isinstance(max_context_units, bool)         or max_context_units < 1


def _turn_values_ok(turn, values) -> bool:
    if not isinstance(turn, int) or isinstance(turn, bool) or turn < 1:
        return False
    if not isinstance(values, list):
        return False
    return all(isinstance(value, str) and 0 < len(value) <= 2000 for value in values)


def _injection_secret_issue(turn: int, values: list) -> list[str] | None:
    for value in values:
        secrets = secret_guard.find(value, f"$.injections[{turn}]")
        if secrets:
            return [
                "sensitive data: {} ({})".format(item["path"], item["kind"])
                for item in secrets
            ]
    return None


def _normalize_injections(state, injections) -> dict:
    normalized: dict[int, list[str]] = {}
    if injections is None:
        return normalized
    if not isinstance(injections, dict):
        return _invalid(state, ["injections must be an object"])
    total = 0
    for turn, values in injections.items():
        if not _turn_values_ok(turn, values):
            return _invalid(state, ["invalid injections"])
        issue = _injection_secret_issue(turn, values)
        if issue is not None:
            return _invalid(state, issue)
        total += len(values)
        normalized[turn] = list(values)
    if total > 64:
        return _invalid(state, ["too many injections"])
    return normalized


def _validate_options(state, opts: LoopOptions) -> dict:
    if _bad_turns(opts.max_turns):
        return _invalid(state, ["max_turns must be a non-negative integer"])
    if _bad_seconds(opts.max_seconds):
        return _invalid(state, ["max_seconds must be non-negative"])
    if _bad_context_units(opts.max_context_units):
        return _invalid(state, ["max_context_units must be positive"])
    return _normalize_injections(state, opts.injections)


def _validate(prompt: str, opts: LoopOptions) -> tuple[dict | None, dict]:
    """run 的入参校验段（逐字搬移）：非法输入原样返回 fail 信封。"""
    state = opts.state
    prompt_secrets = secret_guard.find(prompt, "$.prompt")
    if prompt_secrets:
        return _invalid(
            state,
            [
                "sensitive data: {} ({})".format(item["path"], item["kind"])
                for item in prompt_secrets
            ],
        )
    return _validate_options(state, opts)


@dataclass
class _Ctx:
    """run 装配段的输出（store/journal 会话状态）。"""
    started: float
    store: dict | None
    store_file: Path | None
    store_status: str
    ledger: dict
    journal_status: str
    s: dict
    resumed_from_turn: int


def _mutual_fail(state) -> dict:
    return {
        "status": "fail",
        "state": copy.deepcopy(state),
        "trace": [
            {
                "turn": 0,
                "action": "error",
                "issues": ["journal_path and state are mutually exclusive"],
            }
        ],
        "turns": int(state.get("turn", 0)),
        "complete": False,
        "termination": "invalid-input",
    }


def _tampered_fail(base_state: dict, store_status: str) -> dict:
    return {
        "status": "fail",
        "state": base_state,
        "trace": [
            {"turn": 0, "action": "error", "issues": ["calibration store: " + store_status]}
        ],
        "turns": int(base_state.get("turn", 0)),
        "turns_this_run": 0,
        "complete": False,
        "termination": "calibration-store-error",
        "journal_status": "not-started",
        "resumed_from_turn": int(base_state.get("turn", 0)),
    }


def _journal_fail(state: dict, journal_status: str) -> dict:
    return {
        "status": "fail",
        "state": state,
        "trace": [{"turn": 0, "action": "error", "issues": ["journal: " + journal_status]}],
        "turns": 0,
        "complete": False,
        "termination": "journal-error",
        "journal_status": journal_status,
        "resumed_from_turn": 0,
    }


def _calibration_fail(state: dict, calibration_status: str, journal_status: str) -> dict:
    turn = int(state.get("turn", 0))
    return {
        "status": "fail",
        "state": state,
        "trace": [
            {
                "turn": turn,
                "action": "error",
                "issues": ["calibration: " + calibration_status],
            }
        ],
        "turns": turn,
        "turns_this_run": 0,
        "complete": not ls.unmet(state),
        "termination": "calibration-store-error",
        "journal_status": journal_status,
        "resumed_from_turn": turn,
    }


def _journal_session(prompt, journal_path, base_state, ledger, store, store_status):
    """journal 装配段 → (fail 信封 | None, state, ledger, journal_status)。"""
    journal_status = "disabled"
    if journal_path is None:
        return None, base_state, ledger, journal_status
    doc, journal_status = journal.ensure(
        Path(journal_path), prompt, base_state, initial_ledger=ledger
    )
    if doc is None:
        s = cc.initial_state(prompt)
        return _journal_fail(s, journal_status), s, ledger, journal_status
    s = journal.current_state(doc)
    if journal_status == "new" and store is not None:
        s["store_status"] = store_status
    if not doc["events"]:
        return None, s, ledger, journal_status
    ledger, calibration_status = journal.reconcile_calibration(doc, ledger)
    if calibration_status != "ok":
        return _calibration_fail(s, calibration_status, journal_status), s, ledger, journal_status
    return None, s, ledger, journal_status


def _open_session(prompt: str, opts: LoopOptions) -> tuple[dict | None, _Ctx]:
    """run 的 store/journal 装配段（逐字搬移）：失败原样返回 fail 信封。"""
    store_path = opts.store_path
    state = opts.state
    journal_path = opts.journal_path
    started = time.monotonic()
    if journal_path is not None and state is not None:
        return _mutual_fail(state)
    store_file = Path(store_path) if store_path is not None else None
    if store_file is not None:
        store, store_status = cs.load(store_file)
        ledger = store["atoms"]
    else:
        store = None
        store_status = "disabled"
        ledger = cl.initial_ledger()
    base_state = copy.deepcopy(state) if state is not None else cc.initial_state(prompt)
    if store_status.startswith("tampered:"):
        return _tampered_fail(base_state, store_status)
    if store is not None:
        base_state["store_status"] = store_status
    failure, s, ledger, journal_status = _journal_session(
        prompt, journal_path, base_state, ledger, store, store_status
    )
    if failure is not None:
        return failure
    resumed_from_turn = int(s.get("turn", 0))
    return _Ctx(started=started, store=store, store_file=store_file,
                store_status=store_status, ledger=ledger,
                journal_status=journal_status, s=s,
                resumed_from_turn=resumed_from_turn)
