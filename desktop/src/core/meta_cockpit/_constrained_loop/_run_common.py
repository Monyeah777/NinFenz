"""constrained_loop run 的通用小件（回合检 / trace / 结果信封）。"""

from __future__ import annotations

import time

from core.meta_cockpit import (
    calibration_store as cs,
)
from core.meta_cockpit._constrained_loop._base import (
    complete,
    safe_error,
)


def _elapsed(env: dict) -> float:
    return time.monotonic() - env["started"]


def _deadline(env: dict) -> bool:
    return env["max_seconds"] is not None and _elapsed(env) >= env["max_seconds"]


def _budget_exceeded(env: dict, context_units) -> bool:
    return (
        env["max_context_units"] is not None
        and env["spent_before"] + int(context_units or 0) > env["max_context_units"]
    )


def _stop_trace(env: dict, turn: int, action: str, reason=None, issues=None) -> None:
    entry = {"turn": turn, "action": action}
    if reason is not None:
        entry["reason"] = reason
    if issues is not None:
        entry["issues"] = issues
    env["trace"].append(entry)


def _initial_stop(env: dict) -> None:
    if complete(env["s"]):
        env["trace"].append(
            {"turn": env["resumed_from_turn"] + 1, "action": "stop", "reason": "done"}
        )
        env["termination"] = "done"
        env["exhausted"] = False


def _check_turn(env: dict, turn: int) -> bool:
    """回合前检；True = 已写 trace 并应结束循环。"""
    if not env["exhausted"]:
        return True
    if complete(env["s"]):
        env["trace"].append({"turn": turn, "action": "stop", "reason": "done"})
        env["termination"] = "done"
        env["exhausted"] = False
        return True
    if _deadline(env):
        env["trace"].append({"turn": turn, "action": "stop", "reason": "deadline"})
        env["termination"] = "deadline"
        env["exhausted"] = False
        return True
    return False


def _persist_store(env: dict) -> None:
    """只为至少完成一次真实转换的回合落盘；策略/协议失败不伪造新运行轮次。"""
    store, store_file = env["store"], env["store_file"]
    if store is None or store_file is None or not env["applied"]:
        return
    store["atoms"] = env["ledger"]
    try:
        saved = cs.save(store_file, store)
    except (OSError, ValueError, RuntimeError) as exc:
        env["trace"].append(
            {
                "turn": int(env["s"].get("turn", 0)),
                "action": "error",
                "issues": ["calibration store save: " + safe_error(exc)],
            }
        )
        env["termination"] = "calibration-store-error"
    else:
        env["s"]["calibration_rounds"] = saved["rounds"]


def _result(env: dict) -> dict:
    failed = env["termination"] in {
        "policy-error",
        "protocol-error",
        "execution-error",
        "calibration-error",
        "journal-error",
        "calibration-store-error",
        "deadline-exceeded",
        "context-budget-exceeded",
        "state-cycle",
    }
    return {
        "status": "fail" if failed else "pass",
        "state": env["s"],
        "trace": env["trace"],
        "turns": int(env["s"].get("turn", 0)),
        "turns_this_run": env["applied"],
        "complete": complete(env["s"]),
        "termination": env["termination"],
        "journal_status": env["journal_status"],
        "resumed_from_turn": env["resumed_from_turn"],
        "elapsed_ms": round(_elapsed(env) * 1000, 3),
        "context_units_spent": int(env["s"].get("context_units_spent", 0)),
        "context_units_limit": env["max_context_units"],
    }
