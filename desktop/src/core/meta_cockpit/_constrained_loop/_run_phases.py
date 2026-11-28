"""constrained_loop 单回合各阶段实现（注入/预检/策略/执行/落盘）。"""

from __future__ import annotations

import copy
import time
from pathlib import Path

from core.meta_cockpit import (
    calibration_ledger as cl,
)
from core.meta_cockpit import constrained_choice as cons
from core.meta_cockpit import (
    context_pack,
    method_memory,
    task_profile,
)
from core.meta_cockpit import live_selector as ls
from core.meta_cockpit import session_journal as journal
from core.meta_cockpit._constrained_loop._base import (
    complete,
    external_context_of,
    safe_error,
    source_snapshot_of,
)
from core.meta_cockpit._constrained_loop._run_common import (
    _budget_exceeded,
    _deadline,
    _stop_trace,
)

def _observations(turn_state: dict, injections: dict, turn: int) -> list[str]:
    observations = []
    for question in injections.get(turn, []):
        text = str(question).strip()
        if text and text not in turn_state["open_questions"]:
            turn_state["open_questions"].append(text)
            observations.append(text)
    return observations


def _prepare_turn(env: dict, turn: int) -> bool:
    """注入 / 候选 / 预检预算；False = 已写 trace 并应结束循环。"""
    turn_state = copy.deepcopy(env["s"])
    observations = _observations(turn_state, env["injections"], turn)
    candidates = cons.build_candidates(turn_state, env["ledger"])
    candidate_search_stats = ls.search_stats()
    if not candidates:
        env["trace"].append({"turn": turn, "action": "stop", "reason": "no candidates"})
        env["termination"] = "blocked"
        env["exhausted"] = False
        return False
    context_units = None
    spent_before = 0
    if env["max_context_units"] is not None:
        spent_before = int(env["s"].get("context_units_spent", 0))
        try:
            preflight_payload = cons.build_prompt_payload(
                turn_state, candidates, providers=getattr(env["policy"], "providers", None)
            )
            context_units = preflight_payload["context"]["budget"]["estimated_units"]
        except ValueError as exc:
            _stop_trace(env, turn, "error", issues=[safe_error(exc)])
            env["termination"] = "context-budget-exceeded"
            env["exhausted"] = False
            return False
        if spent_before + context_units > env["max_context_units"]:
            _stop_trace(env, turn, "error", issues=["session context budget exceeded"])
            env["termination"] = "context-budget-exceeded"
            env["exhausted"] = False
            return False
    env.update(
        {
            "turn_state": turn_state,
            "observations": observations,
            "candidates": candidates,
            "candidate_search_stats": candidate_search_stats,
            "context_units": context_units,
            "spent_before": spent_before,
        }
    )
    return True


def _context_missing(
    context_digest, context_units, source_snapshot, external_context
) -> bool:
    return (
        context_digest is None
        or context_units is None
        or source_snapshot is None
        or external_context is None
    )


def _context_of(env: dict, resp) -> tuple:
    turn_state, candidates = env["turn_state"], env["candidates"]
    context_units = env["context_units"]
    response_context_units = getattr(resp, "context_units", None)
    if response_context_units is not None:
        context_units = response_context_units
    context_digest = getattr(resp, "context_digest", None)
    source_snapshot = getattr(resp, "source_snapshot", None)
    external_context = getattr(resp, "external_context", None)
    missing = _context_missing(context_digest, context_units, source_snapshot, external_context)
    if env["journal_path"] is not None and missing:
        payload = cons.build_prompt_payload(turn_state, candidates)
        if context_digest is None:
            context_digest = context_pack.digest(payload)
        if context_units is None:
            context_units = payload["context"]["budget"]["estimated_units"]
        if source_snapshot is None:
            source_snapshot = source_snapshot_of(payload)
        if external_context is None:
            external_context = external_context_of(payload)
    return context_units, context_digest, source_snapshot, external_context


def _policy_phase(env: dict, turn: int) -> bool:
    """策略调用 + 上下文/协议校验；False = 已写 trace 并应结束循环。"""
    turn_state, candidates = env["turn_state"], env["candidates"]
    try:
        policy_started = time.monotonic()
        resp = env["policy"](copy.deepcopy(turn_state), copy.deepcopy(candidates))
    except Exception as exc:
        _stop_trace(env, turn, "error", issues=[f"policy exception: {safe_error(exc)}"])
        env["termination"] = "policy-error"
        env["exhausted"] = False
        return False
    policy_ms = round((time.monotonic() - policy_started) * 1000, 3)
    if _deadline(env):
        _stop_trace(env, turn, "error", issues=["policy deadline exceeded"])
        env["termination"] = "deadline-exceeded"
        env["exhausted"] = False
        return False
    context_units, context_digest, source_snapshot, external_context = _context_of(env, resp)
    env["context_units"] = context_units
    if _budget_exceeded(env, context_units):
        _stop_trace(env, turn, "error", issues=["session context budget exceeded after policy"])
        env["termination"] = "context-budget-exceeded"
        env["exhausted"] = False
        return False
    issues = cons.validate(resp, candidates, turn_state)
    if issues:
        _stop_trace(env, turn, "error", issues=issues)
        env["termination"] = "protocol-error"
        env["exhausted"] = False
        return False
    if resp["choice"] is None:
        _stop_trace(env, turn, "stop", resp["reason"])
        env["termination"] = "policy-stop"
        env["exhausted"] = False
        return False
    env.update(
        {
            "resp": resp,
            "policy_ms": policy_ms,
            "context_digest": context_digest,
            "source_snapshot": source_snapshot,
            "external_context": external_context,
        }
    )
    return True


def _apply_phase(env: dict, turn: int) -> bool:
    """执行候选并做结果/进度检查；False = 已写 trace 并应结束循环。"""
    resp, candidates = env["resp"], env["candidates"]
    c = candidates[resp["choice"]]
    thought_patch = resp.get("thought_patch")
    turn_state = env["turn_state"]
    before_keys = ls.available_keys(turn_state)
    before_unmet = set(ls.unmet(turn_state))
    execution_started = time.monotonic()
    result = cons.apply(turn_state, candidates, resp)
    execution_ms = round((time.monotonic() - execution_started) * 1000, 3)
    if result["status"] != "pass":
        _stop_trace(env, turn, "error", issues=[result["error"]])
        env["termination"] = "execution-error"
        env["exhausted"] = False
        return False
    actual = set(result["resolved"])
    if actual != set(c["resolves"]):
        _stop_trace(env, turn, "error", issues=["calibration mismatch"])
        env["termination"] = "calibration-error"
        env["exhausted"] = False
        return False
    committed_state = copy.deepcopy(result["state"])
    committed_state["turn"] = turn
    committed_state["context_units_spent"] = int(
        turn_state.get("context_units_spent", 0)
    ) + int(env["context_units"] or 0)
    if method_memory.core_signature(committed_state) == method_memory.core_signature(env["s"]):
        _stop_trace(env, turn, "stop", "no progress")
        env["termination"] = "no-progress"
        env["exhausted"] = False
        return False
    if method_memory.is_cycle(env["s"], committed_state):
        _stop_trace(env, turn, "error", issues=["cognitive state cycle"])
        env["termination"] = "state-cycle"
        env["exhausted"] = False
        return False
    method_memory.record_turn(
        committed_state,
        turn,
        c["cluster"],
        [str(item) for item in actual],
        result.get("changed_keys", []),
        c.get("kind", "unknown"),
    )
    env.update(
        {
            "c": c,
            "thought_patch": thought_patch,
            "before_keys": before_keys,
            "before_unmet": before_unmet,
            "actual": actual,
            "result": result,
            "execution_ms": execution_ms,
            "committed_state": committed_state,
        }
    )
    return True


def _decision_payload(env: dict) -> dict:
    resp = env["resp"]
    payload = {
        "choice": resp["choice"],
        "candidates": env["candidates"],
        "context_digest": env["context_digest"],
        "context_units": int(env["context_units"] or 0),
        "source_snapshot": env["source_snapshot"] or [],
        "external_context": bool(env["external_context"]),
    }
    thought_patch = env["thought_patch"]
    if thought_patch is not None:
        payload["thought_patch"] = thought_patch
        payload["thought_patch_digest"] = journal.digest(thought_patch)
    return payload


def _append_turn(
    journal_path, prompt: str, env: dict, decision: dict, cal_before, cal_after
) -> str:
    _, commit_status = journal.append_turn(
        Path(journal_path),
        prompt,
        opts=journal.TurnOptions(
            before_state=env["s"],
            after_state=env["committed_state"],
            cluster=env["c"]["cluster"],
            kind=env["c"].get("kind", "unknown"),
            predicted=env["c"]["resolves"],
            resolved=sorted(env["actual"]),
            changed_keys=env["result"].get("changed_keys", []),
            atom_trace=env["result"].get("atom_trace", []),
            decision=decision,
            calibration_before_digest=cal_before,
            calibration_after_digest=cal_after,
            observations=env["observations"],
        ),
    )
    return commit_status


def _commit_phase(env: dict, turn: int) -> bool:
    """journal 落盘（预测/实际一致后才提交）；False = 已写 trace 并应结束循环。"""
    c = env["c"]
    pending_ledger = copy.deepcopy(env["ledger"])
    calibration_before_digest = None
    calibration_after_digest = None
    if env["journal_path"] is not None:
        calibration_before_digest = journal.digest(pending_ledger)
        cl.observe(pending_ledger, c["cluster"], ls.available_keys(env["committed_state"]))
        calibration_after_digest = journal.digest(pending_ledger)
    if env["journal_path"] is not None:
        commit_status = _append_turn(
            env["journal_path"],
            env["prompt"],
            env,
            _decision_payload(env),
            calibration_before_digest,
            calibration_after_digest,
        )
        if commit_status != "appended":
            _stop_trace(env, turn, "error", issues=["journal: " + commit_status])
            env["termination"] = "journal-error"
            env["exhausted"] = False
            return False
    env["pending_ledger"] = pending_ledger
    return True


def _finalize_turn(env: dict, turn: int) -> bool:
    """提交本回合状态并写 apply trace；False = 已写 trace 并应结束循环。"""
    c = env["c"]
    result = env["result"]
    env["s"] = env["committed_state"]
    if env["journal_path"] is not None:
        env["ledger"] = env["pending_ledger"]
    else:
        cl.observe(env["ledger"], c["cluster"], ls.available_keys(env["s"]))
    after_unmet = set(ls.unmet(env["s"]))
    env["applied"] += 1
    env["trace"].append(
        {
            "turn": turn,
            "action": "apply",
            "cluster": c["cluster"],
            "resolved": sorted(env["before_unmet"] - after_unmet),
            "changed_keys": result.get("changed_keys", []),
            "kind": c.get("kind", "unknown"),
            "policy_ms": env["policy_ms"],
            "execution_ms": env["execution_ms"],
            "context_units": int(env["context_units"] or 0),
            "context_units_spent": int(env["committed_state"]["context_units_spent"]),
            "facet_gaps": task_profile.build_facet_agenda(env["s"])["gaps"],
            "candidate_search_stats": env["candidate_search_stats"],
            "thought_patch_keys": (
                sorted(env["thought_patch"]) if env["thought_patch"] is not None else []
            ),
            "reliability_band": cl.band(cl.avg_reliability(env["ledger"], c["cluster"])),
        }
    )
    if complete(env["s"]):
        _stop_trace(env, turn, "stop", "done")
        env["termination"] = "done"
        env["exhausted"] = False
        return False
    if env["before_keys"] == ls.available_keys(env["s"]):
        _stop_trace(env, turn, "stop", "no progress")
        env["termination"] = "no-progress"
        env["exhausted"] = False
        return False
    return True


def _run_turn(env: dict, turn: int) -> bool:
    return (
        _prepare_turn(env, turn)
        and _policy_phase(env, turn)
        and _apply_phase(env, turn)
        and _commit_phase(env, turn)
        and _finalize_turn(env, turn)
    )
