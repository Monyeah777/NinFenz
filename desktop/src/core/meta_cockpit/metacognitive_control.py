"""元认知控制：EVC 继续/停止 + 预测/实际校准。"""

from __future__ import annotations

from . import atom_planner
from . import calibration_ledger as ledger_mod
from . import live_selector as ls
from . import plan_compiler as plan_compile

CONTROL_VALUE = 3.0
COST_WEIGHT = 1.0


def control_value(plan: dict, s: dict, ledger: dict | None = None) -> float:
    ledger = ledger or ledger_mod.initial_ledger()
    rel = ledger_mod.avg_reliability(ledger, plan["cluster"])
    return round(len(plan["resolves"]) * CONTROL_VALUE * rel - plan["cost"] * COST_WEIGHT, 3)


def decide_compiled(
    s: dict, ledger: dict | None = None, max_cost: int = 3, threshold: float = 0.0
) -> dict | None:
    ledger = ledger or ledger_mod.initial_ledger()
    try:
        comp = plan_compile.compile_goals(s, goals=None, max_cost=max_cost)
    except ValueError:
        return None
    goals, stages = comp["goals"], comp["stages"]
    if not goals or not stages:
        return None
    atoms = [a for st in stages for a in st]
    rel = ledger_mod.avg_reliability(ledger, atoms)
    cost = sum(ls.CONTRACTS[a]["cost"] for a in atoms)
    cv = len(goals) * CONTROL_VALUE * rel - cost
    if rel < ledger_mod.RELIABILITY_FLOOR or cv <= threshold:
        return {
            "action": "stop",
            "reason": "no reliable compiled plan",
            "cluster": [],
            "resolves": [],
            "goal": ",".join(goals),
        }
    cluster: list[str] = []
    for st in stages:
        if len(cluster) + len(st) > 3:
            break
        cluster += st
    if not cluster:
        cluster = stages[0][:1]
    if any(ledger[a]["reliability"] < ledger_mod.RELIABILITY_FLOOR for a in cluster):
        return {
            "action": "stop",
            "reason": "cluster reliability below floor",
            "cluster": [],
            "resolves": [],
            "goal": ",".join(goals),
        }
    return {
        "action": "continue",
        "reason": "compiled plan",
        "goal": ",".join(goals),
        "goals": goals,
        "cluster": cluster,
        "resolves": ls.resolved(tuple(cluster), s),
        "reliability": ledger_mod.avg_reliability(ledger, cluster),
        "plan_reliability": rel,
    }


def decide(s: dict, ledger: dict | None = None, max_cost: int = 3, threshold: float = 0.0) -> dict:
    ledger = ledger or ledger_mod.initial_ledger()
    plans = atom_planner.plan_all(s, max_cost)
    scored = []
    for p in plans:
        cv = control_value(p, s, ledger)
        rel = ledger_mod.avg_reliability(ledger, p["cluster"])
        if cv > threshold:
            scored.append({**p, "control_value": cv, "reliability": rel})
    scored = [x for x in scored if x["reliability"] >= ledger_mod.RELIABILITY_FLOOR]
    if not scored:
        return {
            "action": "stop",
            "reason": "no reliable positive control value",
            "cluster": [],
            "resolves": [],
            "goal": None,
        }
    scored.sort(key=lambda x: (-x["control_value"], x["cost"], x["cluster"]))
    best = scored[0]
    return {
        "action": "continue",
        "reason": "positive control value",
        "goal": best["goal"],
        "cluster": best["cluster"],
        "resolves": best["resolves"],
        "cost": best["cost"],
        "reliability": best["reliability"],
    }


def calibration(predicted: list[str], actual: list[str]) -> dict:
    pred, act = set(predicted), set(actual)
    return {"error": len(pred ^ act), "missed": sorted(pred - act), "extra": sorted(act - pred)}
