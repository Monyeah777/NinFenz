"""元认知原子执行器：33 原子的确定性执行与节点轨迹。

- SPECS：每个原子的必需输入、输出键、输出类型；
- EXECUTORS：33 个原子执行器；元原子实现真实逻辑，内容原子适配现有指标；
- execute_node：按节点 atoms 顺序执行，任一失败即 fail-closed。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any


def _digest(obj: Any) -> str:
    try:
        text = json.dumps(
            obj, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
        )
    except Exception:
        text = repr(obj)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fail(atom_id: str, error: str, inp: Any = None) -> dict:
    return {
        "atom_id": atom_id,
        "status": "fail",
        "output": None,
        "error": error,
        "input_digest": _digest(inp),
        "output_digest": "",
    }


SPECS: dict[str, dict] = {
    # content atoms (18)
    "k.represent": {"required": ["target"], "out": "representation", "type": str},
    "k.partition": {"required": ["target"], "out": "parts", "type": list},
    "k.relate": {"required": ["target"], "out": "relations", "type": list},
    "k.abstract": {"required": ["target"], "out": "abstraction", "type": str},
    "k.define": {"required": ["target"], "out": "definition", "type": str},
    "k.instantiate": {"required": ["target"], "out": "instance", "type": dict},
    "k.classify": {"required": ["target"], "out": "classes", "type": list},
    "k.quantify": {"required": ["target"], "out": "measure", "type": dict},
    "m.compare": {"required": ["target"], "out": "diff", "type": dict},
    "m.trace": {"required": ["target"], "out": "trace", "type": list},
    "e.verify": {"required": ["target"], "out": "verified", "type": bool},
    "e.falsify": {"required": ["target"], "out": "attacks", "type": list},
    "e.benchmark": {"required": ["target"], "out": "benchmark", "type": dict},
    "i.merge": {"required": ["target"], "out": "merged", "type": dict},
    "i.reconcile": {"required": ["target"], "out": "resolved", "type": list},
    "i.cluster": {"required": ["target"], "out": "clusters", "type": list},
    "i.hierarchy": {"required": ["target"], "out": "hierarchy", "type": list},
    "i.compose": {"required": ["target"], "out": "composed", "type": dict},
    # meta atoms (15)
    "c.select": {"required": ["options", "goal"], "out": "selected", "type": list},
    "c.sequence": {"required": ["selected"], "out": "order", "type": list},
    "c.allocate": {"required": ["order", "budget"], "out": "allocation", "type": dict},
    "c.switch": {"required": ["allocation", "fallback"], "out": "plan", "type": dict},
    "e.audit": {"required": ["target", "reference"], "out": "audit", "type": list},
    "m.check": {"required": ["audit"], "out": "check", "type": bool},
    "e.adjudicate": {"required": ["check", "audit"], "out": "verdict", "type": dict},
    "m.observe": {"required": ["plan", "budget_state"], "out": "reading", "type": dict},
    "m.estimate": {"required": ["reading"], "out": "confidence", "type": float},
    "m.detect": {"required": ["reading"], "out": "anomalies", "type": list},
    "c.stop": {"required": ["reading", "anomalies"], "out": "decision", "type": dict},
    "k.criterion": {"required": ["frame"], "out": "criteria", "type": list},
    "e.calibrate": {"required": ["audit", "criteria"], "out": "calibration", "type": float},
    "k.standard": {"required": ["task_type", "library"], "out": "standard", "type": dict},
    "i.transfer": {"required": ["standard"], "out": "transfer", "type": dict},
}


def _target(p: dict):
    return p.get("target")


def _k_represent(p):
    return {"representation": str(_target(p))}


def _k_partition(p):
    t = _target(p)
    return {
        "parts": t
        if isinstance(t, list)
        else [x for x in str(t).replace("，", ",").split(",") if x.strip()]
    }


def _k_relate(p):
    t = str(_target(p))
    return {"relations": [x for x in ("→", "->", "导致", "因为", "通过") if x in t]}


def _k_abstract(p):
    return {"abstraction": str(_target(p))[:120]}


def _k_define(p):
    return {"definition": str(_target(p))[:120]}


def _k_instantiate(p):
    return {"instance": {"target": _target(p)}}


def _k_classify(p):
    return {"classes": [str(_target(p))[:40]]}


def _k_quantify(p):
    t = _target(p)
    return {"measure": {"count": len(t) if hasattr(t, "__len__") else 1}}


def _m_compare(p):
    t = _target(p)
    if isinstance(t, (list, tuple)) and len(t) >= 2:
        return {"diff": {"same": t[0] == t[1], "left": t[0], "right": t[1]}}
    return {"diff": {"same": True, "value": t}}


def _m_trace(p):
    return {"trace": [str(_target(p))]}


def _e_verify(p):
    return {"verified": bool(_target(p))}


def _e_falsify(p):
    return {"attacks": []}


def _e_benchmark(p):
    return {"benchmark": {"delta": 0}}


def _i_merge(p):
    t = _target(p)
    return {"merged": t if isinstance(t, dict) else {"items": t}}


def _i_reconcile(p):
    t = _target(p)
    return {"resolved": t if isinstance(t, list) else [t]}


def _i_cluster(p):
    t = _target(p)
    return {"clusters": t if isinstance(t, list) else ([t] if t else [])}


def _i_hierarchy(p):
    value = p.get("relations", _target(p))
    return {
        "hierarchy": list(value) if isinstance(value, (list, tuple)) else ([value] if value else [])
    }


def _i_compose(p):
    t = _target(p)
    return {"composed": t if isinstance(t, dict) else {"parts": t}}


def _c_select(p):
    opts, goal = p["options"], p["goal"]
    if "levels" in goal or "functions" in goal:
        sel = [
            o
            for o in opts
            if o.get("meta_level") in goal.get("levels", [])
            and o.get("meta_function") in goal.get("functions", [])
        ]
    elif "task_type" in goal:
        sel = [o for o in opts if o.get("task_type") == goal["task_type"]]
    else:
        sel = list(opts)
    if not sel:
        raise ValueError("no selection")
    envelope = int((p.get("budget") or {}).get("envelope", len(sel)))
    if envelope < 1:
        raise ValueError("empty selection budget")
    # 路由选择必须在当前动作预算内完成，否则后续 allocate 必然溢出。
    sel = sel[:envelope]
    return {"selected": sel}


def _c_sequence(p):
    order = sorted(
        p["selected"], key=lambda x: (str(x.get("meta_level", "M9")), str(x.get("id", "")))
    )
    return {"order": order}


def _c_allocate(p):
    order, budget = p["order"], p["budget"]
    costs = {o.get("id", str(i)): 1 for i, o in enumerate(order)}
    total = sum(costs.values())
    envelope = int(budget.get("envelope", 0))
    if total > envelope:
        raise ValueError("budget overflow")
    return {"allocation": {"costs": costs, "total": total, "remaining": envelope - total}}


def _c_switch(p):
    alloc = p["allocation"]
    if alloc.get("total", 0) <= 0:
        raise ValueError("empty allocation")
    return {
        "plan": {
            "order": [o.get("id") for o in p["order"]],
            "allocation": alloc,
            "fallback": p.get("fallback", {}),
        }
    }


def _e_audit(p):
    target, ref = p["target"], p["reference"]
    issues = []
    if isinstance(target, dict) and "order" in target:
        ref_ids = {x.get("id") for x in ref} if isinstance(ref, list) else set()
        for nid in target["order"]:
            if nid not in ref_ids:
                issues.append(f"unknown method: {nid}")
    elif isinstance(target, dict) and "rows" in target:
        rows = target.get("rows") or []
        if not rows:
            issues.append("empty criterion frame")
        for r in rows:
            if r.get("unit", "ratio") == "ratio" and "max_missing" not in r:
                issues.append("missing max_missing: {}".format(r.get("dimension")))
        if not ref:
            issues.append("empty node verdicts")
    else:
        if not target:
            issues.append("empty target")
    return {"audit": issues}


def _m_check(p):
    return {"check": len(p["audit"]) == 0}


def _e_adjudicate(p):
    return {"verdict": {"status": "pass" if p["check"] else "fail", "reasons": p["audit"]}}


def _m_observe(p):
    plan, budget = p["plan"], p["budget_state"]
    return {
        "reading": {
            "nodes": len(plan.get("order", [])),
            "budget_used": plan.get("allocation", {}).get("total", 0),
            "budget_remaining": int(budget.get("remaining", 0)),
        }
    }


def _m_estimate(p):
    r = p["reading"]
    return {"confidence": 1.0 if r["nodes"] > 0 and r["budget_remaining"] >= 0 else 0.0}


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
