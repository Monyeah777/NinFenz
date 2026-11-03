"""M6 跨回合 anytime 预算调度：把一次性的搜索节点预算摊到多个回合。

公开契约（``nf-anytime-session/1``）::

    class AnytimeSession:
        __init__(state, total_nodes=200, turns_left=4)
        advance(nodes) -> {"best_gap": int, "best_plan": [...], "spent": int, "done": bool}
        share_for_turn() -> int        # 剩余节点 / 剩余回合，至少 1
        close_turn(found: bool) -> None  # 结转剩余预算

- **``advance(nodes)``**：``nodes >= 1`` 时推进；``nodes == 0`` **不抛错**，直接返回
  当前 best（不推进、``spent``/remaining 不变、trace 不增长）；负数/非整数仍
  fail-closed 抛 ``ValueError``。每回合至少推进 1 节点是调用方责任（用
  ``share_for_turn()`` 的返回值即 ≥1）。
- ``best_gap`` **单调不增**：会话把每次 ``advance`` 的结果和已记录最优值比较，
  只在 ``(gap_total, cost, digest)`` 更优时替换；永不因单次搜索变差而回退。
- ``done = complete()``：只有已经拿到"缺口全闭合"的计划才为 True；预算耗尽但
  未完成时为 False（由上层用剩余回合/预算决定是否继续）。
- ``close_turn(found)``：``found=True`` 表示本回合已找到完整解，不再消耗回合；
  否则 ``turns_left`` 减一，**未花完的预算自然结转到下一回合**（``share_for_turn``
  用"剩余节点 / 剩余回合"重算）。
- 会话记录 anytime trace（``nodes`` / ``best_gap`` / ``best_cost``），无墙钟、
  无 RNG、无模型调用；同输入两次运行逐字节一致。
"""

from __future__ import annotations

import copy
import json

from . import budget as budget_mod
from . import bridge as nf
from . import search

SCHEMA = "nf-anytime-session/1"
MAX_TOTAL_NODES = 4096
MAX_TURNS = 32
MAX_DEPTH = 12


class _RawSearchPlane(search.SearchPlane):
    """禁用 Phase 1 的"预算耗尽→greedy 兜底"降级。

    Anytime 曲线要观察**搜索本身**随预算增加的推进（gap 下降）；若沿用默认
    降级，小预算也会返回 greedy 完整路径，曲线会永远贴在 gap=0，失去信息量。
    这里只关掉兜底，其余语义（影子执行、hard prune、步级判定）不变。
    """

    def _degrade(self, report: dict, start_state: dict, budget) -> dict:  # noqa: D401
        del start_state, budget
        return report


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("state must contain artifact object")
    if not isinstance(state.get("goal"), str):
        raise ValueError("state must contain goal string")


class AnytimeSession:
    """跨回合 anytime 搜索会话（确定性、无评分）。"""

    def __init__(self, state: dict, total_nodes: int = 200, turns_left: int = 4) -> None:
        _validate_state(state)
        if not _is_int(total_nodes) or not 1 <= total_nodes <= MAX_TOTAL_NODES:
            raise ValueError("total_nodes must be an integer in [1, {}]".format(MAX_TOTAL_NODES))
        if not _is_int(turns_left) or not 1 <= turns_left <= MAX_TURNS:
            raise ValueError("turns_left must be an integer in [1, {}]".format(MAX_TURNS))
        self._initial = copy.deepcopy(state)
        self._initial_digest = nf.state_digest(state)
        self.total_nodes = int(total_nodes)
        self.turns_left = int(turns_left)
        self._depth = int(budget_mod.allocate_for(len(nf.completion_gaps(state))).max_depth)
        self.spent = 0
        self.best_gap = len(nf.completion_gaps(state))
        self.best_cost = 0
        self.best_plan: list[list[str]] = []
        self.best_digest = self._initial_digest
        self._complete = bool(nf.complete(state))
        self._found = False
        self._turn = 0
        self._trace: list[dict] = []

    # ------------------------------------------------------------------ 预算
    def share_for_turn(self) -> int:
        """剩余节点 / 剩余回合，至少 1（剩余为 0 时也返回 1，由 advance 截断）。"""

        turns = max(1, int(self.turns_left))
        remaining = self.total_nodes - self.spent
        return max(1, remaining // turns)

    @property
    def done(self) -> bool:
        """done = complete()：只有缺口全闭合才为 True。"""

        return bool(self._complete or self.best_gap == 0)

    # ------------------------------------------------------------------ 推进
    def advance(self, nodes: int | None = None) -> dict:
        """用至多 ``nodes`` 个节点做一次搜索；返回当前最优计划视图。

        ``nodes == 0`` 是合法的"空推进"：不消耗预算、不推进，直接返回当前
        best（幂等；用于"先看一眼再决定给多少预算"的调度）。
        """

        if nodes is not None:
            if not _is_int(nodes) or nodes < 0:
                raise ValueError("nodes must be a non-negative integer")
            if nodes == 0:
                return self._view()
        if self.done:
            return self._view()
        remaining = self.total_nodes - self.spent
        if remaining < 1:
            return self._view()
        if nodes is None:
            budget_nodes = self.share_for_turn()
        else:
            budget_nodes = int(nodes)
        budget_nodes = min(budget_nodes, remaining)

        budget = budget_mod.Budget(max_nodes=budget_nodes, max_depth=self._depth)
        plane = _RawSearchPlane(mode="best_first")
        report = plane.search(state=copy.deepcopy(self._initial), budget=budget)
        final = report.get("best_path", {}).get("final", {}) or {}
        gap = len(final.get("completion_gaps", []))
        actions = [list(cluster) for cluster in report.get("best_path", {}).get("actions", [])]
        cost = sum(int(item["cost"]) for item in report.get("path", []))
        used = min(int(report.get("stats", {}).get("nodes_created", 0)), budget_nodes)
        self.spent += used
        self._turn += 1
        complete = bool(report.get("complete"))
        candidate_digest = nf.digest(
            {
                "plan": actions,
                "final": final.get("state_digest"),
                "complete": complete,
            }
        )
        better = (
            gap < self.best_gap
            or (
                gap == self.best_gap
                and (cost, len(actions), candidate_digest)
                < (self.best_cost, len(self.best_plan), self.best_digest)
            )
        )
        if better and actions:
            self.best_gap = int(gap)
            self.best_cost = int(cost)
            self.best_plan = [list(cluster) for cluster in actions]
            self.best_digest = candidate_digest
        if complete:
            self._complete = True
        self._trace.append(
            {
                "turn": int(self._turn),
                "nodes": int(budget_nodes),
                "nodes_used": int(used),
                "best_gap": int(self.best_gap),
                "best_cost": int(self.best_cost),
                "plan_steps": len(self.best_plan),
                "complete": bool(self._complete),
            }
        )
        return self._view()

    # ------------------------------------------------------------------ 回合
    def close_turn(self, found: bool) -> None:
        """结束本回合：找到完整解则不再消耗回合；否则回合数减一、预算结转。"""

        if not isinstance(found, bool):
            raise ValueError("found must be a boolean")
        self._found = bool(found)
        if found:
            self._complete = True
        else:
            self.turns_left = max(0, self.turns_left - 1)

    # ------------------------------------------------------------------ 视图
    def _view(self) -> dict:
        return {
            "best_gap": int(self.best_gap),
            "best_plan": [list(cluster) for cluster in self.best_plan],
            "spent": int(self.spent),
            "done": bool(self.done),
        }

    def summary(self) -> dict:
        """anytime trace 的自描述视图（无墙钟，逐字节可复算）。"""

        return {
            "schema": SCHEMA,
            "initial_digest": self._initial_digest,
            "total_nodes": int(self.total_nodes),
            "turns_left": int(self.turns_left),
            "turn": int(self._turn),
            "spent": int(self.spent),
            "best_gap": int(self.best_gap),
            "best_cost": int(self.best_cost),
            "best_plan": [list(cluster) for cluster in self.best_plan],
            "done": bool(self.done),
            "trace": [dict(item) for item in self._trace],
        }


def canonical(report: dict) -> bytes:
    """canonical 字节表示（两次运行逐字节一致断言用）。"""

    return json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
