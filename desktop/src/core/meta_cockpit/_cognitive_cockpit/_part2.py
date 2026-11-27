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


def execute_cluster(s: dict, cluster: list[str], thought_patch: dict | None = None) -> dict:
    """事务式执行一个 1-3 原子簇。

    先在状态副本上执行；任一原子失败则不提交任何前缀状态。
    返回的 state 是新副本，调用方可将其作为下一轮唯一合法状态。
    """
    if not 1 <= len(cluster) <= 3 or len(set(cluster)) != len(cluster):
        return {
            "status": "fail",
            "state": s,
            "resolved": [],
            "error": "cluster must contain 1-3 unique atoms",
            "atom_trace": [],
        }
    if thought_patch is not None:
        issues = epistemic_agenda.validate_thought_patch({"cluster": cluster}, thought_patch)
        if issues:
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "thought patch: " + "; ".join(issues),
                "atom_trace": [],
            }
    before_keys = ls.available_keys(s)
    before = _met(s)
    work = copy.deepcopy(s)
    atom_trace = []
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
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "{}: {}".format(atom_id, res["error"]),
                "atom_trace": atom_trace,
            }
        _enrich(work, atom_id, res["output"])
        if thought_patch:
            for key in ls.CONTRACTS[atom_id]["adds"]:
                if key in thought_patch:
                    work["artifact"][key] = copy.deepcopy(thought_patch[key])
    after_keys = ls.available_keys(work)
    after = _met(work)
    resolved = [k for k in before if not before[k] and after[k]]
    unresolved = epistemic_agenda.unresolved_after(work, resolved)
    if unresolved:
        return {
            "status": "fail",
            "state": s,
            "resolved": [],
            "error": "thought patch did not close: " + ",".join(unresolved),
            "atom_trace": atom_trace,
        }
    if thought_patch is not None:
        regressions = coherence.new_issue_ids(s, work)
        if regressions:
            return {
                "status": "fail",
                "state": s,
                "resolved": [],
                "error": "thought patch introduced incoherence: " + ",".join(regressions),
                "atom_trace": atom_trace,
            }
    return {
        "status": "pass",
        "state": work,
        "resolved": resolved,
        "error": "",
        "atom_trace": atom_trace,
        "changed_keys": sorted(after_keys - before_keys),
    }


def think(
    prompt: str,
    injections: dict | None = None,
    max_turns: int = 8,
    store_path: str | Path | None = None,
) -> tuple[dict, list[dict]]:
    s = initial_state(prompt)
    store_file = Path(store_path) if store_path is not None else None
    if store_file is not None:
        store, status = cal_store.load(store_file)
        ledger = store["atoms"]
        s["store_status"] = status
        if status.startswith("tampered:"):
            s["error"] = "calibration store: " + status
            return s, []
    else:
        store = None
        ledger = cal_ledger.initial_ledger()
    injections = injections or {}
    trace = []
    while s["turn"] < max_turns:
        if s["turn"] in injections:
            s["open_questions"].append(injections[s["turn"]])
        need = infer_need(s)
        if need == "done":
            break
        cluster = compose(s, ledger)
        d = s.get("_last_decision", {})
        if d.get("action") == "stop":
            trace.append(
                {
                    "turn": s["turn"] + 1,
                    "need": need,
                    "goal": None,
                    "cluster": [],
                    "resolved": [],
                    "calibration_error": 0,
                    "action": "stop",
                    "reason": d.get("reason"),
                    "changed": False,
                    "reliability_band": "n/a",
                }
            )
            break
        before_keys = ls.available_keys(s)
        applied = execute_cluster(s, cluster)
        if applied["status"] != "pass":
            s["error"] = applied["error"]
            break
        after_keys = ls.available_keys(applied["state"])
        actual = applied["resolved"]
        cal = control.calibration(d.get("resolves", []), actual)
        if cal["error"] > 0:
            s["error"] = f"calibration mismatch: {cal}"
            break
        s = applied["state"]
        cal_ledger.observe(ledger, cluster, after_keys)
        rel_band = cal_ledger.band(cal_ledger.avg_reliability(ledger, cluster))
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
    if store is not None and store_file is not None:
        saved = cal_store.save(store_file, store)
        s["calibration_rounds"] = saved["rounds"]
    return s, trace
