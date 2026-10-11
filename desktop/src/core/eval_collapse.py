"""评测口径折叠 + 防静默回归（机制借鉴 stashbase evals/README.md:31-36）。

先把语料折叠到文档级再打分（避免长文档吃权重）；并用断言禁止折叠口径回归。
"""
from __future__ import annotations

from typing import Callable, Dict, List


def collapsed_mean(per_doc: Dict[str, List[float]]) -> float:
    """每篇先平均，再对篇平均（不等于全体平均）。"""
    if not per_doc:
        return 0.0
    per = [sum(v) / len(v) for v in per_doc.values() if v]
    return (sum(per) / len(per)) if per else 0.0


def regression_guard(baseline: float, current: float, tolerance: float,
                     collapse: Callable[[Dict[str, List[float]]], float] = collapsed_mean,
                     raw_global: float = 0.0) -> List[str]:
    """折叠口径下降但全体口径未降 → 说明口径被换（静默回归）。"""
    if current + tolerance < baseline and raw_global + tolerance >= baseline:
        return ["折叠口径回归但全体口径未回归（修复指引：核评测折叠规则，勿换口径掩盖）"]
    return []
