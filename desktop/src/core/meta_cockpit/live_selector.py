"""活体选择器：原子前后条件 → 1-3 原子候选簇 → 结构优先级。

优先级 = 解决未满足 need 数 / 成本；不是质量评分，不进入驾驶舱结果。
"""

from __future__ import annotations

import copy
import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import TypedDict

from . import json_asset

BASE = Path(__file__).parent
CONTRACTS = {c["id"]: c for c in json_asset.load(BASE / "atom_contracts.json")["contracts"]}
CONTRACTS_DIGEST = hashlib.sha256((BASE / "atom_contracts.json").read_bytes()).hexdigest()
CACHE_LIMIT = 256
MAX_SEARCH_EXPANSIONS = 2000
MAX_SEARCH_GENERATED = 10000
_CANDIDATE_CACHE: OrderedDict = OrderedDict()
_CACHE_STATS = {"hits": 0, "misses": 0, "evictions": 0}
_LAST_SEARCH_STATS: dict = {}


class SearchState(TypedDict):
    chain: tuple[str, ...]
    avail: set[str]
    cost: int


NEEDS = ["structure", "relations", "risks", "synthesis", "grounding", "resolve"]
NEED_KEY = {
    "structure": "parts",
    "relations": "relations",
    "risks": "risks",
    "synthesis": "plan",
    "grounding": "verified",
}
TOP_KEYS = (
    "goal",
    "options",
    "budget",
    "fallback",
    "reference",
    "library",
    "task_type",
    "frame",
    "budget_state",
)
PRESENT_WHEN_EMPTY = {"audit", "anomalies", "check"}


def available_keys(s: dict) -> set[str]:
    keys = set()
    for k, v in s["artifact"].items():
        if v not in ("", [], False, None) or k in PRESENT_WHEN_EMPTY:
            keys.add(k)
    for k in TOP_KEYS:
        if k in s and s[k] not in (None, "", [], False):
            keys.add(k)
    # 驾驶舱把 goal 投影为执行器可读的 target；参考面由 NF 资产适配层
    # 提供，不是模型可自由伪造的输入。
    if s.get("goal"):
        keys.update(("goal", "target", "reference"))
    unmet_now = [n for n in NEEDS if not need_met(n, keys)]
    if len(unmet_now) >= 2:
        # 这是驾驶舱当前可选的结构缺口，不是预设全程计划。
        keys.add("options")
    if s.get("open_questions"):
        keys.add("open_questions")
    return keys


def need_met(need: str, keys: set[str]) -> bool:
    if need == "resolve":
        return "open_questions" not in keys
    return NEED_KEY[need] in keys


def unmet(s: dict) -> list[str]:
    keys = available_keys(s)
    return [n for n in NEEDS if not need_met(n, keys)]


def simulate(chain: tuple[str, ...], s: dict) -> set[str] | None:
    avail = available_keys(s)
    for atom_id in chain:
        c = CONTRACTS[atom_id]
        if not set(c["requires"]) <= avail:
            return None
        avail |= set(c["adds"])
        avail -= set(c["removes"])
    return avail


def resolved(chain: tuple[str, ...], s: dict) -> list[str]:
    before = available_keys(s)
    after = simulate(chain, s)
    if after is None:
        return []
    return [n for n in NEEDS if not need_met(n, before) and need_met(n, after)]


def _compatible(chain: tuple[str, ...], atom_id: str) -> bool:
    c = CONTRACTS[atom_id]
    for x in chain:
        if atom_id in CONTRACTS[x]["incompatible_with"] or x in c["incompatible_with"]:
            return False
    return True


def _bounded_search(s: dict, max_len: int, beam_width: int) -> list[dict]:
    """枚举 1-3 原子链，并按结构增量裁剪下一层搜索面。"""
    before = available_keys(s)
    frontier: list[SearchState] = [{"chain": (), "avail": before, "cost": 0}]
    records: list[dict] = []
    expansions = 0
    generated = 0
    frontier_peak = 1
    for _ in range(max_len):
        seen = set()
        level = []
        for parent in frontier:
            expansions += 1
            if expansions > MAX_SEARCH_EXPANSIONS:
                raise ValueError("candidate search expansion budget exceeded")
            chain, avail = parent["chain"], parent["avail"]
            for atom_id, c in CONTRACTS.items():
                if atom_id in chain or not _compatible(chain, atom_id):
                    continue
                nc = chain + (atom_id,)
                if nc in seen or not set(c["requires"]) <= avail:
                    continue
                seen.add(nc)
                generated += 1
                if generated > MAX_SEARCH_GENERATED:
                    raise ValueError("candidate search generation budget exceeded")
                after = set(avail)
                after.update(c["adds"])
                after.difference_update(c["removes"])
                cost = parent["cost"] + c["cost"]
                level.append(
                    {
                        "chain": nc,
                        "cost": cost,
                        "avail": after,
                        "resolves": [
                            need
                            for need in NEEDS
                            if not need_met(need, before) and need_met(need, after)
                        ],
                        "effect": {
                            "adds": sorted(after - before),
                            "removes": sorted(before - after),
                        },
                    }
                )
        records.extend(level)
        level.sort(
            key=lambda x: (
                -len(x["resolves"]),
                -len(x["effect"]["adds"]),
                len(x["chain"]),
                x["chain"],
            )
        )
        frontier = [
            {"chain": item["chain"], "avail": item["avail"], "cost": item["cost"]}
            for item in level[:beam_width]
        ]
        frontier_peak = max(frontier_peak, len(frontier))
    global _LAST_SEARCH_STATS
    _LAST_SEARCH_STATS = {
        "cache_hit": False,
        "expansions": expansions,
        "generated": generated,
        "records": len(records),
        "frontier_peak": frontier_peak,
        "beam_width": beam_width,
        "max_len": max_len,
        "max_expansions": MAX_SEARCH_EXPANSIONS,
        "max_generated": MAX_SEARCH_GENERATED,
        "budget_exhausted": False,
    }
    return records


def _direct_from_records(records: list[dict], max_cost: int, limit: int) -> list[dict]:
    out = []
    for rec in records:
        if not rec["resolves"] or rec["cost"] > max_cost:
            continue
        out.append(
            {
                "cluster": list(rec["chain"]),
                "resolves": rec["resolves"],
                "priority": round(len(rec["resolves"]) / rec["cost"], 3),
                "cost": rec["cost"],
            }
        )
    out.sort(key=lambda x: (-x["priority"], len(x["cluster"]), x["cluster"]))
    return out[:limit]


def _progress_from_records(records: list[dict], max_cost: int, limit: int) -> list[dict]:
    out = []
    for rec in records:
        if rec["cost"] > max_cost:
            continue
        if not rec["effect"]["adds"] and not rec["effect"]["removes"]:
            continue
        out.append(
            {
                "cluster": list(rec["chain"]),
                "resolves": rec["resolves"],
                "cost": rec["cost"],
                "effect": rec["effect"],
            }
        )
    out.sort(
        key=lambda x: (
            len(x["cluster"]),
            -len(x["resolves"]),
            -len(x["effect"]["adds"]),
            x["cluster"],
        )
    )
    return out[:limit]


def candidate_families(
    s: dict,
    max_len: int = 3,
    direct_limit: int = 5,
    progress_limit: int = 12,
    max_cost: int = 3,
    beam_width: int = 192,
) -> dict:
    before = frozenset(available_keys(s))
    key = (CONTRACTS_DIGEST, before, max_len, direct_limit, progress_limit, max_cost, beam_width)
    if key in _CANDIDATE_CACHE:
        _CACHE_STATS["hits"] += 1
        _CANDIDATE_CACHE.move_to_end(key)
        global _LAST_SEARCH_STATS
        _LAST_SEARCH_STATS = {
            "cache_hit": True,
            "expansions": 0,
            "generated": 0,
            "records": 0,
            "frontier_peak": 0,
            "beam_width": beam_width,
            "max_len": max_len,
            "max_expansions": MAX_SEARCH_EXPANSIONS,
            "max_generated": MAX_SEARCH_GENERATED,
            "budget_exhausted": False,
        }
        return copy.deepcopy(_CANDIDATE_CACHE[key])
    _CACHE_STATS["misses"] += 1
    records = _bounded_search(s, max_len, beam_width)
    result = {
        "direct": _direct_from_records(records, max_cost, direct_limit),
        "progress": _progress_from_records(records, max_cost, progress_limit),
    }
    _CANDIDATE_CACHE[key] = copy.deepcopy(result)
    if len(_CANDIDATE_CACHE) > CACHE_LIMIT:
        _CANDIDATE_CACHE.popitem(last=False)
        _CACHE_STATS["evictions"] += 1
    return result


def candidate_cache_stats() -> dict:
    return {**_CACHE_STATS, "size": len(_CANDIDATE_CACHE), "limit": CACHE_LIMIT}


def candidate_cache_clear() -> None:
    _CANDIDATE_CACHE.clear()
    for key in _CACHE_STATS:
        _CACHE_STATS[key] = 0
    _LAST_SEARCH_STATS.clear()


def search_stats() -> dict:
    return copy.deepcopy(_LAST_SEARCH_STATS)


def candidates(
    s: dict, max_len: int = 3, limit: int = 5, max_cost: int = 3, beam_width: int = 192
) -> list[dict]:
    return candidate_families(
        s,
        max_len=max_len,
        direct_limit=limit,
        progress_limit=0,
        max_cost=max_cost,
        beam_width=beam_width,
    )["direct"]


def progress_candidates(
    s: dict, max_len: int = 3, limit: int = 12, max_cost: int = 3, beam_width: int = 192
) -> list[dict]:
    """返回会扩展能力状态面的候选，包括不直接兑现 need 的准备态。

    `resolves` 仍是结构缺口，不是质量分；准备态必须至少新增或移除一个
    当前契约键，否则不会进入候选，保证有限状态上不会空转。
    """
    return candidate_families(
        s,
        max_len=max_len,
        direct_limit=0,
        progress_limit=limit,
        max_cost=max_cost,
        beam_width=beam_width,
    )["progress"]


def select(s: dict, max_cost: int = 3) -> dict:
    c = candidates(s, limit=1, max_cost=max_cost)
    return c[0] if c else {"cluster": [], "resolves": [], "priority": 0, "cost": 0}
