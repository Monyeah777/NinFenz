from __future__ import annotations

from core.meta_cockpit._constrained_loop._base import LoopOptions
from core.meta_cockpit._constrained_loop._request import _open_session, _validate
from core.meta_cockpit._constrained_loop._run_common import (
    _check_turn,
    _initial_stop,
    _persist_store,
    _result,
)
from core.meta_cockpit._constrained_loop._run_phases import _run_turn


def run(prompt: str, policy, opts: LoopOptions | None = None) -> dict:
    """约束选择完整回合循环：候选 -> 选择 -> 执行 -> 校准 -> 重编译。"""
    opts = opts if opts is not None else LoopOptions()
    res = _validate(prompt, opts)
    if "status" in res:
        return res
    normalized_injections = res
    res = _open_session(prompt, opts)
    if isinstance(res, dict):
        return res
    ctx = res
    env = {
        "prompt": prompt,
        "policy": policy,
        "started": ctx.started,
        "store": ctx.store,
        "store_file": ctx.store_file,
        "store_status": ctx.store_status,
        "ledger": ctx.ledger,
        "journal_status": ctx.journal_status,
        "s": ctx.s,
        "resumed_from_turn": ctx.resumed_from_turn,
        "journal_path": opts.journal_path,
        "max_turns": opts.max_turns,
        "max_seconds": opts.max_seconds,
        "max_context_units": opts.max_context_units,
        "injections": normalized_injections,
        "trace": [],
        "applied": 0,
        "termination": "max-turns",
        "exhausted": True,
    }
    _initial_stop(env)
    for turn in range(env["resumed_from_turn"] + 1, env["max_turns"] + 1):
        if _check_turn(env, turn):
            break
        if not _run_turn(env, turn):
            break
    if env["exhausted"]:
        env["trace"].append(
            {
                "turn": max(env["max_turns"], env["resumed_from_turn"]),
                "action": "stop",
                "reason": "max turns",
            }
        )
    _persist_store(env)
    return _result(env)
