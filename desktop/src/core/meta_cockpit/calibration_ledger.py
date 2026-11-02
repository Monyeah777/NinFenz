"""原子可靠性账本：预测效果 vs 实际落地，监控→控制。"""

from __future__ import annotations

from . import live_selector as ls

PRIOR_SUCCESS = 8
PRIOR_TRIALS = 10
RELIABILITY_FLOOR = 0.5


def initial_ledger() -> dict:
    return {
        aid: {
            "successes": PRIOR_SUCCESS,
            "trials": PRIOR_TRIALS,
            "reliability": PRIOR_SUCCESS / PRIOR_TRIALS,
        }
        for aid in ls.CONTRACTS
    }


def observe(ledger: dict, cluster: list[str], after_keys: set[str]) -> dict:
    for aid in cluster:
        adds = ls.CONTRACTS[aid]["adds"]
        ok = all(k in after_keys for k in adds)
        rec = ledger[aid]
        rec["successes"] += 1 if ok else 0
        rec["trials"] += 1
        rec["reliability"] = round(rec["successes"] / rec["trials"], 3)
    return ledger


def avg_reliability(ledger: dict, cluster: list[str]) -> float:
    if not cluster:
        return 0.0
    return round(sum(ledger[a]["reliability"] for a in cluster) / len(cluster), 3)


def band(rel: float) -> str:
    if rel >= 0.75:
        return "high"
    if rel >= RELIABILITY_FLOOR:
        return "medium"
    return "low"
