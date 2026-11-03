"""认知状态图搜索平面：默认 AND-OR best-first，可选 PUCT。

公开契约（无标量评分）：

- 节点 = 规范化认知状态；指纹 = 关键字段排序 JSON 的 sha256（与仓内
  ``method_memory.core_signature`` 同一字段集），同 digest 合并即 transposition。
- 动作 = ``live_selector.candidate_families`` 的原子簇（≤3 原子，cost 累加）；
  执行 = ``cognitive_cockpit.execute_cluster`` 的 **deepcopy 影子执行**，
  不调用模型、不写回调用方状态。
- 步级判定 = ``prm.step_verify`` 的 ``nf-step-verdict/1``：只有
  pass/fail/unknown 与整数 gains（unmet/coherence/facet/new_keys），没有
  value/score/weights；coherence 出现新 issue 立即硬剪枝。
- ``mode="best_first"``（默认）——词典序整数键
  ``(unmet+facet, coherence_issues, cost)`` 优先队列；值回传取最优子
  （同键 min），不是均值；transposition 合并保留最小 cost 边。
- ``mode="puct"``——PUCT 选择 + 均值回传，Q 仅作为**内部变量**；
  公开 report 的 path/visits 只含 ``gap_total/cost/visits/discoveries`` 等计数。
- 预算来自 ``budget.Budget``；``complete()`` 早停。预算耗尽但未完成时，
  降级为**同一预算下的完整 greedy 路径**（``termination="search-degraded"``、
  ``degraded=True``），不返回失败。
- 报告只含 digest / 键名 / 计数；确定性输入两次运行逐字节一致（墙钟只参与
  预算判定，不写入报告）。
"""

from __future__ import annotations

import copy
import heapq
import math
import time

from . import budget as budget_mod
from . import bridge as nf
from . import value as prm
from . import steering

SCHEMA = "nf-cognition-search/1"
C_PUCT = 1.4
GAMMA = 0.95
MODES = ("best_first", "puct")
BUDGET_TERMINATIONS = frozenset(
    {"max-nodes", "max-depth", "deadline", "unit-budget", "exhausted"}
)
MAX_PROMPT_CHARS = 20000
MAX_NODES_REQUEST = 4096
MAX_VISITS_REPORTED = 1024
MAX_ITER_FACTOR = 8
MIN_ITERATIONS = 64
STALL_FACTOR = 2


def _state_counts(state: dict) -> dict:
    """整数计数：unmet / facet / coherence / gap_total。"""

    gaps = nf.completion_gaps(state)
    unmet = len(nf.unmet(state))
    coherence = len(nf.coherence_issues(state))
    facet = max(0, len(gaps) - unmet - coherence)
    return {
        "unmet": unmet,
        "facet": facet,
        "coherence": coherence,
        "gap_total": len(gaps),
    }


class _Node:
    __slots__ = (
        "digest",
        "state",
        "depth",
        "reward",
        "prior",
        "parent",
        "parents",
        "action",
        "untried",
        "priors",
        "children",
        "visits",
        "gains",
        "gap_total",
        "unmet",
        "facet",
        "coherence",
        "verdict",
        "checks",
        "cost",
        "version",
        "closed",
        "discoveries",
        "changed_keys",
        "resolved",
    )

    def __init__(self, digest, state, depth, prior, parent, action):
        self.digest = digest
        self.state = state
        self.depth = depth
        self.reward = 0.0  # 仅 PUCT 内部 Q 使用，绝不写入公开 report
        self.prior = prior
        self.parent = parent
        self.parents = [parent.digest] if parent is not None else []
        self.action = list(action) if action else []
        self.untried = None  # None 表示尚未枚举动作
        self.priors = {}
        self.children = []
        self.visits = 0 if parent is None else 1
        self.gains = {"unmet": 0, "coherence": 0, "facet": 0, "new_keys": 0}
        self.gap_total = 0
        self.unmet = 0
        self.facet = 0
        self.coherence = 0
        self.verdict = ""
        self.checks = []
        self.cost = 0
        self.version = 0
        self.closed = False
        self.discoveries = 1
        self.changed_keys = []
        self.resolved = []

    @property
    def key(self) -> tuple[int, int, int]:
        """best_first 的整数词典序键：(unmet+facet, coherence, cost)。"""

        return (self.unmet + self.facet, self.coherence, self.cost)


def _stats_template(backend: str) -> dict:
    return {
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
        "root_visits": 0,
        "root_children": 0,
        "solution_found": False,
        "steering_fallbacks": 0,
        "reparented": 0,
        "backend": backend,
        "degraded": False,
    }


def _fail_report(code: str, message: str, *, budget=None) -> dict:
    """fail-closed 报告：固定文案 + 空结构，不回显任何用户输入。"""

    return {
        "schema": SCHEMA,
        "status": "fail",
        "termination": "invalid-input",
        "complete": False,
        "root_digest": None,
        "goal_digest": None,
        "best_path": {"actions": [], "digests": [], "depth": 0, "final": None},
        "path": [],
        "visits": [],
        "stats": _stats_template("n/a"),
        "search_stats": {"backend": "n/a", "degraded": False, "termination": "invalid-input"},
        "budget": budget.as_dict() if isinstance(budget, budget_mod.Budget) else None,
        "error": {"code": code, "message": message},
        "trace_digest": None,
    }


class SearchPlane:
    """可插拔的认知状态图搜索平面（默认 best_first，可切 PUCT）。"""

    def __init__(
        self,
        *,
        mode: str = "best_first",
        executor=None,
        candidate_provider=None,
        complete_fn=None,
        verifier=None,
        c_puct: float = C_PUCT,
        gamma: float = GAMMA,
        beta: float = steering.DEFAULT_BETA,
        use_steering: bool = True,
    ) -> None:
        if mode not in MODES:
            raise ValueError("mode must be one of {}".format(", ".join(MODES)))
        if not isinstance(c_puct, (int, float)) or isinstance(c_puct, bool) or c_puct <= 0:
            raise ValueError("c_puct must be positive")
        if not isinstance(gamma, (int, float)) or isinstance(gamma, bool) or not 0 < gamma <= 1:
            raise ValueError("gamma must be in (0, 1]")
        self.mode = mode
        self.executor = executor or nf.shadow_execute
        self.candidate_provider = candidate_provider or nf.candidate_actions
        self.complete_fn = complete_fn or nf.complete
        self.verifier = verifier or prm.StepVerifier()
        self.c_puct = float(c_puct)
        self.gamma = float(gamma)
        self.beta = beta
        self.use_steering = bool(use_steering)
        self._reset()

    # ------------------------------------------------------------------ 状态
    def _reset(self) -> None:
        self.ledger = None
        self._steering_warnings: list[str] = []
        self._invalid_actions = 0
        self._steering_fallbacks = 0
        self._steering_summary = {
            "digest": None,
            "prior_source": "uniform",
            "normalization": "none",
            "beta_requested": round(float(self.beta), 6),
            "beta_applied": 0.0,
            "beta_cap": steering.MAX_BETA,
            "clamped": False,
            "disabled": False,
            "warnings": [],
        }

    # ------------------------------------------------------------------ 输入校验
    def _resolve(self, prompt, state, budget):
        if state is not None and prompt is not None:
            return None, None, _fail_report("ambiguous-input", "provide prompt or state, not both")
        if state is None:
            if not isinstance(prompt, str) or not prompt.strip():
                return None, None, _fail_report(
                    "invalid-prompt", "prompt must be a non-empty string"
                )
            if len(prompt) > MAX_PROMPT_CHARS:
                return None, None, _fail_report("invalid-prompt", "prompt is too long")
            if nf.secret_find(prompt):
                return None, None, _fail_report("sensitive-input", "prompt contains sensitive data")
            try:
                state = nf.initial_state(prompt)
            except Exception:  # noqa: BLE001 - 仓内异常不向调用方扩散
                return None, None, _fail_report("invalid-prompt", "cockpit rejected prompt")
        else:
            if not isinstance(state, dict) or not isinstance(state.get("artifact"), dict):
                return None, None, _fail_report(
                    "invalid-state", "state must contain artifact object"
                )
            if not isinstance(state.get("goal"), str):
                return None, None, _fail_report("invalid-state", "state must contain goal string")
            if nf.secret_find(
                {
                    "goal": state.get("goal"),
                    "open_questions": state.get("open_questions", []),
                }
            ):
                return None, None, _fail_report("sensitive-input", "state contains sensitive data")
        if budget is None:
            try:
                budget = budget_mod.allocate_for(len(nf.completion_gaps(state)))
            except Exception:  # noqa: BLE001
                return None, None, _fail_report("invalid-budget", "cannot derive budget from state")
        elif isinstance(budget, dict):
            try:
                budget = budget_mod.Budget(**budget)
            except (TypeError, ValueError):
                return None, None, _fail_report("invalid-budget", "budget fields are invalid")
        elif not isinstance(budget, budget_mod.Budget):
            return None, None, _fail_report("invalid-budget", "budget must be a Budget or object")
        if budget.max_nodes > MAX_NODES_REQUEST:
            return None, None, _fail_report("invalid-budget", "max_nodes is too large")
        beta = self.beta
        if not isinstance(beta, (int, float)) or isinstance(beta, bool) or not math.isfinite(beta):
            return None, None, _fail_report("invalid-beta", "beta must be a finite number")
        if beta < 0:
            return None, None, _fail_report("invalid-beta", "beta must be non-negative")
        return state, budget, None

    # ------------------------------------------------------------------ 动作/先验
    def _actions_for(self, state: dict) -> list[dict]:
        """候选提供者 + 结构化校验 + steering 先验；全部确定性、不调用模型。"""

        try:
            raw = self.candidate_provider(state)
        except Exception:  # noqa: BLE001 - 提供者异常 = 该节点无动作
            self._invalid_actions += 1
            return []
        if not isinstance(raw, (list, tuple)):
            self._invalid_actions += 1
            return []
        contracts = nf.live_selector.CONTRACTS
        known_needs = set(nf.NEEDS)
        checked: list[dict] = []
        seen: set[tuple[str, ...]] = set()
        for item in raw:
            if not isinstance(item, dict):
                self._invalid_actions += 1
                continue
            cluster = item.get("cluster")
            if not isinstance(cluster, (list, tuple)) or not cluster:
                self._invalid_actions += 1
                continue
            cluster = list(cluster)
            if (
                len(cluster) > nf.MAX_ATOMS
                or len(set(cluster)) != len(cluster)
                or any(not isinstance(atom, str) or atom not in contracts for atom in cluster)
            ):
                self._invalid_actions += 1
                continue
            key = tuple(cluster)
            if key in seen:
                continue
            seen.add(key)
            cost = item.get("cost")
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
                self._invalid_actions += 1
                continue
            resolves = item.get("resolves", [])
            if not isinstance(resolves, (list, tuple)) or not set(resolves) <= known_needs:
                resolves = []
            checked.append(
                {
                    "cluster": cluster,
                    "cost": int(cost),
                    "resolves": list(resolves),
                    "prior": 0.0,
                }
            )
        if not checked:
            return []
        if self.use_steering:
            try:
                audit = steering.steer(
                    state,
                    [
                        {
                            "cluster": item["cluster"],
                            "cost": item["cost"],
                            "resolves": item["resolves"],
                        }
                        for item in checked
                    ],
                    beta=self.beta,
                    ledger=self.ledger,
                )
            except ValueError:
                self._steering_fallbacks += 1
                priors = steering.base_prior(checked)
                self._steering_warnings.append("steering-fallback")
            else:
                priors = list(audit["posterior"])
                self._steering_warnings.extend(audit["warnings"])
                self._steering_summary = {
                    "digest": audit["digest"],
                    "prior_source": audit["prior_source"],
                    "normalization": audit["normalization"],
                    "beta_requested": audit["beta_requested"],
                    "beta_applied": audit["beta_applied"],
                    "beta_cap": audit["beta_cap"],
                    "clamped": audit["clamped"],
                    "disabled": audit["disabled"],
                    "warnings": list(audit["warnings"]),
                }
        else:
            priors = steering.base_prior(checked)
        for action, prior in zip(checked, priors):
            action["prior"] = round(float(prior), 9)
        checked.sort(key=lambda action: (-action["prior"], action["cluster"]))
        return checked

    # ------------------------------------------------------------------ 统一输出
    @staticmethod
    def _search_stats(stats: dict, termination: str) -> dict:
        """只留计数与 backend/degraded/termination（公开契约）。"""

        keys = (
            "backend",
            "degraded",
            "iterations",
            "nodes_created",
            "transpositions",
            "coherence_pruned",
            "action_failures",
            "dead_ends",
            "units_spent",
            "max_depth_reached",
        )
        summary = {key: stats.get(key) for key in keys if key in stats}
        summary["termination"] = termination
        return summary

    @staticmethod
    def _path_nodes(node: _Node) -> list[_Node]:
        chain = []
        current = node
        while current is not None and current.parent is not None:
            chain.append(current)
            current = current.parent
        return list(reversed(chain))

    def _path_records(self, path_nodes: list[_Node]) -> list[dict]:
        records = []
        for turn, node in enumerate(path_nodes, start=1):
            head = nf.state_head(node.state)
            records.append(
                {
                    "turn": turn,
                    "cluster": list(node.action),
                    "cost": sum(
                        int(nf.live_selector.CONTRACTS[atom]["cost"]) for atom in node.action
                    ),
                    "gap_total": node.gap_total,
                    "gains": dict(node.gains),
                    "verdict": node.verdict,
                    "checks": [dict(item) for item in node.checks],
                    "changed_keys": list(node.changed_keys),
                    "resolved": list(node.resolved),
                    "state_digest": node.digest,
                    "unmet": head["unmet"],
                    "completion_gaps": head["completion_gaps"],
                    "coherence_issues": head["coherence_issues"],
                }
            )
        return records

    def _build_report(
        self,
        *,
        root: _Node,
        final_node: _Node,
        path_nodes: list[_Node],
        termination: str,
        complete: bool,
        budget,
        visits: list[dict],
        stats: dict,
    ) -> dict:
        stats = dict(stats)
        stats["root_visits"] = root.visits
        stats["root_children"] = len(root.children)
        stats["nodes_created"] = stats.get("nodes_created", 1)
        steering_summary = dict(self._steering_summary)
        steering_summary["warnings"] = sorted(dict.fromkeys(self._steering_warnings))
        stats["steering"] = steering_summary
        trace_payload = {
            "root_digest": root.digest,
            "termination": termination,
            "complete": bool(complete),
            "path_actions": [list(node.action) for node in path_nodes],
            "path_digests": [node.digest for node in path_nodes],
            "final_digest": final_node.digest,
            "visits": visits,
            "stats": {
                key: stats[key]
                for key in (
                    "iterations",
                    "nodes_created",
                    "transpositions",
                    "coherence_pruned",
                    "action_failures",
                    "dead_ends",
                    "invalid_actions",
                    "units_spent",
                    "units_attempted",
                    "max_depth_reached",
                )
            },
        }
        return {
            "schema": SCHEMA,
            "status": "pass",
            "backend": self.mode,
            "mode": self.mode,
            "termination": termination,
            "complete": bool(complete),
            "root_digest": root.digest,
            "goal_digest": nf.digest(root.state.get("goal", "")),
            "best_path": {
                "actions": [list(node.action) for node in path_nodes],
                "digests": [node.digest for node in path_nodes],
                "depth": final_node.depth,
                "final": nf.state_head(final_node.state),
                "source": "search",
            },
            "path": self._path_records(path_nodes),
            "visits": visits,
            "stats": stats,
            "search_stats": self._search_stats(stats, termination),
            "budget": budget.as_dict(),
            "trace_digest": nf.digest(trace_payload),
        }

    # ------------------------------------------------------------------ 动作执行
    @staticmethod
    def _internal_progress(verdict: dict, cost: int) -> float:
        """PUCT 内部 Q 用的有界数值；只存在内存里，不写入公开 report。"""

        gains = verdict.get("gains", {}) if isinstance(verdict, dict) else {}
        raw = (
            2 * int(gains.get("unmet", 0))
            + int(gains.get("coherence", 0))
            + 0.5 * int(gains.get("facet", 0))
            - 0.25 * cost
        )
        return max(-1.0, min(1.0, raw / 12.0))

    @staticmethod
    def _apply_verdict(node: _Node, verdict: dict, result: dict, cost: int) -> None:
        """把 nf-step-verdict/1 投影到节点（只留整数 gains/checks/verdict）。"""

        node.gains = {key: int(value) for key, value in verdict["gains"].items()}
        node.verdict = verdict["verdict"]
        node.checks = [
            {"id": item["id"], "ok": item["ok"]} for item in verdict.get("checks", [])
        ]
        node.reward = SearchPlane._internal_progress(verdict, cost)
        node.changed_keys = list(result.get("changed_keys", []) or [])
        node.resolved = list(result.get("resolved", []) or [])

    def _attempt(self, node: _Node, cluster: list[str]):
        """影子执行 + coherence 硬剪枝 + nf-step-verdict/1 判定。

        返回 ``(child_state, verdict, result, pruned)``；失败位为 None。
        """

        try:
            result = self.executor(node.state, cluster)
        except Exception:  # noqa: BLE001 - 执行器异常 = 该动作非法
            return None, None, None, False
        if (
            not isinstance(result, dict)
            or result.get("status") != "pass"
            or not isinstance(result.get("state"), dict)
        ):
            return None, None, None, False
        child_state = result["state"]
        if nf.coherence_new_issue_ids(node.state, child_state):
            return None, None, result, True
        try:
            verdict = self.verifier.step_verify(
                node.state,
                child_state,
                cluster,
                turn=int(child_state.get("turn", node.state.get("turn", 0))),
                step=node.depth + 1,
            )
        except Exception:  # noqa: BLE001
            return None, None, result, False
        if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
            return None, None, result, False
        return child_state, verdict, result, False

    @staticmethod
    def _make_child(node: _Node, action: dict, child_state: dict, digest: str) -> _Node:
        counts = _state_counts(child_state)
        child = _Node(
            digest, child_state, node.depth + 1, action["prior"], node, action["cluster"]
        )
        child.cost = node.cost + int(action["cost"])
        child.gap_total = counts["gap_total"]
        child.unmet = counts["unmet"]
        child.facet = counts["facet"]
        child.coherence = counts["coherence"]
        return child

    # ------------------------------------------------------------------ PUCT 后端
    def _q(self, node: _Node) -> float:
        return node.reward + self.gamma * self._v(node)

    def _v(self, node: _Node) -> float:
        if not node.children:
            return 0.0
        return math.fsum(self._q(child) for child in node.children) / len(node.children)

    def _select_child(self, node: _Node) -> _Node:
        sqrt_parent = math.sqrt(max(1, node.visits))

        def key(child: _Node) -> tuple:
            exploit = self._q(child)
            explore = self.c_puct * child.prior * sqrt_parent / (1 + child.visits)
            return (exploit + explore, -child.depth, child.digest)

        return max(node.children, key=key)

    def _prepare(self, node: _Node) -> None:
        if node.untried is not None:
            return
        actions = self._actions_for(node.state)
        node.untried = list(actions)
        node.priors = {tuple(action["cluster"]): action["prior"] for action in actions}

    @staticmethod
    def _backup(node: _Node) -> None:
        current = node
        while current is not None:
            current.visits += 1
            current = current.parent

    @staticmethod
    def _expandable(node: _Node, max_depth: int) -> bool:
        return node.depth < max_depth and (node.untried is None or bool(node.untried))

    def _visits_puct(self, graph: dict[str, _Node]) -> list[dict]:
        visits = []
        for node in sorted(graph.values(), key=lambda item: (item.depth, item.digest))[
            :MAX_VISITS_REPORTED
        ]:
            visits.append(
                {
                    "state_digest": node.digest,
                    "depth": node.depth,
                    "visits": node.visits,
                    "gap_total": node.gap_total,
                    "cost": node.cost,
                    "action": list(node.action),
                    "parents": len(node.parents),
                    "discoveries": node.discoveries,
                    "children": len(node.children),
                    "untried": None if node.untried is None else len(node.untried),
                }
            )
        return visits

    def _run_puct(self, start_state: dict, budget) -> dict:
        stats = _stats_template("puct")
        root_digest = nf.state_digest(start_state)
        root_counts = _state_counts(start_state)
        root = _Node(root_digest, start_state, 0, 1.0, None, None)
        root.gap_total = root_counts["gap_total"]
        root.unmet = root_counts["unmet"]
        root.facet = root_counts["facet"]
        root.coherence = root_counts["coherence"]
        graph: dict[str, _Node] = {root_digest: root}
        solution: _Node | None = None
        termination = "exhausted"
        complete = bool(self.complete_fn(start_state))
        if complete:
            termination = "complete"
        started = time.monotonic()
        max_iterations = max(MIN_ITERATIONS, budget.max_nodes * MAX_ITER_FACTOR)
        stall_limit = max(8, budget.max_nodes * STALL_FACTOR)
        stall = 0
        while not complete and stats["iterations"] < max_iterations:
            stats["iterations"] += 1
            decision = budget_mod.should_stop(
                budget=budget,
                complete=False,
                nodes=len(graph),
                depth=stats["max_depth_reached"],
                elapsed=time.monotonic() - started,
                units_spent=stats["units_attempted"],
                check_depth=False,
            )
            if decision["stop"]:
                termination = decision["reason"]
                break
            node = root
            while True:
                self._prepare(node)
                if node.untried and node.depth < budget.max_depth:
                    break
                if not node.children:
                    break
                node = self._select_child(node)
            created = False
            if node.untried and node.depth < budget.max_depth:
                action = node.untried.pop(0)
                cluster = list(action["cluster"])
                cost = int(action["cost"])
                stats["units_attempted"] += cost
                child_state, verdict, result, pruned = self._attempt(node, cluster)
                if child_state is None:
                    if pruned:
                        stats["coherence_pruned"] += 1
                        stats["dead_ends"] += 1
                    else:
                        stats["action_failures"] += 1
                    stall += 1
                    continue
                child_digest = nf.state_digest(child_state)
                if child_digest in graph:
                    stats["transpositions"] += 1
                    existing = graph[child_digest]
                    if node.digest not in existing.parents:
                        existing.parents.append(node.digest)
                    existing.visits += 1
                    existing.discoveries += 1
                    self._backup(node)
                    stall += 1
                    continue
                child = self._make_child(node, action, child_state, child_digest)
                self._apply_verdict(child, verdict, result, cost)
                node.children.append(child)
                graph[child_digest] = child
                stats["units_spent"] += cost
                stats["max_depth_reached"] = max(stats["max_depth_reached"], child.depth)
                created = True
                stall = 0
                self._backup(child)
                if self.complete_fn(child_state):
                    solution = child
                    complete = True
                    termination = "complete"
                    break
            else:
                stats["dead_ends"] += 1
                self._backup(node)
                stall += 1
            if created:
                continue
            if stall >= stall_limit:
                expandable = any(
                    self._expandable(item, budget.max_depth) for item in graph.values()
                )
                if not expandable:
                    if len(graph) == 1:
                        termination = "no-actions"
                    elif stats["max_depth_reached"] >= budget.max_depth:
                        termination = "max-depth"
                    else:
                        termination = "dead-end"
                break
        stats["nodes_created"] = len(graph)
        stats["solution_found"] = solution is not None
        stats["invalid_actions"] = self._invalid_actions
        stats["steering_fallbacks"] = self._steering_fallbacks
        final_node = solution if solution is not None else self._puct_partial(root)
        return self._build_report(
            root=root,
            final_node=final_node,
            path_nodes=self._path_nodes(final_node),
            termination=termination,
            complete=complete,
            budget=budget,
            visits=self._visits_puct(graph),
            stats=stats,
        )

    def _puct_partial(self, root: _Node) -> _Node:
        node = root
        while node.children:
            node = max(
                node.children,
                key=lambda child: (
                    child.visits,
                    self._q(child),
                    child.depth,
                    child.digest,
                ),
            )
        return node

    # ------------------------------------------------------------------ best-first 后端
    @staticmethod
    def _bf_best(node: _Node) -> tuple[int, int, int]:
        """值回传：取最优子（整数键 lexicographic min），不是均值。"""

        if not node.children:
            return node.key
        return min(SearchPlane._bf_best(child) for child in node.children)

    @staticmethod
    def _best_first_partial(graph: dict[str, _Node]) -> _Node:
        return min(graph.values(), key=lambda node: (*node.key, node.digest))

    def _visits_best_first(self, graph: dict[str, _Node]) -> list[dict]:
        visits = []
        for node in sorted(graph.values(), key=lambda item: (item.depth, item.digest))[
            :MAX_VISITS_REPORTED
        ]:
            visits.append(
                {
                    "state_digest": node.digest,
                    "depth": node.depth,
                    "visits": node.visits,
                    "gap_total": node.gap_total,
                    "cost": node.cost,
                    "unmet": node.unmet,
                    "facet": node.facet,
                    "coherence": node.coherence,
                    "action": list(node.action),
                    "parents": len(node.parents),
                    "discoveries": node.discoveries,
                    "children": len(node.children),
                    "closed": node.closed,
                    "backup": list(self._bf_best(node)),
                }
            )
        return visits

    def _run_best_first(self, start_state: dict, budget) -> dict:
        stats = _stats_template("best_first")
        root_digest = nf.state_digest(start_state)
        root_counts = _state_counts(start_state)
        root = _Node(root_digest, start_state, 0, 1.0, None, None)
        root.gap_total = root_counts["gap_total"]
        root.unmet = root_counts["unmet"]
        root.facet = root_counts["facet"]
        root.coherence = root_counts["coherence"]
        graph: dict[str, _Node] = {root_digest: root}
        frontier: list[tuple] = [
            (root.unmet + root.facet, root.coherence, 0, 0, root_digest, root.version)
        ]
        heapq.heapify(frontier)
        solution: _Node | None = None
        termination = "exhausted"
        complete = bool(self.complete_fn(start_state))
        if complete:
            termination = "complete"
        started = time.monotonic()
        max_iterations = max(MIN_ITERATIONS, budget.max_nodes * MAX_ITER_FACTOR)
        while not complete:
            stats["iterations"] += 1
            if stats["iterations"] > max_iterations:
                termination = "exhausted"
                break
            decision = budget_mod.should_stop(
                budget=budget,
                complete=False,
                nodes=len(graph),
                depth=stats["max_depth_reached"],
                elapsed=time.monotonic() - started,
                units_spent=stats["units_attempted"],
                check_depth=False,
            )
            if decision["stop"]:
                termination = decision["reason"]
                break
            if not frontier:
                if len(graph) == 1:
                    termination = "no-actions"
                elif stats["max_depth_reached"] >= budget.max_depth:
                    termination = "max-depth"
                else:
                    termination = "dead-end"
                break
            first, coherence, cost, depth, digest, version = heapq.heappop(frontier)
            node = graph.get(digest)
            if node is None or node.version != version or node.closed:
                continue  # 陈旧条目
            if self.complete_fn(node.state):
                solution = node
                complete = True
                termination = "complete"
                break
            if node.depth >= budget.max_depth:
                node.closed = True
                stats["dead_ends"] += 1
                continue
            # 惰性生成后继：每次只展开一个动作，父节点剩余动作重新入队；
            # 这样 gap 更小的后继能立刻抢占队列，而不是把预算摊在同深度兄弟上。
            if node.untried is None:
                node.untried = self._actions_for(node.state)
            if not node.untried:
                node.closed = True
                stats["dead_ends"] += 1
                continue
            if len(graph) >= budget.max_nodes:
                termination = "max-nodes"
                break
            action = node.untried.pop(0)
            cluster = list(action["cluster"])
            action_cost = int(action["cost"])
            stats["units_attempted"] += action_cost
            child_state, verdict, result, pruned = self._attempt(node, cluster)
            if child_state is None:
                if pruned:
                    stats["coherence_pruned"] += 1
                    stats["dead_ends"] += 1
                else:
                    stats["action_failures"] += 1
                if node.untried and not node.closed:
                    heapq.heappush(
                        frontier, (*node.key, node.depth, node.digest, node.version)
                    )
                else:
                    node.closed = True
                continue
            child_digest = nf.state_digest(child_state)
            child_cost = node.cost + action_cost
            if child_digest in graph:
                # transposition：合并为同一节点，保留 cost 最小的入边
                stats["transpositions"] += 1
                existing = graph[child_digest]
                if node.digest not in existing.parents:
                    existing.parents.append(node.digest)
                existing.visits += 1
                existing.discoveries += 1
                if child_cost < existing.cost:
                    existing.parent = node
                    existing.action = cluster
                    existing.cost = child_cost
                    existing.depth = node.depth + 1
                    existing.version += 1
                    stats["reparented"] += 1
                    if not existing.closed:
                        heapq.heappush(
                            frontier,
                            (*existing.key, existing.depth, existing.digest, existing.version),
                        )
                if node.untried and not node.closed:
                    heapq.heappush(
                        frontier, (*node.key, node.depth, node.digest, node.version)
                    )
                else:
                    node.closed = True
                continue
            child = self._make_child(node, action, child_state, child_digest)
            self._apply_verdict(child, verdict, result, action_cost)
            node.children.append(child)
            graph[child_digest] = child
            stats["units_spent"] += action_cost
            stats["max_depth_reached"] = max(stats["max_depth_reached"], child.depth)
            if node.untried and not node.closed:
                heapq.heappush(
                    frontier, (*node.key, node.depth, node.digest, node.version)
                )
            else:
                node.closed = True
            heapq.heappush(
                frontier, (*child.key, child.depth, child.digest, child.version)
            )
            if self.complete_fn(child_state):
                solution = child
                complete = True
                termination = "complete"
                break
        stats["nodes_created"] = len(graph)
        stats["solution_found"] = solution is not None
        stats["invalid_actions"] = self._invalid_actions
        stats["steering_fallbacks"] = self._steering_fallbacks
        final_node = solution if solution is not None else self._best_first_partial(graph)
        return self._build_report(
            root=root,
            final_node=final_node,
            path_nodes=self._path_nodes(final_node),
            termination=termination,
            complete=complete,
            budget=budget,
            visits=self._visits_best_first(graph),
            stats=stats,
        )

    # ------------------------------------------------------------------ 对外入口
    def search(self, prompt: str | None = None, *, state: dict | None = None, budget=None) -> dict:
        self._reset()
        self.ledger = nf.initial_ledger()
        if hasattr(self.verifier, "cache"):
            self.verifier.cache.clear()  # 单次搜索是事务：内部缓存统计不进入报告
        start_state, budget, failure = self._resolve(prompt, state, budget)
        if failure is not None:
            return failure
        if self.mode == "best_first":
            report = self._run_best_first(copy.deepcopy(start_state), budget)
        else:
            report = self._run_puct(copy.deepcopy(start_state), budget)
        return self._degrade(report, start_state, budget)

    def _degrade(self, report: dict, start_state: dict, budget) -> dict:
        """预算耗尽未完成 → 返回**同一预算下的完整 greedy 路径**，不返回失败。"""

        if report.get("status") != "pass" or report.get("complete"):
            return report
        reason = report.get("termination")
        if reason not in BUDGET_TERMINATIONS:
            return report
        fallback = SearchPlane(
            mode=self.mode,
            executor=self.executor,
            candidate_provider=self.candidate_provider,
            complete_fn=self.complete_fn,
            verifier=self.verifier,
            c_puct=self.c_puct,
            gamma=self.gamma,
            beta=self.beta,
            use_steering=self.use_steering,
        )
        greedy = fallback.greedy(state=copy.deepcopy(start_state), budget=budget)
        stats = dict(report["stats"])
        stats["degraded"] = True
        stats["degraded_from"] = reason
        stats["fallback"] = {
            "termination": greedy["termination"],
            "depth": len(greedy["path"]),
            "completed": bool(greedy["complete"]),
        }
        degraded = dict(report)
        degraded["termination"] = "search-degraded"
        degraded["degraded_from"] = reason
        degraded["complete"] = bool(greedy["complete"])
        degraded["best_path"] = {
            "actions": [list(item["cluster"]) for item in greedy["path"]],
            "digests": [item["state_digest"] for item in greedy["path"]],
            "depth": len(greedy["path"]),
            "final": greedy["final"],
            "source": "greedy-fallback",
        }
        degraded["path"] = greedy["path"]
        degraded["stats"] = stats
        degraded["search_stats"] = self._search_stats(stats, "search-degraded")
        degraded["trace_digest"] = nf.digest(
            {
                "search_trace": report.get("trace_digest"),
                "degraded": True,
                "degraded_from": reason,
                "fallback_termination": greedy["termination"],
                "fallback_path": [item["state_digest"] for item in greedy["path"]],
            }
        )
        return degraded

    @staticmethod
    def _greedy_record(
        before: dict, after: dict, chosen: dict, verdict: dict, result: dict
    ) -> dict:
        head = nf.state_head(after)
        counts = _state_counts(after)
        return {
            "turn": int(after.get("turn", before.get("turn", 0))),
            "cluster": list(chosen["cluster"]),
            "cost": int(chosen["cost"]),
            "gap_total": counts["gap_total"],
            "gains": {key: int(value) for key, value in verdict["gains"].items()},
            "verdict": verdict["verdict"],
            "checks": [
                {"id": item["id"], "ok": item["ok"]} for item in verdict.get("checks", [])
            ],
            "changed_keys": list(result.get("changed_keys", []) or []),
            "resolved": list(result.get("resolved", []) or []),
            "state_digest": nf.state_digest(after),
            "unmet": head["unmet"],
            "completion_gaps": head["completion_gaps"],
            "coherence_issues": head["coherence_issues"],
        }

    def greedy(self, prompt: str | None = None, *, state: dict | None = None, budget=None) -> dict:
        """贪心基线：每步取 steering 先验最高的可执行候选（benchmark 对照）。"""

        self._reset()
        self.ledger = nf.initial_ledger()
        if hasattr(self.verifier, "cache"):
            self.verifier.cache.clear()
        start_state, budget, failure = self._resolve(prompt, state, budget)
        if failure is not None:
            return failure
        state = copy.deepcopy(start_state)
        path: list[dict] = []
        termination = "max-nodes"
        units_spent = 0
        attempts = 0
        limit = min(budget.max_depth, budget.max_nodes)
        for turn in range(1, limit + 1):
            if self.complete_fn(state):
                termination = "complete"
                break
            actions = self._actions_for(state)
            if not actions:
                termination = "no-actions"
                break
            chosen = actions[0]
            attempts += 1
            units_spent += int(chosen["cost"])
            try:
                result = self.executor(state, chosen["cluster"])
            except Exception:  # noqa: BLE001
                termination = "execution-error"
                break
            if (
                not isinstance(result, dict)
                or result.get("status") != "pass"
                or not isinstance(result.get("state"), dict)
            ):
                termination = "execution-error"
                break
            new_state = result["state"]
            if nf.coherence_new_issue_ids(state, new_state):
                termination = "coherence-pruned"
                break
            verdict = self.verifier.step_verify(
                state,
                new_state,
                chosen["cluster"],
                turn=int(new_state.get("turn", state.get("turn", 0))),
                step=turn,
            )
            if not isinstance(verdict, dict) or verdict.get("verdict") != "pass":
                termination = "verdict-error"
                break
            path.append(self._greedy_record(state, new_state, chosen, verdict, result))
            if nf.state_digest(new_state) == nf.state_digest(state):
                state = new_state
                termination = "no-progress"
                break
            state = new_state
            if self.complete_fn(state):
                termination = "complete"
                break
        else:
            termination = "max-depth" if budget.max_depth <= budget.max_nodes else "max-nodes"
        return {
            "schema": SCHEMA,
            "backend": "greedy",
            "strategy": "greedy-prior",
            "status": "pass",
            "termination": termination,
            "complete": bool(self.complete_fn(state)),
            "path": path,
            "depth": len(path),
            "attempts": attempts,
            "units_spent": units_spent,
            "final": nf.state_head(state),
            "budget": budget.as_dict(),
        }


def search(prompt: str | None = None, *, state: dict | None = None, budget=None, **kwargs) -> dict:
    return SearchPlane(**kwargs).search(prompt, state=state, budget=budget)


def greedy(prompt: str | None = None, *, state: dict | None = None, budget=None, **kwargs) -> dict:
    return SearchPlane(**kwargs).greedy(prompt, state=state, budget=budget)
