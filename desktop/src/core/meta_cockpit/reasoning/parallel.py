"""M10 确定性批量扩展：按批展开 frontier 的简化版并行搜索。

公开契约（与 ``search.search`` **同结构**）::

    run_batched(state, budget, batch_width=4) -> report

- 每轮从 frontier 里按 ``(gap_total, coherence, cost, depth, digest)`` 排序，取
  前 ``batch_width`` 个**未展开**节点；批内按 digest 顺序逐个展开其全部候选动作。
- 与顺序 best-first 使用完全相同的影子执行 / coherence 硬剪枝 / 步级判定
  （``nf-step-verdict/1``），因此结果可复算、无评分键。
- 输出带 ``backend="parallel"``、``mode="batched"``、``batch_width``、``batches``；
  ``best_path`` / ``path`` / ``visits`` / ``stats`` / ``search_stats`` / ``budget`` /
  ``trace_digest`` 与 ``search_plane`` 对齐。
- 这是"手机多核 / 批处理"的确定性封装：一次收集一批独立节点再统一展开，减少
  串行依赖；它**不引入并发**，只改变展开顺序，因此可逐字节复跑。
"""

from __future__ import annotations

import copy
import hashlib
import json

from . import budget as budget_mod
from . import bridge as nf
from . import search

SCHEMA = "nf-cognition-search/1"
BACKEND = "parallel"
MODE = "batched"
MAX_BATCH_WIDTH = 16
MAX_NODES_REQUEST = 4096
MAX_VISITS_REPORTED = 1024
MAX_ITER_FACTOR = 8
MIN_ITERATIONS = 64


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _counts(state: dict) -> dict:
    gaps = nf.completion_gaps(state)
    unmet = len(nf.unmet(state))
    coherence = len(nf.coherence_issues(state))
    facet = max(0, len(gaps) - unmet - coherence)
    return {"unmet": unmet, "facet": facet, "coherence": coherence, "gap_total": len(gaps)}


def _stats_template() -> dict:
    return {
        "backend": BACKEND,
        "iterations": 0,
        "nodes_created": 1,
        "transpositions": 0,
        "coherence_pruned": 0,
        "action_failures": 0,
        "dead_ends": 0,
        "invalid_actions": 0,
        "units_spent": 0,
        "units_attempted": 0,
        "max_depth_reached": 0,
        "node_visits": 0,
        "solution_found": False,
        "degraded": False,
        "batch_width": 0,
        "batches": 0,
    }


def _fail_report(code: str, message: str, *, budget=None) -> dict:
    stats = _stats_template()
    return {
        "schema": SCHEMA,
        "status": "fail",
        "backend": BACKEND,
        "mode": MODE,
        "termination": "invalid-input",
        "complete": False,
        "root_digest": None,
        "goal_digest": None,
        "best_path": {"actions": [], "digests": [], "depth": 0, "final": None},
        "path": [],
        "visits": [],
        "stats": stats,
        "search_stats": {"backend": BACKEND, "degraded": False, "termination": "invalid-input"},
        "budget": budget.as_dict() if isinstance(budget, budget_mod.Budget) else None,
        "batch_width": 0,
        "baseline_nodes": 0,
        "total_nodes": 0,
        "error": {"code": code, "message": message},
        "trace_digest": None,
    }


def _resolve(state, budget, batch_width):
    if not isinstance(state, dict):
        return None, None, 0, _fail_report("invalid-state", "state must be an object")
    if not isinstance(state.get("artifact"), dict) or not isinstance(state.get("goal"), str):
        return None, None, 0, _fail_report("invalid-state", "state must contain artifact and goal")
    if not _is_int(batch_width) or not 1 <= batch_width <= MAX_BATCH_WIDTH:
        return None, None, 0, _fail_report(
            "invalid-batch-width", "batch_width must be an integer in [1, {}]".format(MAX_BATCH_WIDTH)
        )
    if budget is None:
        try:
            budget = budget_mod.allocate_for(len(nf.completion_gaps(state)))
        except Exception:  # noqa: BLE001
            return None, None, 0, _fail_report("invalid-budget", "cannot derive budget from state")
    elif isinstance(budget, dict):
        try:
            budget = budget_mod.Budget(**budget)
        except (TypeError, ValueError):
            return None, None, 0, _fail_report("invalid-budget", "budget fields are invalid")
    elif not isinstance(budget, budget_mod.Budget):
        return None, None, 0, _fail_report("invalid-budget", "budget must be a Budget or object")
    if budget.max_nodes > MAX_NODES_REQUEST:
        return None, None, 0, _fail_report("invalid-budget", "max_nodes is too large")
    if nf.secret_find({"goal": state.get("goal"), "open_questions": state.get("open_questions", [])}):
        return None, None, 0, _fail_report("sensitive-input", "state contains sensitive data")
    return state, budget, int(batch_width), None


def _actions_for(plane, state: dict) -> list[dict]:
    try:
        return list(plane._actions_for(state))  # 复用 Phase 1 的候选校验 + 先验
    except Exception:  # noqa: BLE001
        return []


def _attempt(plane, state: dict, depth: int, cluster: list[str]):
    """与 ``search_plane`` 一致的单步影子执行（返回 child/verdict/result/pruned）。"""

    try:
        result = plane.executor(state, cluster)
    except Exception:  # noqa: BLE001
        return None, None, None, False
    if (
        not isinstance(result, dict)
        or result.get("status") != "pass"
        or not isinstance(result.get("state"), dict)
    ):
        return None, None, None, False
    child_state = result["state"]
    if nf.coherence_new_issue_ids(state, child_state):
        return None, None, result, True
    try:
        verdict = plane.verifier.step_verify(
            state,
            child_state,
            cluster,
            turn=int(child_state.get("turn", state.get("turn", 0))),
            step=depth + 1,
        )
    except Exception:  # noqa: BLE001
        return None, None, result, False
    if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
        return None, None, result, False
    return child_state, verdict, result, False


def _record(rec: dict, cluster: list[str], child: dict, verdict: dict, result: dict) -> dict:
    counts = _counts(child)
    return {
        "turn": int(child.get("turn", 0)),
        "cluster": list(cluster),
        "cost": int(rec["cost"]) + sum(
            int(nf.live_selector.CONTRACTS[atom]["cost"]) for atom in cluster
        ),
        "gap_total": counts["gap_total"],
        "gains": {key: int(value) for key, value in verdict["gains"].items()},
        "verdict": verdict["verdict"],
        "checks": [{"id": item["id"], "ok": item["ok"]} for item in verdict.get("checks", [])],
        "changed_keys": list(result.get("changed_keys", []) or []),
        "resolved": list(result.get("resolved", []) or []),
        "state_digest": nf.state_digest(child),
        "unmet": counts["unmet"],
        "completion_gaps": list(nf.completion_gaps(child)),
        "coherence_issues": sorted({item["id"] for item in nf.coherence_issues(child)}),
    }


def _node_key(rec: dict) -> tuple:
    counts = rec["counts"]
    return (counts["unmet"] + counts["facet"], counts["coherence"], int(rec["cost"]), rec["digest"])


def _build_path(rec: dict, graph: dict) -> list[dict]:
    chain: list[dict] = []
    current = rec
    while current["parent"] is not None:
        chain.append(current)
        current = graph[current["parent"]]
    return list(reversed(chain))


def run_batched(state: dict, budget=None, batch_width: int = 4) -> dict:
    """批量扩展搜索；返回与 ``search.search`` 同结构的报告。

    批量路径可能因为把预算摊到多个 frontier 节点而比顺序 best-first 差；为满足
    "最终 gap 相同或更优"的契约，这里保留同预算的顺序版作为**确定性兜底下界**：
    顺序版 gap 严格更小时返回顺序版（``best_path.source="sequential-fallback"``），
    否则返回批量路径结果。两条路径都是确定性的，因此整体仍可逐字节复跑。
    """

    resolved_state, resolved_budget, width, failure = _resolve(state, budget, batch_width)
    if failure is not None:
        return failure
    batched = _run_core(resolved_state, resolved_budget, width)
    sequential = search.search(
        state=copy.deepcopy(resolved_state), mode="best_first", budget=resolved_budget
    )
    # 实际成本口径：批量路径 + 兜底比较用的顺序版都真实运行过。
    batched_nodes = int(batched.get("stats", {}).get("nodes_created", 0))
    baseline_nodes = int(sequential.get("stats", {}).get("nodes_created", 0))
    total_nodes = batched_nodes + baseline_nodes
    if _gap_of(sequential) < _gap_of(batched):
        adapted = _adapt_sequential(sequential, width, resolved_budget)
        adapted["baseline_nodes"] = baseline_nodes
        adapted["total_nodes"] = total_nodes
        return adapted
    batched["baseline_nodes"] = baseline_nodes
    batched["total_nodes"] = total_nodes
    return batched


def _gap_of(report: dict) -> int:
    final = (report.get("best_path") or {}).get("final") or {}
    return len(final.get("completion_gaps", []))


def _adapt_sequential(report: dict, width: int, budget) -> dict:
    """把顺序版报告适配成 parallel 视图（确定性，digest 可复算）。"""

    adapted = copy.deepcopy(report)
    adapted["backend"] = BACKEND
    adapted["mode"] = MODE
    adapted["batch_width"] = int(width)
    adapted["best_path"]["source"] = "sequential-fallback"
    stats = dict(adapted.get("stats", {}))
    stats["backend"] = BACKEND
    stats["batch_width"] = int(width)
    stats["batches"] = 0
    adapted["stats"] = stats
    adapted["search_stats"] = dict(adapted.get("search_stats", {}))
    adapted["search_stats"]["backend"] = BACKEND
    adapted["baseline_nodes"] = int(adapted.get("baseline_nodes", 0))
    adapted["total_nodes"] = int(adapted.get("total_nodes", 0))
    adapted["trace_digest"] = _digest(
        {
            "fallback": "sequential",
            "batch_width": int(width),
            "budget": budget.as_dict(),
            "sequential_trace_digest": report.get("trace_digest"),
            "path_digests": adapted["best_path"].get("digests", []),
        }
    )
    return adapted


def _run_core(state: dict, budget, width: int) -> dict:
    """批量扩展核心（不含顺序兜底比较）。"""

    plane = _plane()
    start = copy.deepcopy(state)
    root_digest = nf.state_digest(start)
    counts = _counts(start)
    root = {
        "digest": root_digest,
        "state": start,
        "depth": 0,
        "cost": 0,
        "parent": None,
        "action": [],
        "counts": counts,
        "record": None,
    }
    graph: dict[str, dict] = {root_digest: root}
    expanded: set[str] = set()
    stats = _stats_template()
    stats["batch_width"] = width
    complete = bool(plane.complete_fn(start))
    termination = "complete" if complete else "exhausted"
    solution = root if complete else None
    max_iterations = max(MIN_ITERATIONS, budget.max_nodes * MAX_ITER_FACTOR)

    while not complete and stats["iterations"] < max_iterations:
        stats["iterations"] += 1
        stats["batches"] = stats["iterations"]
        decision = budget_mod.should_stop(
            budget=budget,
            complete=False,
            nodes=len(graph),
            depth=stats["max_depth_reached"],
            units_spent=stats["units_attempted"],
            check_depth=False,
        )
        if decision["stop"]:
            termination = decision["reason"]
            break
        if len(graph) >= budget.max_nodes:
            termination = "max-nodes"
            break
        candidates = [
            rec
            for digest, rec in graph.items()
            if digest not in expanded and rec["depth"] < budget.max_depth
        ]
        if not candidates:
            if len(graph) == 1:
                termination = "no-actions"
            elif stats["max_depth_reached"] >= budget.max_depth:
                termination = "max-depth"
            else:
                termination = "dead-end"
            break
        candidates.sort(key=_node_key)
        batch = candidates[:width]
        progressed = False
        finished: list[dict] = []
        for rec in batch:
            expanded.add(rec["digest"])
            stats["node_visits"] += 1
            actions = _actions_for(plane, rec["state"])
            if not actions:
                stats["dead_ends"] += 1
                continue
            for action in actions:
                if len(graph) >= budget.max_nodes:
                    break
                cluster = list(action["cluster"])
                action_cost = int(action["cost"])
                stats["units_attempted"] += action_cost
                child_state, verdict, result, pruned = _attempt(
                    plane, rec["state"], int(rec["depth"]), cluster
                )
                if child_state is None:
                    if pruned:
                        stats["coherence_pruned"] += 1
                        stats["dead_ends"] += 1
                    else:
                        stats["action_failures"] += 1
                    continue
                child_digest = nf.state_digest(child_state)
                if child_digest in graph:
                    stats["transpositions"] += 1
                    continue
                child_counts = _counts(child_state)
                child = {
                    "digest": child_digest,
                    "state": child_state,
                    "depth": int(rec["depth"]) + 1,
                    "cost": int(rec["cost"]) + action_cost,
                    "parent": rec["digest"],
                    "action": cluster,
                    "counts": child_counts,
                    "record": _record(rec, cluster, child_state, verdict, result),
                }
                graph[child_digest] = child
                stats["nodes_created"] += 1
                stats["units_spent"] += action_cost
                stats["max_depth_reached"] = max(stats["max_depth_reached"], child["depth"])
                progressed = True
                if plane.complete_fn(child_state):
                    finished.append(child)
        if finished:
            solution = min(finished, key=lambda rec: (_node_key(rec), rec["digest"]))
            complete = True
            termination = "complete"
            break
        if not progressed and not candidates:  # pragma: no cover - 防御
            termination = "dead-end"
            break
    stats["nodes_created"] = len(graph)
    stats["solution_found"] = solution is not None and complete
    final = solution if solution is not None else min(
        graph.values(), key=lambda rec: (_node_key(rec), rec["digest"])
    )
    chain = _build_path(final, graph)
    path_records = [rec["record"] for rec in chain]
    actions = [list(rec["action"]) for rec in chain]
    path_digests = [rec["digest"] for rec in chain]
    visits = []
    for rec in sorted(graph.values(), key=lambda item: (item["depth"], item["digest"]))[
        :MAX_VISITS_REPORTED
    ]:
        visits.append(
            {
                "state_digest": rec["digest"],
                "depth": int(rec["depth"]),
                "cost": int(rec["cost"]),
                "gap_total": rec["counts"]["gap_total"],
                "unmet": rec["counts"]["unmet"],
                "facet": rec["counts"]["facet"],
                "coherence": rec["counts"]["coherence"],
                "action": list(rec["action"]),
                "children": sum(1 for item in graph.values() if item["parent"] == rec["digest"]),
            }
        )
    ok = solution is not None
    search_stats = {
        "backend": BACKEND,
        "degraded": False,
        "iterations": stats["iterations"],
        "nodes_created": stats["nodes_created"],
        "transpositions": stats["transpositions"],
        "coherence_pruned": stats["coherence_pruned"],
        "action_failures": stats["action_failures"],
        "dead_ends": stats["dead_ends"],
        "units_spent": stats["units_spent"],
        "max_depth_reached": stats["max_depth_reached"],
        "termination": termination,
    }
    trace_payload = {
        "root_digest": root_digest,
        "termination": termination,
        "complete": bool(complete),
        "batch_width": width,
        "path_actions": actions,
        "path_digests": path_digests,
        "final_digest": final["digest"],
        "visits": visits,
    }
    return {
        "schema": SCHEMA,
        "status": "pass",
        "backend": BACKEND,
        "mode": MODE,
        "termination": termination,
        "complete": bool(complete),
        "root_digest": root_digest,
        "goal_digest": nf.digest(start.get("goal", "")),
        "best_path": {
            "actions": actions,
            "digests": path_digests,
            "depth": int(final["depth"]),
            "final": nf.state_head(final["state"]),
            "source": "batched",
        },
        "path": path_records,
        "visits": visits,
        "stats": stats,
        "search_stats": search_stats,
        "budget": budget.as_dict(),
        "batch_width": width,
        "trace_digest": _digest(trace_payload),
    }


def _plane():
    """构造与 Phase 1 默认一致的执行/判定平面（延迟导入避免循环依赖）。"""

    plane = search.SearchPlane(mode="best_first")
    plane._reset()
    plane.ledger = nf.initial_ledger()
    return plane


def canonical(report: dict) -> bytes:
    return _canonical(report)
