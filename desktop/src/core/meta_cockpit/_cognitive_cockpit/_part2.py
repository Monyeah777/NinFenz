"""core.cognitive_cockpit 私有实现分片 2/2（对外只经 core.cognitive_cockpit 门面导入）： 等"""

from __future__ import annotations

import copy
from pathlib import Path

from core.meta_cockpit import calibration_ledger as cal_ledger
from core.meta_cockpit import calibration_store as cal_store
from core.meta_cockpit import coherence, epistemic_agenda
from core.meta_cockpit import live_selector as ls
from core.meta_cockpit import meta_atom_runtime as atoms
from core.meta_cockpit import metacognitive_control as control

from ._part1 import _enrich, _met, _payload, compose, infer_need, initial_state


def _cluster_fail(s: dict, error: str, atom_trace: list[dict]) -> dict:
    return {
        "status": "fail",
        "state": s,
        "resolved": [],
        "error": error,
        "atom_trace": atom_trace,
    }


def _apply_patch(work: dict, atom_id: str, thought_patch: dict) -> None:
    for key in ls.CONTRACTS[atom_id]["adds"]:
        if key in thought_patch:
            work["artifact"][key] = copy.deepcopy(thought_patch[key])


def _run_atoms(
    work: dict, cluster: list[str], thought_patch: dict | None
) -> tuple[list[dict], str | None]:
    atom_trace: list[dict] = []
    for atom_id in cluster:
        res = atoms.execute_atom(atom_id, _payload(work))
        atom_trace.append(
            {
                "atom_id": atom_id,
                "status": res["status"],
                "input_digest": res["input_digest"],
                "output_digest": res["output_digest"],
            }
        )
        if res["status"] != "pass":
            return atom_trace, "{}: {}".format(atom_id, res["error"])
        _enrich(work, atom_id, res["output"])
        if thought_patch:
            _apply_patch(work, atom_id, thought_patch)
    return atom_trace, None


def _closing_issue(
    s: dict, work: dict, resolved: list[str], thought_patch: dict | None
) -> str | None:
    unresolved = epistemic_agenda.unresolved_after(work, resolved)
    if unresolved:
        return "thought patch did not close: " + ",".join(unresolved)
    if thought_patch is not None:
        regressions = coherence.new_issue_ids(s, work)
        if regressions:
            return "thought patch introduced incoherence: " + ",".join(regressions)
    return None


def execute_cluster(s: dict, cluster: list[str], thought_patch: dict | None = None) -> dict:
    """事务式执行一个 1-3 原子簇。

    先在状态副本上执行；任一原子失败则不提交任何前缀状态。
    返回的 state 是新副本，调用方可将其作为下一轮唯一合法状态。
    """
    if not 1 <= len(cluster) <= 3 or len(set(cluster)) != len(cluster):
        return _cluster_fail(s, "cluster must contain 1-3 unique atoms", [])
    if thought_patch is not None:
        issues = epistemic_agenda.validate_thought_patch({"cluster": cluster}, thought_patch)
        if issues:
            return _cluster_fail(s, "thought patch: " + "; ".join(issues), [])
    before_keys = ls.available_keys(s)
    before = _met(s)
    work = copy.deepcopy(s)
    atom_trace, error = _run_atoms(work, cluster, thought_patch)
    if error is not None:
        return _cluster_fail(s, error, atom_trace)
    after_keys = ls.available_keys(work)
    after = _met(work)
    resolved = [k for k in before if not before[k] and after[k]]
    closing = _closing_issue(s, work, resolved, thought_patch)
    if closing is not None:
        return _cluster_fail(s, closing, atom_trace)
    return {
        "status": "pass",
        "state": work,
        "resolved": resolved,
        "error": "",
        "atom_trace": atom_trace,
        "changed_keys": sorted(after_keys - before_keys),
    }


def _load_store(store_path) -> tuple[Path | None, dict | None, dict, str]:
    store_file = Path(store_path) if store_path is not None else None
    if store_file is None:
        return None, None, cal_ledger.initial_ledger(), ""
    store, status = cal_store.load(store_file)
    return store_file, store, store["atoms"], status


def _normalized_injections(injections: dict | None) -> dict:
    return injections or {}


def _save_rounds(store: dict | None, store_file: Path | None) -> int | None:
    if store is None or store_file is None:
        return None
    return cal_store.save(store_file, store)["rounds"]


def _calibrate(ledger: dict, cluster: list[str], applied: dict, d: dict) -> tuple:
    after_keys = ls.available_keys(applied["state"])
    actual = applied["resolved"]
    cal = control.calibration(d.get("resolves", []), actual)
    if cal["error"] > 0:
        return after_keys, actual, cal, None
    cal_ledger.observe(ledger, cluster, after_keys)
    rel_band = cal_ledger.band(cal_ledger.avg_reliability(ledger, cluster))
    return after_keys, actual, cal, rel_band


def _stop_trace(turn: int, need: str, reason) -> dict:
    return {
        "turn": turn,
        "need": need,
        "goal": None,
        "cluster": [],
        "resolved": [],
        "calibration_error": 0,
        "action": "stop",
        "reason": reason,
        "changed": False,
        "reliability_band": "n/a",
    }


def _turn_need(s: dict, injections: dict) -> str:
    if s["turn"] in injections:
        s["open_questions"].append(injections[s["turn"]])
    return infer_need(s)


def _apply_rounds(s: dict, store: dict | None, store_file: Path | None) -> None:
    rounds = _save_rounds(store, store_file)
    if rounds is not None:
        s["calibration_rounds"] = rounds


def think(
    prompt: str,
    injections: dict | None = None,
    max_turns: int = 8,
    store_path: str | Path | None = None,
) -> tuple[dict, list[dict]]:
    s = initial_state(prompt)
    store_file, store, ledger, store_status = _load_store(store_path)
    if store_status:
        s["store_status"] = store_status
        if store_status.startswith("tampered:"):
            s["error"] = "calibration store: " + store_status
            return s, []
    injections = _normalized_injections(injections)
    trace = []
    while s["turn"] < max_turns:
        need = _turn_need(s, injections)
        if need == "done":
            break
        cluster = compose(s, ledger)
        d = s.get("_last_decision", {})
        if d.get("action") == "stop":
            trace.append(_stop_trace(s["turn"] + 1, need, d.get("reason")))
            break
        before_keys = ls.available_keys(s)
        applied = execute_cluster(s, cluster)
        if applied["status"] != "pass":
            s["error"] = applied["error"]
            break
        after_keys, actual, cal, rel_band = _calibrate(ledger, cluster, applied, d)
        if cal["error"] > 0:
            s["error"] = f"calibration mismatch: {cal}"
            break
        s = applied["state"]
        trace.append(
            {
                "turn": s["turn"] + 1,
                "need": need,
                "cluster": cluster,
                "goal": d.get("goal"),
                "resolved": actual,
                "calibration_error": cal["error"],
                "reliability_band": rel_band,
                "action": d.get("action", "continue"),
                "changed": before_keys != after_keys,
            }
        )
        s["turn"] += 1
        if before_keys == after_keys and not s["open_questions"]:
            break
    _apply_rounds(s, store, store_file)
    return s, trace
