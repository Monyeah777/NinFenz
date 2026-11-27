from __future__ import annotations

import copy
import time
from pathlib import Path

from core.meta_cockpit import (
    calibration_ledger as cl,
)
from core.meta_cockpit import (
    calibration_store as cs,
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
    LoopOptions,
    complete,
    external_context_of,
    safe_error,
    source_snapshot_of,
)
from core.meta_cockpit._constrained_loop._request import _open_session, _validate


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
    started = ctx.started

    def elapsed_seconds() -> float:
        return time.monotonic() - started

    store = ctx.store
    store_file = ctx.store_file
    store_status = ctx.store_status
    ledger = ctx.ledger
    journal_status = ctx.journal_status
    s = ctx.s
    resumed_from_turn = ctx.resumed_from_turn
    journal_path = opts.journal_path
    max_turns = opts.max_turns
    max_seconds = opts.max_seconds
    max_context_units = opts.max_context_units
    injections = normalized_injections
    trace = []
    applied = 0
    termination = "max-turns"
    exhausted = True
    if complete(s):
        trace.append({"turn": resumed_from_turn + 1, "action": "stop", "reason": "done"})
        termination = "done"
        exhausted = False
    for turn in range(resumed_from_turn + 1, max_turns + 1):
        if not exhausted:
            break
        if complete(s):
            trace.append({"turn": turn, "action": "stop", "reason": "done"})
            termination = "done"
            exhausted = False
            break
        if max_seconds is not None and elapsed_seconds() >= max_seconds:
            trace.append({"turn": turn, "action": "stop", "reason": "deadline"})
            termination = "deadline"
            exhausted = False
            break
        turn_state = copy.deepcopy(s)
        observations = []
        for question in injections.get(turn, []):
            text = str(question).strip()
            if text and text not in turn_state["open_questions"]:
                turn_state["open_questions"].append(text)
                observations.append(text)
        candidates = cons.build_candidates(turn_state, ledger)
        candidate_search_stats = ls.search_stats()
        if not candidates:
            trace.append({"turn": turn, "action": "stop", "reason": "no candidates"})
            termination = "blocked"
            exhausted = False
            break
        context_units = None
        if max_context_units is not None:
            spent_before_context = int(s.get("context_units_spent", 0))
            try:
                preflight_payload = cons.build_prompt_payload(
                    turn_state, candidates, providers=getattr(policy, "providers", None)
                )
                context_units = preflight_payload["context"]["budget"]["estimated_units"]
            except ValueError as exc:
                trace.append({"turn": turn, "action": "error", "issues": [safe_error(exc)]})
                termination = "context-budget-exceeded"
                exhausted = False
                break
            if spent_before_context + context_units > max_context_units:
                trace.append(
                    {"turn": turn, "action": "error", "issues": ["session context budget exceeded"]}
                )
                termination = "context-budget-exceeded"
                exhausted = False
                break
        try:
            policy_started = time.monotonic()
            resp = policy(copy.deepcopy(turn_state), copy.deepcopy(candidates))
        except Exception as exc:
            trace.append(
                {
                    "turn": turn,
                    "action": "error",
                    "issues": [f"policy exception: {safe_error(exc)}"],
                }
            )
            termination = "policy-error"
            exhausted = False
            break
        policy_ms = round((time.monotonic() - policy_started) * 1000, 3)
        if max_seconds is not None and elapsed_seconds() >= max_seconds:
            trace.append({"turn": turn, "action": "error", "issues": ["policy deadline exceeded"]})
            termination = "deadline-exceeded"
            exhausted = False
            break
        context_digest = getattr(resp, "context_digest", None)
        response_context_units = getattr(resp, "context_units", None)
        if response_context_units is not None:
            context_units = response_context_units
        source_snapshot = getattr(resp, "source_snapshot", None)
        external_context = getattr(resp, "external_context", None)
        if journal_path is not None and (
            context_digest is None
            or context_units is None
            or source_snapshot is None
            or external_context is None
        ):
            payload = cons.build_prompt_payload(turn_state, candidates)
            if context_digest is None:
                context_digest = context_pack.digest(payload)
            if context_units is None:
                context_units = payload["context"]["budget"]["estimated_units"]
            if source_snapshot is None:
                source_snapshot = source_snapshot_of(payload)
            if external_context is None:
                external_context = external_context_of(payload)
        if (
            max_context_units is not None
            and spent_before_context + int(context_units or 0) > max_context_units
        ):
            trace.append(
                {
                    "turn": turn,
                    "action": "error",
                    "issues": ["session context budget exceeded after policy"],
                }
            )
            termination = "context-budget-exceeded"
            exhausted = False
            break
        issues = cons.validate(resp, candidates, turn_state)
        if issues:
            trace.append({"turn": turn, "action": "error", "issues": issues})
            termination = "protocol-error"
            exhausted = False
            break
        if resp["choice"] is None:
            trace.append({"turn": turn, "action": "stop", "reason": resp["reason"]})
            termination = "policy-stop"
            exhausted = False
            break
        c = candidates[resp["choice"]]
        thought_patch = resp.get("thought_patch")
        before_keys = ls.available_keys(turn_state)
        before_unmet = set(ls.unmet(turn_state))
        execution_started = time.monotonic()
        result = cons.apply(turn_state, candidates, resp)
        execution_ms = round((time.monotonic() - execution_started) * 1000, 3)
        if result["status"] != "pass":
            trace.append({"turn": turn, "action": "error", "issues": [result["error"]]})
            termination = "execution-error"
            exhausted = False
            break
        actual = set(result["resolved"])
        if actual != set(c["resolves"]):
            trace.append({"turn": turn, "action": "error", "issues": ["calibration mismatch"]})
            termination = "calibration-error"
            exhausted = False
            break
        committed_state = copy.deepcopy(result["state"])
        committed_state["turn"] = turn
        committed_state["context_units_spent"] = int(
            turn_state.get("context_units_spent", 0)
        ) + int(context_units or 0)
        if method_memory.core_signature(committed_state) == (method_memory.core_signature(s)):
            trace.append({"turn": turn, "action": "stop", "reason": "no progress"})
            termination = "no-progress"
            exhausted = False
            break
        if method_memory.is_cycle(s, committed_state):
            trace.append({"turn": turn, "action": "error", "issues": ["cognitive state cycle"]})
            termination = "state-cycle"
            exhausted = False
            break
        method_memory.record_turn(
            committed_state,
            turn,
            c["cluster"],
            [str(item) for item in actual],
            result.get("changed_keys", []),
            c.get("kind", "unknown"),
        )
        pending_ledger = copy.deepcopy(ledger)
        calibration_before_digest = None
        calibration_after_digest = None
        if journal_path is not None:
            calibration_before_digest = journal.digest(pending_ledger)
            cl.observe(pending_ledger, c["cluster"], ls.available_keys(committed_state))
            calibration_after_digest = journal.digest(pending_ledger)
        if journal_path is not None:
            decision_payload = {
                "choice": resp["choice"],
                "candidates": candidates,
                "context_digest": context_digest,
                "context_units": int(context_units or 0),
                "source_snapshot": source_snapshot or [],
                "external_context": bool(external_context),
            }
            if thought_patch is not None:
                decision_payload["thought_patch"] = thought_patch
                decision_payload["thought_patch_digest"] = journal.digest(thought_patch)
            _, commit_status = journal.append_turn(
                Path(journal_path),
                prompt,
                opts=journal.TurnOptions(
                    before_state=s,
                    after_state=committed_state,
                    cluster=c['cluster'],
                    kind=c.get('kind', 'unknown'),
                    predicted=c['resolves'],
                    resolved=sorted(actual),
                    changed_keys=result.get('changed_keys', []),
                    atom_trace=result.get('atom_trace', []),
                    decision=decision_payload,
                    calibration_before_digest=calibration_before_digest,
                    calibration_after_digest=calibration_after_digest,
                    observations=observations,
                ),
            )
            if commit_status != "appended":
                trace.append(
                    {"turn": turn, "action": "error", "issues": ["journal: " + commit_status]}
                )
                termination = "journal-error"
                exhausted = False
                break
        # 预测/实际一致且持久化成功后才提交本回合。
        s = committed_state
        if journal_path is not None:
            ledger = pending_ledger
        else:
            cl.observe(ledger, c["cluster"], ls.available_keys(s))
        after_unmet = set(ls.unmet(s))
        applied += 1
        trace.append(
            {
                "turn": turn,
                "action": "apply",
                "cluster": c["cluster"],
                "resolved": sorted(before_unmet - after_unmet),
                "changed_keys": result.get("changed_keys", []),
                "kind": c.get("kind", "unknown"),
                "policy_ms": policy_ms,
                "execution_ms": execution_ms,
                "context_units": int(context_units or 0),
                "context_units_spent": int(committed_state["context_units_spent"]),
                "facet_gaps": task_profile.build_facet_agenda(s)["gaps"],
                "candidate_search_stats": candidate_search_stats,
                "thought_patch_keys": sorted(thought_patch) if thought_patch is not None else [],
                "reliability_band": cl.band(cl.avg_reliability(ledger, c["cluster"])),
            }
        )
        if complete(s):
            trace.append({"turn": turn, "action": "stop", "reason": "done"})
            termination = "done"
            exhausted = False
            break
        if before_keys == ls.available_keys(s):
            trace.append({"turn": turn, "action": "stop", "reason": "no progress"})
            termination = "no-progress"
            exhausted = False
            break
    if exhausted:
        trace.append(
            {"turn": max(max_turns, resumed_from_turn), "action": "stop", "reason": "max turns"}
        )

    # 只为至少完成一次真实转换的回合落盘；策略/协议失败不伪造新运行轮次。
    if store is not None and store_file is not None and applied:
        store["atoms"] = ledger
        try:
            saved = cs.save(store_file, store)
        except (OSError, ValueError, RuntimeError) as exc:
            trace.append(
                {
                    "turn": int(s.get("turn", 0)),
                    "action": "error",
                    "issues": ["calibration store save: " + safe_error(exc)],
                }
            )
            termination = "calibration-store-error"
        else:
            s["calibration_rounds"] = saved["rounds"]
    failed = termination in {
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
        "state": s,
        "trace": trace,
        "turns": int(s.get("turn", 0)),
        "turns_this_run": applied,
        "complete": complete(s),
        "termination": termination,
        "journal_status": journal_status,
        "resumed_from_turn": resumed_from_turn,
        "elapsed_ms": round(elapsed_seconds() * 1000, 3),
        "context_units_spent": int(s.get("context_units_spent", 0)),
        "context_units_limit": max_context_units,
    }
