"""core.meta_atom_runtime 私有实现分片 1/2（对外只经 core.meta_atom_runtime 门面导入）： 等"""

from __future__ import annotations

import hashlib
import json
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


def _select_options(opts: list[dict], goal: dict) -> list[dict]:
    if "levels" in goal or "functions" in goal:
        return [
            o
            for o in opts
            if o.get("meta_level") in goal.get("levels", [])
            and o.get("meta_function") in goal.get("functions", [])
        ]
    if "task_type" in goal:
        return [o for o in opts if o.get("task_type") == goal["task_type"]]
    return list(opts)


def _c_select(p):
    opts, goal = p["options"], p["goal"]
    sel = _select_options(opts, goal)
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


def _audit_order(target: dict, ref) -> list[str]:
    issues = []
    ref_ids = {x.get("id") for x in ref} if isinstance(ref, list) else set()
    for nid in target["order"]:
        if nid not in ref_ids:
            issues.append(f"unknown method: {nid}")
    return issues


def _audit_rows(target: dict, ref) -> list[str]:
    issues = []
    rows = target.get("rows") or []
    if not rows:
        issues.append("empty criterion frame")
    for r in rows:
        if r.get("unit", "ratio") == "ratio" and "max_missing" not in r:
            issues.append("missing max_missing: {}".format(r.get("dimension")))
    if not ref:
        issues.append("empty node verdicts")
    return issues


def _e_audit(p):
    target, ref = p["target"], p["reference"]
    if isinstance(target, dict) and "order" in target:
        return {"audit": _audit_order(target, ref)}
    if isinstance(target, dict) and "rows" in target:
        return {"audit": _audit_rows(target, ref)}
    if not target:
        return {"audit": ["empty target"]}
    return {"audit": []}


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
