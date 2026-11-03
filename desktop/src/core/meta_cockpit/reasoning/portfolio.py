"""M5 多后端 successive halving：在有限节点预算里把几种搜索策略放在一起竞速。

公开契约 ``nf-search-portfolio/1``::

    run(state, total_nodes=200, backends=("greedy","best_first","puct"), rounds=3)

- **预留式预算**（避免第一轮吃光预算）：第 r 轮先算剩余预算
  ``remaining = total_nodes - allocated``，存活后端各分
  ``slice = max(8, remaining // (len(alive) * (rounds - r)))``；每轮从
  ``remaining`` 里扣**实际分配额**，因此 ``sum(分配) ≤ total_nodes``。
- 每轮按 ``(gap_total, coherence_issues, cost, digest)`` 排序，保留前一半（至少 1）。
- 公开结构**不含** ``reward/q/value/score/weights``：排序键全是整数缺口计数、
  整数 cost 与 digest 字符串，没有标量质量分。
- ``totals.allocated`` = 各轮分配额之和（≤ total），``totals.spent`` = 实际创建/
  尝试节点数之和（≤ allocated，按实际消耗记账，避免"轮数×份额"超发）；
  ``totals.nodes`` 是 ``spent`` 的兼容别名。
- winner 取所有轮次里排名最优的一次结果（因此不会劣于任何单次参选结果），
  ``plan`` 是 winner 路径的原子簇序列。
- 同输入两次运行 canonical 字节一致：无 RNG、无墙钟写入、无模型调用。

设计取舍：successive halving 的每一轮都用**该轮份额**作为 ``max_nodes`` 从同一
初始状态重跑（而不是从上一轮状态续跑），因此每轮的 ``gap_total`` 可直接比较；
总节点用实际消耗记账，避免"轮数 × 份额"超过总预算。
"""

from __future__ import annotations

import copy
import json

from . import budget as budget_mod
from . import bridge as nf
from . import search

SCHEMA = "nf-search-portfolio/1"
BACKENDS = ("greedy", "best_first", "puct")
MIN_ROUND_SLICE = 8
MAX_TOTAL_NODES = 4096
MAX_ROUNDS = 6


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("state must contain artifact object")
    if not isinstance(state.get("goal"), str):
        raise ValueError("state must contain goal string")


def _validate_backends(backends) -> list[str]:
    if not isinstance(backends, (list, tuple)) or not backends:
        raise ValueError("backends must be a non-empty sequence")
    ordered: list[str] = []
    for backend in backends:
        if backend not in BACKENDS:
            raise ValueError("unknown backend: {}".format(backend))
        if backend in ordered:
            raise ValueError("backends must be unique")
        ordered.append(backend)
    return ordered


def _validated_total(total_nodes) -> int:
    if not _is_int(total_nodes) or total_nodes < 1:
        raise ValueError("total_nodes must be a positive integer")
    if total_nodes > MAX_TOTAL_NODES:
        raise ValueError("total_nodes is too large")
    return int(total_nodes)


def _validated_rounds(rounds) -> int:
    if not _is_int(rounds) or not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError("rounds must be an integer in [1, {}]".format(MAX_ROUNDS))
    return int(rounds)


def _depth_for(state: dict) -> int:
    """由初始结构缺口数派生深度上限（与 budget.allocate_for 同一策略）。"""

    gaps = len(nf.completion_gaps(state))
    return int(budget_mod.allocate_for(gaps).max_depth)


def _run_backend(backend: str, state: dict, nodes: int, depth: int) -> dict:
    """跑一次后端；返回 ``nf-cognition-search/1`` 报告（greedy 为简易报告）。"""

    budget = budget_mod.Budget(max_nodes=nodes, max_depth=depth)
    if backend == "greedy":
        plane = search.SearchPlane(mode="best_first")
        return plane.greedy(state=copy.deepcopy(state), budget=budget)
    return search.search(state=copy.deepcopy(state), mode=backend, budget=budget)


def _extract(backend: str, report: dict, budget_nodes: int) -> dict:
    """从报告抽确定性度量：全是整数计数 / digest，没有评分。"""

    if backend == "greedy":
        path = report.get("path", []) or []
        final = report.get("final", {}) or {}
        actions = [list(item["cluster"]) for item in path]
        cost = sum(int(item["cost"]) for item in path)
        used = int(report.get("attempts", 0))
        complete = bool(report.get("complete"))
        degraded = False
        digest = nf.digest(
            {
                "path": [item["state_digest"] for item in path],
                "complete": complete,
            }
        )
    else:
        best_path = report.get("best_path", {}) or {}
        path = report.get("path", []) or []
        final = best_path.get("final", {}) or {}
        actions = [list(cluster) for cluster in best_path.get("actions", [])]
        cost = sum(int(item["cost"]) for item in path)
        used = int(report.get("stats", {}).get("nodes_created", 0))
        complete = bool(report.get("complete"))
        degraded = bool(
            report.get("search_stats", {}).get("degraded")
            or report.get("stats", {}).get("degraded")
        )
        digest = report.get("trace_digest") or nf.digest(
            {"final": final.get("state_digest"), "complete": complete}
        )
    # 预算内实际消耗（报告里的计数不应超发，这里再夹一次保证总量守恒）。
    used = min(max(0, used), int(budget_nodes))
    return {
        "backend": backend,
        "gap_total": len(final.get("completion_gaps", [])),
        "coherence_issues": len(final.get("coherence_issues", [])),
        "cost": cost,
        "nodes": used,
        "complete": complete,
        "degraded": degraded,
        "actions": actions,
        "digest": digest,
    }


def _rank(item: dict) -> tuple:
    """successive halving 的确定性排序键（全整数 + digest）。"""

    return (
        int(item["gap_total"]),
        int(item["coherence_issues"]),
        int(item["cost"]),
        str(item["digest"]),
    )


def _public_result(item: dict) -> dict:
    """结果行的公开视图：去掉内部 actions，只留计数与 digest。"""

    return {
        "backend": item["backend"],
        "budget_nodes": int(item["budget_nodes"]),
        "nodes": int(item["nodes"]),
        "gap_total": int(item["gap_total"]),
        "coherence_issues": int(item["coherence_issues"]),
        "cost": int(item["cost"]),
        "complete": bool(item["complete"]),
        "degraded": bool(item["degraded"]),
        "digest": str(item["digest"]),
    }


def run(
    state: dict,
    total_nodes: int = 200,
    backends=("greedy", "best_first", "puct"),
    rounds: int = 3,
) -> dict:
    """多后端 successive halving；返回 ``nf-search-portfolio/1``。"""

    _validate_state(state)
    total = _validated_total(total_nodes)
    ordered = _validate_backends(backends)
    rounds = _validated_rounds(rounds)
    depth = _depth_for(state)

    alive = list(ordered)
    allocated = 0
    spent = 0
    results: list[dict] = []
    trace_rounds: list[dict] = []
    for index in range(rounds):
        if not alive:
            break
        remaining = total - allocated
        if remaining < 1:
            break
        # 预留式：剩余预算按"存活后端 × 剩余轮数"分摊，避免第一轮把总预算吃光。
        share = max(MIN_ROUND_SLICE, remaining // (len(alive) * (rounds - index)))
        round_rows: list[dict] = []
        round_allocated = 0
        for backend in alive:
            remaining = total - allocated
            if remaining < 1:
                break
            budget_nodes = min(share, remaining)
            allocated += budget_nodes
            round_allocated += budget_nodes
            report = _run_backend(backend, state, budget_nodes, depth)
            item = _extract(backend, report, budget_nodes)
            item["budget_nodes"] = budget_nodes
            spent += int(item["nodes"])
            results.append(item)
            round_rows.append(item)
        if not round_rows:
            break
        ranked = sorted(round_rows, key=_rank)
        keep = max(1, (len(round_rows) + 1) // 2)  # 前一半（向上取整）
        survivors = [item["backend"] for item in ranked[:keep]]
        alive = survivors
        trace_rounds.append(
            {
                "round": index,
                "share": int(share),
                "allocated": int(round_allocated),
                "results": [_public_result(item) for item in ranked],
                "survivors": list(survivors),
            }
        )

    if not results:  # pragma: no cover - total_nodes ≥ 1 时不会发生
        raise RuntimeError("portfolio produced no results")

    # winner = 所有轮次里排名最优的一次结果；同一 backend 同分时取更早轮次。
    ordered_index = {backend: index for index, backend in enumerate(ordered)}
    winner = min(
        results,
        key=lambda item: (*_rank(item), ordered_index[item["backend"]]),
    )
    backends_run = sorted({item["backend"] for item in results}, key=ordered_index.get)
    totals = {
        "allocated": int(allocated),
        "spent": int(spent),
        "nodes": int(spent),  # 兼容别名：= spent
        "backends": backends_run,
    }
    trace_payload = {
        "schema": SCHEMA,
        "initial_digest": nf.state_digest(state),
        "rounds": trace_rounds,
        "winner": winner["backend"],
        "winner_digest": winner["digest"],
        "plan": [list(cluster) for cluster in winner["actions"]],
        "totals": totals,
    }
    return {
        "schema": SCHEMA,
        "winner": winner["backend"],
        "plan": [list(cluster) for cluster in winner["actions"]],
        "rounds": trace_rounds,
        "totals": totals,
        "trace_digest": nf.digest(trace_payload),
    }


def canonical(report: dict) -> bytes:
    """canonical 字节表示（两次运行逐字节一致断言用）。"""

    return json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
