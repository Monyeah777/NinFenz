"""ReasoningSession：把 steering / search / memory 收成一个只读、可复算的每回合门面。

设计要点：

- ``begin_turn`` **只读**：不改 ``state`` / ``candidates`` / ``ledger``（候选按副本处理），
  返回重排后的候选与 ``nf-reasoning-turn/1`` trace；
- β > 0 时经 ``steering.steer`` 得 posterior，按 posterior 降序稳定排序；
- ``mode`` 为 ``auto``/``search`` 且初始 ``completion_gaps`` 数 ≥ ``min_gaps`` 时，跑一次
  ``search.search``（节点预算 = session 剩余预算与策略上限的较小值），把计划首簇与候选
  cluster 相同者排到最前；
- ``record_turn`` 用 ``value.step_verify`` 记一次步骤判定，并把上一轮搜索实际消耗的节点
  从 session 搜索预算里扣掉；
- 所有公开输出递归无 ``reward/q/value/score/weights`` 标量，trace 里只有 digest、簇 id、
  布尔与整数计数。
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

from .. import json_asset
from . import bridge as nf
from . import budget as budget_mod
from . import search
from . import steering
from . import trace
from . import value as prm

POLICY_SCHEMA = "nf-reasoning-policy/1"
TURN_SCHEMA = "nf-reasoning-turn/1"
SESSION_SCHEMA = "nf-reasoning-session/1"
RECORD_SCHEMA = "nf-reasoning-record/1"
MODES = ("auto", "search", "off")
SEARCH_BACKENDS = ("best_first", "puct")
MAX_SEARCH_NODES = 4096
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY_PATH = BASE_DIR / "reasoning_policy.json"


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_policy(path=None) -> dict:
    """读取并校验 ``reasoning_policy.json``（可传路径覆盖）。"""

    target = DEFAULT_POLICY_PATH if path is None else Path(path)
    raw = json_asset.load(target, dict, what="reasoning 策略")
    return _validate_policy(raw)


def _merge_policy(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_policy(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _validate_policy(policy) -> dict:
    if not isinstance(policy, dict):
        raise ValueError("推理策略必须是 JSON object（修复指引：检查 reasoning_policy.json）")
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("推理策略 schema 必须是 {}（修复指引：核对 reasoning_policy.schema.json）"
                         .format(POLICY_SCHEMA))
    if not isinstance(policy.get("version"), str) or not policy["version"]:
        raise ValueError("推理策略 version 必须是非空字符串（修复指引：示例 \"1.0.0\"）")
    mode = policy.get("mode")
    if mode not in MODES:
        raise ValueError("推理策略 mode 只允许 {}（修复指引：改用合法值）".format(", ".join(MODES)))
    beta_cap = policy.get("beta_cap")
    if not _is_number(beta_cap) or not 0 < float(beta_cap) <= 1:
        raise ValueError("beta_cap 必须是 (0, 1] 内的数（修复指引：默认 0.5）")
    beta = policy.get("beta")
    if not _is_number(beta) or not 0 <= float(beta) <= float(beta_cap):
        raise ValueError("beta 必须是 [0, beta_cap] 内的数（修复指引：默认 0.0）")
    search_cfg = policy.get("search")
    if not isinstance(search_cfg, dict):
        raise ValueError("policy.search 必须是 object（修复指引：见 reasoning_policy.json）")
    if not _is_int(search_cfg.get("max_nodes")) or not 1 <= search_cfg["max_nodes"] <= MAX_SEARCH_NODES:
        raise ValueError("search.max_nodes 必须是 1..{} 的整数（修复指引：默认 200）"
                         .format(MAX_SEARCH_NODES))
    if search_cfg.get("backend") not in SEARCH_BACKENDS:
        raise ValueError("search.backend 只允许 {}（修复指引：默认 best_first）"
                         .format(", ".join(SEARCH_BACKENDS)))
    if not _is_int(search_cfg.get("min_gaps")) or search_cfg["min_gaps"] < 0:
        raise ValueError("search.min_gaps 必须是非负整数（修复指引：默认 6）")
    for block, keys in (
        ("portfolio", ("enabled",)),
        ("memory", ("enabled", "threshold")),
    ):
        value = policy.get(block)
        if not isinstance(value, dict):
            raise ValueError("policy.{} 必须是 object（修复指引：见 reasoning_policy.json）".format(block))
        if not isinstance(value.get("enabled"), bool):
            raise ValueError("{}.enabled 必须是布尔（修复指引：默认 false）".format(block))
        if block == "memory":
            threshold = value.get("threshold")
            if not _is_number(threshold) or not 0 <= float(threshold) <= 1:
                raise ValueError("memory.threshold 必须在 [0, 1]（修复指引：默认 0.75）")
    return copy.deepcopy(policy)


def _validate_state(state: dict, label: str = "state") -> None:
    if not isinstance(state, dict):
        raise ValueError("{} 必须是 object（修复指引：传 cognitive_cockpit.initial_state 的返回值）"
                         .format(label))
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("{} 必须含 artifact object（修复指引：先跑 initial_state）".format(label))
    if not isinstance(state.get("goal"), str):
        raise ValueError("{} 必须含 goal 字符串（修复指引：先跑 initial_state）".format(label))


def _validate_candidates(candidates) -> list[dict]:
    if not isinstance(candidates, (list, tuple)) or not candidates:
        raise ValueError("candidates 必须是非空 list（修复指引：用 constrained_choice.build_candidates）")
    contracts = nf.live_selector.CONTRACTS
    checked: list[dict] = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError("candidates[{}] 必须是 object（修复指引：见 build_candidates 输出）"
                             .format(index))
        cluster = item.get("cluster")
        if not isinstance(cluster, (list, tuple)) or not cluster:
            raise ValueError("candidates[{}].cluster 必须是非空 list（修复指引：见 build_candidates）"
                             .format(index))
        atoms = list(cluster)
        if len(atoms) > nf.MAX_ATOMS or len(set(atoms)) != len(atoms):
            raise ValueError("candidates[{}].cluster 原子数超限或重复（修复指引：最多 {} 个不同原子）"
                             .format(index, nf.MAX_ATOMS))
        for atom in atoms:
            if not isinstance(atom, str) or atom not in contracts:
                raise ValueError("candidates[{}].cluster 含未知原子（修复指引：核对 atom_contracts.json）"
                                 .format(index))
        checked.append(dict(item))
    return checked


def _validate_cluster(cluster) -> list[str]:
    if not isinstance(cluster, (list, tuple)) or not cluster:
        raise ValueError("cluster 必须是非空 list（修复指引：每步 1-{} 个原子）".format(nf.MAX_ATOMS))
    atoms = list(cluster)
    if len(atoms) > nf.MAX_ATOMS or len(set(atoms)) != len(atoms):
        raise ValueError("cluster 原子数超限或重复（修复指引：最多 {} 个不同原子）".format(nf.MAX_ATOMS))
    for atom in atoms:
        if not isinstance(atom, str) or atom not in nf.live_selector.CONTRACTS:
            raise ValueError("cluster 含未知原子（修复指引：核对 atom_contracts.json）")
    return atoms


class ReasoningSession:
    """只读、确定性的每回合推理门面（steering → search → memory）。"""

    def __init__(
        self,
        *,
        mode: str = "auto",
        search_nodes: int = 200,
        beta: float = 0.0,
        policy=None,
        memory=None,
    ) -> None:
        base = load_policy()
        if policy is None:
            merged = base
        elif isinstance(policy, dict):
            merged = _merge_policy(base, policy)
        else:
            raise ValueError("policy 必须是 dict 或 None（修复指引：见 reasoning_policy.json）")
        self.policy = _validate_policy(merged)
        selected_mode = self.policy["mode"] if mode is None else mode
        if selected_mode not in MODES:
            raise ValueError("mode 只允许 {}（修复指引：默认 auto）".format(", ".join(MODES)))
        self.mode = selected_mode
        if not _is_int(search_nodes) or not 1 <= search_nodes <= MAX_SEARCH_NODES:
            raise ValueError("search_nodes 必须是 1..{} 的整数（修复指引：默认 200）"
                             .format(MAX_SEARCH_NODES))
        self._search_budget = int(search_nodes)
        if not _is_number(beta) or beta < 0:
            raise ValueError("beta 必须是有限非负数（修复指引：默认 0.0）")
        if float(beta) > float(self.policy["beta_cap"]):
            raise ValueError("beta 超出 beta_cap={}（修复指引：改用 ≤ beta_cap 的值）"
                             .format(self.policy["beta_cap"]))
        self.beta = float(beta)
        if memory is not None:
            if not (hasattr(memory, "peek") or hasattr(memory, "steering_features")):
                raise ValueError("memory 需提供 peek/steering_features（修复指引：传 memory.PlanMemory）")
        self._memory = memory
        self._nodes_used = 0
        self._pending_nodes = 0
        self._turns: list[dict] = []
        self._orders: list[list[list[str]]] = []
        self._audits: list = []

    # ------------------------------------------------------------------ 回合
    def begin_turn(self, state: dict, candidates, ledger) -> dict:
        """只读地重排候选；返回 ``{"candidates": [...], "trace": {...}}``。"""

        _validate_state(state)
        items = _validate_candidates(candidates)
        if not isinstance(ledger, dict):
            raise ValueError("ledger 必须是 dict（修复指引：用 calibration_ledger.initial_ledger）")
        gaps = len(nf.completion_gaps(state))

        if self.beta > 0:
            audit = steering.steer(
                state, [copy.deepcopy(item) for item in items], beta=self.beta, ledger=ledger
            )
            posterior = list(audit["posterior"])
            if len(posterior) != len(items):
                raise RuntimeError("steering posterior 长度与候选数不一致"
                                   "（修复指引：核对 steering.steer 契约）")
            order = sorted(range(len(items)), key=lambda index: (-posterior[index], index))
            beta_applied = float(audit["beta_applied"])
            audit_digest = str(audit["digest"])
        else:
            order = list(range(len(items)))
            beta_applied = 0.0
            audit_digest = None
        ordered = [items[index] for index in order]

        plan_head = None
        degraded = False
        search_nodes = 0
        min_gaps = int(self.policy["search"]["min_gaps"])
        if self.mode in ("auto", "search") and gaps >= min_gaps:
            remaining = self._search_budget - self._nodes_used
            if remaining > 0:
                search_nodes = max(1, min(int(self.policy["search"]["max_nodes"]), remaining))
                base_budget = budget_mod.allocate_for(gaps)
                run_budget = budget_mod.Budget(
                    max_nodes=search_nodes, max_depth=int(base_budget.max_depth)
                )
                report = search.search(
                    state=state,
                    budget=run_budget,
                    mode=self.policy["search"]["backend"],
                )
                self._pending_nodes = int(report.get("stats", {}).get("nodes_created", 0))
                actions = report.get("best_path", {}).get("actions", [])
                plan_head = list(actions[0]) if actions else None
                degraded = bool(report.get("search_stats", {}).get("degraded"))
                if plan_head is not None:
                    head = tuple(plan_head)
                    front = [item for item in ordered if tuple(item["cluster"]) == head]
                    rest = [item for item in ordered if tuple(item["cluster"]) != head]
                    ordered = front + rest

        memory_hit = 0
        if self._memory is not None:
            if hasattr(self._memory, "peek"):
                memory_hit = 1 if self._memory.peek(state) else 0
            else:
                memory_hit = int(self._memory.steering_features(state)["memory_hit"])

        turn_trace = {
            "schema": TURN_SCHEMA,
            "mode": self.mode,
            "beta_applied": beta_applied,
            "order": [list(item["cluster"]) for item in ordered],
            "audit_digest": audit_digest,
            "search_nodes": int(search_nodes),
            "plan_head": plan_head,
            "degraded": bool(degraded),
            "memory_hit": int(memory_hit),
            "no_scoring": True,
        }
        self._orders.append([list(item["cluster"]) for item in ordered])
        self._audits.append(audit_digest)
        return {"candidates": copy.deepcopy(ordered), "trace": turn_trace}

    def record_turn(self, *, turn: int, before_state: dict, cluster, after_state: dict, result: dict) -> dict:
        """记录一步：step_verify 判定 + 扣减上一轮搜索实际消耗的节点。"""

        if not _is_int(turn) or turn < 1:
            raise ValueError("turn 必须是 >=1 的整数（修复指引：从 1 开始计回合）")
        _validate_state(before_state, "before_state")
        _validate_state(after_state, "after_state")
        atoms = _validate_cluster(cluster)
        if not isinstance(result, dict):
            raise ValueError("result 必须是 execute_cluster 的 dict（修复指引：见 cognitive_cockpit）")
        verdict = prm.StepVerifier().step_verify(
            before_state, after_state, atoms, turn=int(turn), step=int(turn)
        )
        nodes_deducted = int(self._pending_nodes)
        self._pending_nodes = 0
        self._nodes_used += nodes_deducted
        record = {
            "turn": int(turn),
            "cluster": atoms,
            "verdict": verdict.get("verdict"),
            "verdict_digest": verdict.get("digest"),
            "nodes_deducted": nodes_deducted,
            "no_scoring": True,
        }
        self._turns.append(record)
        return {
            "schema": RECORD_SCHEMA,
            **record,
            "nodes_remaining": max(0, self._search_budget - self._nodes_used),
        }

    # ------------------------------------------------------------------ 汇总
    def summary(self) -> dict:
        """会话汇总（digest-only；无评分键）。"""

        return {
            "schema": SESSION_SCHEMA,
            "mode": self.mode,
            "turns": len(self._turns),
            "search_nodes": int(self._nodes_used),
            "orders_digest": trace.digest(self._orders),
            "audits_digest": trace.digest(self._audits),
            "no_scoring": True,
        }
