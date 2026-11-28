"""目标回归规划：从 need 反推 1-3 原子链。"""

from __future__ import annotations

from . import live_selector as ls

GOAL_KEY = {
    "structure": "parts",
    "relations": "relations",
    "risks": "risks",
    "synthesis": "plan",
    "grounding": "verified",
    "resolve": "open_questions",
}


def compatible(chain: tuple[str, ...]) -> bool:
    for i, a in enumerate(chain):
        for b in chain[i + 1 :]:
            if (
                b in ls.CONTRACTS[a]["incompatible_with"]
                or a in ls.CONTRACTS[b]["incompatible_with"]
            ):
                return False
    return True


def achievers(key: str) -> list[str]:
    if key == "open_questions":
        return [c["id"] for c in ls.CONTRACTS.values() if key in c["removes"]]
    return [c["id"] for c in ls.CONTRACTS.values() if key in c["adds"]]


def _extend_chains(
    chains: list[tuple[int, tuple[str, ...]]], sub: tuple[int, tuple[str, ...]]
) -> list[tuple[int, tuple[str, ...]]]:
    """把一个前置子链并进现有链，丢重复原子，只留最优一条（防爆炸）。"""
    merged = [(cost + sub[0], chain + sub[1]) for cost, chain in chains]
    merged = [(cost, chain) for cost, chain in merged if len(set(chain)) == len(chain)]
    return sorted(merged, key=lambda x: (x[0], len(x[1])))[:1]


def _atom_plan(
    atom_id: str, s: dict, budget: int, used: frozenset[str]
) -> tuple[int, tuple[str, ...]] | None:
    """单个原子作为最后一步的候选链 → (total, chain)，不可行返 None。"""
    c = ls.CONTRACTS[atom_id]
    if c["cost"] > budget:
        return None
    chains: list[tuple[int, tuple[str, ...]]] = [(0, ())]
    for req in c["requires"]:
        sub = plan_key(req, s, budget - c["cost"], used | {atom_id})
        if sub is None:
            return None
        chains = _extend_chains(chains, sub)
    cost, chain = chains[0]
    new_chain = chain + (atom_id,)
    if len(set(new_chain)) != len(new_chain):
        return None
    if not compatible(new_chain):
        return None
    if ls.simulate(new_chain, s) is None:
        return None
    total = cost + c["cost"]
    if total > budget:
        return None
    return total, new_chain


def plan_key(
    key: str, s: dict, budget: int, used: frozenset[str] = frozenset()
) -> tuple[int, tuple[str, ...]] | None:
    avail = ls.available_keys(s)
    if key == "open_questions":
        if key not in avail:
            return (0, ())
    elif key in avail:
        return (0, ())
    best = None
    for atom_id in achievers(key):
        if atom_id in used:
            continue
        candidate = _atom_plan(atom_id, s, budget, used)
        if candidate is None:
            continue
        total, new_chain = candidate
        if best is None or total < best[0]:
            best = (total, new_chain)
    return best


def _plan_resolve(s: dict, max_cost: int) -> dict | None:
    if not s.get("open_questions"):
        return None
    avail = ls.available_keys(s)
    for atom_id in achievers("open_questions"):
        c = ls.CONTRACTS[atom_id]
        if c["cost"] > max_cost or not set(c["requires"]) <= avail:
            continue
        single = (atom_id,)
        if ls.simulate(single, s) is None:
            continue
        res = ls.resolved(single, s)
        if "resolve" in res:
            return {
                "goal": "resolve",
                "cluster": list(single),
                "cost": c["cost"],
                "resolves": res,
            }
    return None


def plan_for_goal(goal: str, s: dict, max_cost: int = 3) -> dict | None:
    key = GOAL_KEY[goal]
    if goal == "resolve":
        return _plan_resolve(s, max_cost)
    if key in ls.available_keys(s):
        return None
    p = plan_key(key, s, max_cost)
    if p is None:
        return None
    plan_cost, plan_chain = p
    res = ls.resolved(plan_chain, s)
    if not res:
        return None
    return {"goal": goal, "cluster": list(plan_chain), "cost": plan_cost, "resolves": res}


def plan_all(s: dict, max_cost: int = 3) -> list[dict]:
    out = []
    seen = set()
    for goal in ls.unmet(s):
        p = plan_for_goal(goal, s, max_cost)
        if p and tuple(p["cluster"]) not in seen:
            seen.add(tuple(p["cluster"]))
            out.append(p)
    return out
