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


def _validate(prompt: str, opts: LoopOptions) -> tuple[dict | None, dict]:
    """run 的入参校验段（逐字搬移）：非法输入原样返回 fail 信封。"""
    state = opts.state
    max_turns = opts.max_turns
    max_seconds = opts.max_seconds
    max_context_units = opts.max_context_units
    injections = opts.injections
    prompt_secrets = secret_guard.find(prompt, "$.prompt")
    if prompt_secrets:
        return {
            "status": "fail",
            "state": copy.deepcopy(state),
            "trace": [
                {
                    "turn": 0,
                    "action": "error",
                    "issues": [
                        "sensitive data: {} ({})".format(item["path"], item["kind"])
                        for item in prompt_secrets
                    ],
                }
            ],
            "turns": 0,
            "complete": False,
            "termination": "invalid-input",
        }
    if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 0:
        return {
            "status": "fail",
            "state": copy.deepcopy(state),
            "trace": [
                {
                    "turn": 0,
                    "action": "error",
                    "issues": ["max_turns must be a non-negative integer"],
                }
            ],
            "turns": 0,
            "complete": False,
            "termination": "invalid-input",
        }
    if max_seconds is not None and (
        not isinstance(max_seconds, (int, float))
        or isinstance(max_seconds, bool)
        or max_seconds < 0
    ):
        return {
            "status": "fail",
            "state": copy.deepcopy(state),
            "trace": [
                {"turn": 0, "action": "error", "issues": ["max_seconds must be non-negative"]}
            ],
            "turns": 0,
            "complete": False,
            "termination": "invalid-input",
        }
    if max_context_units is not None and (
        not isinstance(max_context_units, int)
        or isinstance(max_context_units, bool)
        or max_context_units < 1
    ):
        return {
            "status": "fail",
            "state": copy.deepcopy(state),
            "trace": [
                {"turn": 0, "action": "error", "issues": ["max_context_units must be positive"]}
            ],
            "turns": 0,
            "complete": False,
            "termination": "invalid-input",
        }
    normalized_injections: dict[int, list[str]] = {}
    if injections is not None:
        if not isinstance(injections, dict):
            return {
                "status": "fail",
                "state": copy.deepcopy(state),
                "trace": [
                    {"turn": 0, "action": "error", "issues": ["injections must be an object"]}
                ],
                "turns": 0,
                "complete": False,
                "termination": "invalid-input",
            }
        total = 0
        for turn, values in injections.items():
            if (
                not isinstance(turn, int)
                or isinstance(turn, bool)
                or turn < 1
                or not isinstance(values, list)
                or not all(isinstance(value, str) and 0 < len(value) <= 2000 for value in values)
            ):
                return {
                    "status": "fail",
                    "state": copy.deepcopy(state),
                    "trace": [{"turn": 0, "action": "error", "issues": ["invalid injections"]}],
                    "turns": 0,
                    "complete": False,
                    "termination": "invalid-input",
                }
            for value in values:
                secrets = secret_guard.find(value, f"$.injections[{turn}]")
                if secrets:
                    return {
                        "status": "fail",
                        "state": copy.deepcopy(state),
                        "trace": [
                            {
                                "turn": 0,
                                "action": "error",
                                "issues": [
                                    "sensitive data: {} ({})".format(item["path"], item["kind"])
                                    for item in secrets
                                ],
                            }
                        ],
                        "turns": 0,
                        "complete": False,
                        "termination": "invalid-input",
                    }
            total += len(values)
            normalized_injections[turn] = list(values)
        if total > 64:
            return {
                "status": "fail",
                "state": copy.deepcopy(state),
                "trace": [{"turn": 0, "action": "error", "issues": ["too many injections"]}],
                "turns": 0,
                "complete": False,
                "termination": "invalid-input",
            }
    return normalized_injections


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


def _open_session(prompt: str, opts: LoopOptions) -> tuple[dict | None, _Ctx]:
    """run 的 store/journal 装配段（逐字搬移）：失败原样返回 fail 信封。"""
    store_path = opts.store_path
    state = opts.state
    journal_path = opts.journal_path
    started = time.monotonic()
    if journal_path is not None and state is not None:
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
        base_state["store_status"] = store_status
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
    if store is not None:
        base_state["store_status"] = store_status
    journal_status = "disabled"
    if journal_path is not None:
        doc, journal_status = journal.ensure(
            Path(journal_path), prompt, base_state, initial_ledger=ledger
        )
        if doc is None:
            s = cc.initial_state(prompt)
            return {
                "status": "fail",
                "state": s,
                "trace": [{"turn": 0, "action": "error", "issues": ["journal: " + journal_status]}],
                "turns": 0,
                "complete": False,
                "termination": "journal-error",
                "journal_status": journal_status,
                "resumed_from_turn": 0,
            }
        s = journal.current_state(doc)
        if journal_status == "new" and store is not None:
            s["store_status"] = store_status
        if doc["events"]:
            ledger, calibration_status = journal.reconcile_calibration(doc, ledger)
            if calibration_status != "ok":
                return {
                    "status": "fail",
                    "state": s,
                    "trace": [
                        {
                            "turn": int(s.get("turn", 0)),
                            "action": "error",
                            "issues": ["calibration: " + calibration_status],
                        }
                    ],
                    "turns": int(s.get("turn", 0)),
                    "turns_this_run": 0,
                    "complete": not ls.unmet(s),
                    "termination": "calibration-store-error",
                    "journal_status": journal_status,
                    "resumed_from_turn": int(s.get("turn", 0)),
                }
    else:
        s = base_state
    resumed_from_turn = int(s.get("turn", 0))
    return _Ctx(started=started, store=store, store_file=store_file,
                store_status=store_status, ledger=ledger,
                journal_status=journal_status, s=s,
                resumed_from_turn=resumed_from_turn)
