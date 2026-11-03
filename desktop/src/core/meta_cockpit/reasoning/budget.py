"""推理期预算：难度代理 → compute-optimal 式分配 → 早停判据。

本模块只做确定性算术，不读模型、不联网。与 NF 驾驶舱的接口是"难度代理"：
初始 ``completion_gaps`` 的数量（``constrained_loop.completion_gaps``），
这与仓内 "no_scoring" 基调一致——它是**结构缺口计数**，不是质量分。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

SCHEMA = "nf-cognition-budget/1"

#: 参考难度（缺口数）下分配的基准节点数，用于把 unit_budget 缩放回节点量。
UNITS_PER_NODE = 1
MAX_NODES_CAP = 512
MAX_DEPTH_CAP = 12


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def canonical_digest(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Budget:
    """一次推理搜索的硬预算。所有字段 fail-closed 校验。"""

    max_nodes: int = 64
    max_depth: int = 6
    max_seconds: float | None = None
    unit_budget: int | None = None

    def __post_init__(self) -> None:
        if not _is_int(self.max_nodes) or self.max_nodes < 1:
            raise ValueError("max_nodes must be a positive integer")
        if not _is_int(self.max_depth) or self.max_depth < 1:
            raise ValueError("max_depth must be a positive integer")
        if self.max_seconds is not None:
            if not _is_number(self.max_seconds) or not math.isfinite(self.max_seconds):
                raise ValueError("max_seconds must be a finite number")
            if self.max_seconds <= 0:
                raise ValueError("max_seconds must be positive")
        if self.unit_budget is not None:
            if not _is_int(self.unit_budget) or self.unit_budget < 1:
                raise ValueError("unit_budget must be a positive integer")

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "max_nodes": self.max_nodes,
            "max_depth": self.max_depth,
            "max_seconds": self.max_seconds,
            "unit_budget": self.unit_budget,
            "digest": canonical_digest(
                {
                    "max_nodes": self.max_nodes,
                    "max_depth": self.max_depth,
                    "max_seconds": self.max_seconds,
                    "unit_budget": self.unit_budget,
                }
            ),
        }



def difficulty_proxy(gaps: int) -> float:
    """把初始结构缺口数映射为难度代理（≥1）。"""

    if not _is_int(gaps):
        raise ValueError("gaps must be an integer")
    if gaps < 0:
        raise ValueError("gaps must be non-negative")
    return 1.0 + 0.5 * gaps


def compute_optimal_nodes(
    gaps: int,
    *,
    min_nodes: int = 8,
    max_nodes: int = MAX_NODES_CAP,
    base_nodes: int = 30,
    slope: float = 28.0,
    unit_budget: int = 1,
) -> int:
    """compute-optimal 式节点分配：难度（结构缺口数）越高，节点越多。

    形如 ``nodes = clamp((base + slope * gaps) * unit_scale)``，并夹在
    ``[min_nodes, max_nodes]`` 内。思路取自 Snell et al. 2024 的
    "按 prompt 难度分配推理算力"，但这里难度是**可复算的结构缺口**而非
    模型先验概率。
    """

    for name, value in (("min_nodes", min_nodes), ("max_nodes", max_nodes),
                        ("base_nodes", base_nodes), ("unit_budget", unit_budget)):
        if not _is_int(value) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not _is_number(slope) or not math.isfinite(slope) or slope < 0:
        raise ValueError("slope must be a finite non-negative number")
    if min_nodes > max_nodes:
        raise ValueError("min_nodes must not exceed max_nodes")
    proxy = difficulty_proxy(gaps)
    raw = (base_nodes + slope * gaps) * unit_budget / UNITS_PER_NODE
    nodes = int(round(raw))
    return max(min_nodes, min(max_nodes, nodes))


def allocate_for(
    gaps: int,
    *,
    unit_budget: int = 1,
    max_seconds: float | None = None,
    min_nodes: int = 8,
    max_nodes: int = MAX_NODES_CAP,
) -> Budget:
    """由难度代理生成整套预算（节点/深度/时间/单位量）。"""

    nodes = compute_optimal_nodes(
        gaps, min_nodes=min_nodes, max_nodes=max_nodes, unit_budget=unit_budget
    )
    # 缺口越多，允许更深；夹在 [3, MAX_DEPTH_CAP]，不超过剩余缺口量级太多。
    depth = int(max(3, min(MAX_DEPTH_CAP, 3 + (int(gaps) + 1) // 2)))
    # 默认不设墙钟上限：墙钟会让 trace 变成不可复算的输入，调用方需要时显式传。
    seconds = max_seconds
    # 单位预算留足：一次节点展开最多 3 原子，失败重试也算尝试量。
    units = max(2, nodes * 3)
    return Budget(
        max_nodes=nodes, max_depth=depth, max_seconds=seconds, unit_budget=units
    )


def allocate_shares(total_units: int, difficulties: list[int]) -> list[int]:
    """把总节点预算按难度比例分给多个任务（largest-remainder，确定性）。

    ``share_i ∝ 1 + 0.5 * difficulty_i``；每个任务至少 1 个节点。
    返回列表与 ``difficulties`` 等长且和恰为 ``total_units``。
    """

    if not _is_int(total_units) or total_units < 1:
        raise ValueError("total_units must be a positive integer")
    if not isinstance(difficulties, (list, tuple)) or not difficulties:
        raise ValueError("difficulties must be a non-empty list")
    for item in difficulties:
        if not _is_int(item) or item < 0:
            raise ValueError("difficulties must be non-negative integers")
    if total_units < len(difficulties):
        raise ValueError("total_units must be at least the number of tasks")
    weights = [difficulty_proxy(item) for item in difficulties]
    total_weight = math.fsum(weights)
    shares = [1 for _ in difficulties]  # 每个任务至少一个节点
    remainder_pool = total_units - len(difficulties)
    if remainder_pool:
        scaled = [remainder_pool * weight / total_weight for weight in weights]
        base = [int(math.floor(value)) for value in scaled]
        leftover = remainder_pool - sum(base)
        # largest-remainder，平票按任务序号（确定性）
        order = sorted(
            range(len(shares)),
            key=lambda index: (-(scaled[index] - base[index]), index),
        )
        for index in range(len(shares)):
            shares[index] += base[index]
        for index in order[:leftover]:
            shares[index] += 1
    if sum(shares) != total_units:
        raise RuntimeError("allocation invariant violated")
    return shares


def should_stop(
    *,
    budget: Budget,
    complete: bool = False,
    nodes: int = 0,
    depth: int = 0,
    elapsed: float = 0.0,
    units_spent: int = 0,
    best_value: float | None = None,
    value_history: tuple[float, ...] | list[float] = (),
    patience: int = 6,
    epsilon: float = 1e-3,
    check_depth: bool = True,
) -> dict:
    """早停判据（纯函数、可复算）。返回 ``{"stop": bool, "reason": ...}``。

    判定顺序固定：complete → max-nodes → deadline → unit-budget →
    max-depth（可选）→ marginal-value。顺序固定是为了让 trace 可复算。
    """

    if not isinstance(budget, Budget):
        raise ValueError("budget must be a Budget")
    if not _is_int(nodes) or nodes < 0:
        raise ValueError("nodes must be a non-negative integer")
    if not _is_int(depth) or depth < 0:
        raise ValueError("depth must be a non-negative integer")
    if not _is_number(elapsed) or elapsed < 0:
        raise ValueError("elapsed must be a non-negative number")
    if not _is_int(units_spent) or units_spent < 0:
        raise ValueError("units_spent must be a non-negative integer")
    if not _is_int(patience) or patience < 1:
        raise ValueError("patience must be a positive integer")

    reason = None
    if complete:
        reason = "complete"
    elif nodes >= budget.max_nodes:
        reason = "max-nodes"
    elif budget.max_seconds is not None and elapsed >= budget.max_seconds:
        reason = "deadline"
    elif budget.unit_budget is not None and units_spent >= budget.unit_budget:
        reason = "unit-budget"
    elif check_depth and depth >= budget.max_depth:
        reason = "max-depth"
    elif best_value is not None and len(value_history) > patience:
        window = list(value_history)[-patience:]
        if max(window) - min(window) <= epsilon:
            reason = "marginal-value"
    return {
        "schema": SCHEMA,
        "stop": reason is not None,
        "reason": reason,
        "checked": {
            "complete": bool(complete),
            "nodes": nodes,
            "depth": depth,
            "elapsed": elapsed,
            "units_spent": units_spent,
            "patience": patience,
            "epsilon": epsilon,
        },
        "budget": budget.as_dict(),
    }
