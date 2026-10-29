"""约束选择完整回合循环：候选 → 选择 → 执行 → 校准 → 重编译。"""

from __future__ import annotations

import copy
import re
import time
from pathlib import Path

from . import calibration_ledger as cl
from . import calibration_store as cs
from . import cognitive_cockpit as cc
from . import coherence, context_pack, method_memory, secret_guard, task_profile
from . import constrained_choice as cons
from . import live_selector as ls
from . import session_journal as journal

SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)((?:token|api[_-]?key|secret)\s*[=:]\s*)[^\s,;]+"),
)


def safe_error(exc: Exception) -> str:
    if isinstance(exc, (ValueError, PermissionError, TimeoutError)):
        text = str(exc)
    else:
        text = type(exc).__name__
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + "***" if match.lastindex else "***", text)
    return text


def stop(reason: str) -> dict:
    return {"choice": None, "reason": reason, "stop": True}


def completion_gaps(state: dict) -> list[str]:
    facet = task_profile.build_facet_agenda(state)
    coherent = coherence.evaluate(state)
    return (
        ls.unmet(state)
        + ["facet:" + item for item in facet["gaps"]]
        + ["coherence:" + item["id"] for item in coherent["issues"]]
    )


def complete(state: dict) -> bool:
    return not completion_gaps(state)


def first_policy(state: dict, candidates: list[dict]) -> dict:
    return (
        stop("no candidates")
        if not candidates
        else {"choice": 0, "reason": "first candidate", "stop": False}
    )


def last_policy(state: dict, candidates: list[dict]) -> dict:
    return (
        stop("no candidates")
        if not candidates
        else {"choice": len(candidates) - 1, "reason": "last candidate", "stop": False}
    )


def stop_policy(state: dict, candidates: list[dict]) -> dict:
    return stop("policy stop")


def bad_range_policy(state: dict, candidates: list[dict]) -> dict:
    return {"choice": len(candidates) + 1, "reason": "bad", "stop": False}


def bad_score_policy(state: dict, candidates: list[dict]) -> dict:
    return {"choice": 0, "reason": "bad", "stop": False, "score": 1}


def contextual_policy(adapter, providers: list | None = None):
    """把模型 adapter 接到候选上下文包，同时保持短响应协议。"""

    def policy(state: dict, candidates: list[dict]) -> dict:
        payload = cons.build_prompt_payload(state, candidates, providers=providers)
        context_digest = context_pack.digest(payload)
        context_units = payload["context"]["budget"]["estimated_units"]
        source_snapshot = [
            {
                "source": item["source"],
                "path": item["path"],
                "role": item["role"],
                "trust": item["trust"],
                "content_digest": item["content_digest"],
                "file_digest": item["file_digest"],
            }
            for item in payload["context"]["references"]
        ] + [
            {
                "source": item["source"],
                "path": item["path"],
                "role": "graph-source",
                "trust": "local-trusted",
                "content_digest": item["file_digest"],
                "file_digest": item["file_digest"],
            }
            for item in payload["graph_slice"]["sources"]
        ]
        external_context = any(
            source.get("kind") == "mcp-context-provider" for source in payload["context"]["sources"]
        )
        response = adapter(copy.deepcopy(payload))
        if isinstance(response, dict):
            wrapped = ContextualResponse(response)
            wrapped.context_digest = context_digest
            wrapped.context_units = context_units
            wrapped.source_snapshot = source_snapshot
            wrapped.external_context = external_context
            return wrapped
        return response

    policy.providers = providers
    return policy


class ContextualResponse(dict):
    context_digest: str
    context_units: int
    source_snapshot: list[dict]
    external_context: bool


# C901: this is the single transaction boundary for one session turn. Keeping
# validation, selection, execution, calibration and journal commit visible in
# one state machine preserves fail-closed ordering; lower-level logic is
# delegated to tested helpers and modules.
def run(
    prompt: str,
    policy,
    store_path: str | Path | None = None,
    max_turns: int = 8,
    state: dict | None = None,
    journal_path: str | Path | None = None,
    max_seconds: float | None = None,
    max_context_units: int | None = None,
    injections: dict[int, list[str]] | None = None,
) -> dict:
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
    started = time.monotonic()

    def elapsed_seconds() -> float:
        return time.monotonic() - started

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
                source_snapshot = [
                    {
                        "source": item["source"],
                        "path": item["path"],
                        "role": item["role"],
                        "trust": item["trust"],
                        "content_digest": item["content_digest"],
                        "file_digest": item["file_digest"],
                    }
                    for item in payload["context"]["references"]
                ] + [
                    {
                        "source": item["source"],
                        "path": item["path"],
                        "role": "graph-source",
                        "trust": "local-trusted",
                        "content_digest": item["file_digest"],
                        "file_digest": item["file_digest"],
                    }
                    for item in payload["graph_slice"]["sources"]
                ]
            if external_context is None:
                external_context = any(
                    source.get("kind") == "mcp-context-provider"
                    for source in payload["context"]["sources"]
                )
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
                s,
                committed_state,
                c["cluster"],
                c.get("kind", "unknown"),
                c["resolves"],
                sorted(actual),
                result.get("changed_keys", []),
                result.get("atom_trace", []),
                decision_payload,
                calibration_before_digest,
                calibration_after_digest,
                observations,
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
