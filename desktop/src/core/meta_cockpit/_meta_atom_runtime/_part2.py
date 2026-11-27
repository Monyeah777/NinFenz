"""core.meta_atom_runtime 私有实现分片 2/2（对外只经 core.meta_atom_runtime 门面导入）： 等"""

from __future__ import annotations

from collections.abc import Callable

from ._part1 import (
    SPECS,
    _c_allocate,
    _c_select,
    _c_sequence,
    _c_switch,
    _digest,
    _e_adjudicate,
    _e_audit,
    _e_benchmark,
    _e_falsify,
    _e_verify,
    _fail,
    _i_cluster,
    _i_compose,
    _i_hierarchy,
    _i_merge,
    _i_reconcile,
    _k_abstract,
    _k_classify,
    _k_define,
    _k_instantiate,
    _k_partition,
    _k_quantify,
    _k_relate,
    _k_represent,
    _m_check,
    _m_compare,
    _m_estimate,
    _m_observe,
    _m_trace,
)


def _m_detect(p):
    r = p["reading"]
    anomalies = []
    if r["budget_remaining"] < 0:
        anomalies.append("budget_overflow")
    if r["nodes"] == 0:
        anomalies.append("empty_plan")
    return {"anomalies": anomalies}


def _c_stop(p):
    a = p["anomalies"]
    return {"decision": {"action": "stop" if a else "continue", "reasons": a}}


def _k_criterion(p):
    rows = p["frame"].get("rows") or []
    issues = []
    if not rows:
        issues.append("empty criterion frame")
    for r in rows:
        if r.get("unit", "ratio") == "ratio" and "max_missing" not in r:
            issues.append("missing max_missing: {}".format(r.get("dimension")))
    if issues:
        raise ValueError("; ".join(issues))
    return {"criteria": rows}


def _e_calibrate(p):
    if p["audit"]:
        raise ValueError("frame audit issues")
    return {"calibration": 1.0}


def _k_standard(p):
    if p.get("selected"):
        return {"standard": p["selected"][0]}
    match = [x for x in p["library"] if x.get("task_type") == p["task_type"]]
    if not match:
        raise ValueError("unknown task type: {}".format(p["task_type"]))
    return {"standard": match[0]}


def _i_transfer(p):
    s = p["standard"]
    return {"transfer": {"from": s.get("task_type"), "to": "meta-audit", "standard": s.get("id")}}


EXECUTORS: dict[str, Callable[[dict], dict]] = {
    "k.represent": _k_represent,
    "k.partition": _k_partition,
    "k.relate": _k_relate,
    "k.abstract": _k_abstract,
    "k.define": _k_define,
    "k.instantiate": _k_instantiate,
    "k.classify": _k_classify,
    "k.quantify": _k_quantify,
    "m.compare": _m_compare,
    "m.trace": _m_trace,
    "e.verify": _e_verify,
    "e.falsify": _e_falsify,
    "e.benchmark": _e_benchmark,
    "i.merge": _i_merge,
    "i.reconcile": _i_reconcile,
    "i.cluster": _i_cluster,
    "i.hierarchy": _i_hierarchy,
    "i.compose": _i_compose,
    "c.select": _c_select,
    "c.sequence": _c_sequence,
    "c.allocate": _c_allocate,
    "c.switch": _c_switch,
    "e.audit": _e_audit,
    "m.check": _m_check,
    "e.adjudicate": _e_adjudicate,
    "m.observe": _m_observe,
    "m.estimate": _m_estimate,
    "m.detect": _m_detect,
    "c.stop": _c_stop,
    "k.criterion": _k_criterion,
    "e.calibrate": _e_calibrate,
    "k.standard": _k_standard,
    "i.transfer": _i_transfer,
}


def execute_atom(atom_id: str, payload: dict) -> dict:
    if atom_id not in SPECS:
        return _fail(atom_id, "unknown atom", payload)
    if atom_id not in EXECUTORS:
        return _fail(atom_id, "missing executor", payload)
    spec = SPECS[atom_id]
    missing = [k for k in spec["required"] if k not in payload]
    if missing:
        return _fail(atom_id, f"missing inputs: {missing}", payload)
    inp = _digest(payload)
    try:
        out = EXECUTORS[atom_id](payload)
    except Exception as exc:
        return _fail(atom_id, str(exc), payload)
    key, typ = spec["out"], spec["type"]
    if not isinstance(out, dict) or key not in out:
        return _fail(atom_id, f"missing output key: {key}", payload)
    val = out[key]
    if typ is float:
        good = isinstance(val, (int, float)) and not isinstance(val, bool)
    elif typ is bool:
        good = isinstance(val, bool)
    else:
        good = isinstance(val, typ)
    if not good:
        return _fail(atom_id, f"output type mismatch: {key}", payload)
    return {
        "atom_id": atom_id,
        "status": "pass",
        "output": out,
        "error": "",
        "input_digest": inp,
        "output_digest": _digest(out),
    }


def execute_node(node: dict, inputs: dict) -> dict:
    payload = dict(inputs)
    trace = []
    for atom_id in node.get("atoms", []):
        res = execute_atom(atom_id, payload)
        trace.append(res)
        if res["status"] != "pass":
            return {
                "node_id": node["id"],
                "status": "fail",
                "error": "{}: {}".format(atom_id, res["error"]),
                "atom_trace": trace,
                "output": None,
            }
        payload.update(res["output"])
    verdict = payload.get("verdict")
    if isinstance(verdict, dict) and verdict.get("status") == "fail":
        return {
            "node_id": node["id"],
            "status": "fail",
            "error": "adjudication failed: {}".format(verdict.get("reasons")),
            "atom_trace": trace,
            "output": payload,
        }
    return {
        "node_id": node["id"],
        "status": "pass",
        "error": "",
        "atom_trace": trace,
        "output": payload,
    }
