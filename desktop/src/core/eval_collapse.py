"""评测口径折叠 + 防静默回归（机制借鉴 stashbase evals/README.md:31-36）。

先把语料折叠到文档级再打分（避免长文档吃权重）；并用断言禁止折叠口径回归。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List


def collapsed_mean(per_doc: Dict[str, List[float]]) -> float:
    """每篇先平均，再对篇平均（不等于全体平均）。"""
    if not per_doc:
        return 0.0
    per: List[float] = []
    for doc, values in per_doc.items():
        if not values:
            # 空文档按 0 计（跳过会把缺失数据从分母里抹掉，导致分数虚高）
            per.append(0.0)
            continue
        try:
            nums = [float(v) for v in values]
        except (TypeError, ValueError) as exc:
            raise ValueError("评测值不可转为数值：%s（%r）" % (doc, values)) from exc
        if any(not math.isfinite(v) for v in nums):
            raise ValueError("评测值含非有限数：%s（%r）" % (doc, values))
        per.append(sum(nums) / len(nums))
    return sum(per) / len(per)


def regression_guard(baseline: float, current: float, tolerance: float,
                     collapse: Callable[[Dict[str, List[float]]], float] = collapsed_mean,
                     raw_global: float = 0.0) -> List[str]:
    """折叠口径下降但全体口径未降 → 说明口径被换（静默回归）。"""
    values = {"baseline": baseline, "current": current,
              "tolerance": tolerance, "raw_global": raw_global}
    bad = [k for k, v in values.items()
           if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v))]
    if bad:
        return ["评测输入含非法数值：%s（修复指引：用有限实数，禁止 NaN/Infinity/布尔）"
                % "、".join(bad)]
    if float(tolerance) < 0:
        return ["tolerance 不得为负：%r（修复指引：容差为非负数）" % (tolerance,)]
    if current + tolerance < baseline and raw_global + tolerance >= baseline:
        return ["折叠口径回归但全体口径未回归（修复指引：核评测折叠规则，勿换口径掩盖）"]
    return []
