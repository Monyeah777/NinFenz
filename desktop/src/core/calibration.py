"""校准度量（元认知监控的**可算半边**）：置信度分箱 → 每箱的样本数与命中率 → ECE。

为什么（第 44 轮，对应 paper-screening 台账 #1/#2 的「监控 × 控制」与「解耦度量」）：
元认知包里的「校准」此前只在 plan 里被引用（锚点指向 control.py 的 ritual/calibrat 字样），
没有真的可算的实现。本模块把「口头置信是否可信」变成**只计数、不评分**的判据面：

- `bins`：把 (confidence, correct) 按置信度分箱，给每箱 count / mean_conf / accuracy；
- `ece`：expected calibration error（分箱加权 |acc - conf| 的期望）——**不是质量分**，
  是「置信与命中率的偏离程度」，越小越可信；
- `reliability`：给出完整可靠性表（供报告直接引用），不做任何综合评级。

纪律：输入必须是同长度的 confidence∈[0,1] 与 correct∈{0,1}；不一致即 fail-closed 报错，
不做「自动对齐/丢弃坏样本」这类静默修补。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

GUIDE = "修复指引："
SCHEMA = "nf-calibration/1"


def _check(confidences: Sequence[float], correct: Sequence[float]) -> None:
    if len(confidences) != len(correct):
        raise ValueError("置信度与命中标签长度不一致（" + str(len(confidences)) + " vs "
                         + str(len(correct)) + "）（" + GUIDE + "逐样本对齐后再传）")
    if not confidences:
        raise ValueError("样本为空（" + GUIDE + "至少给一条 (confidence, correct)）")
    for i, (c, ok) in enumerate(zip(confidences, correct, strict=True)):
        if not 0.0 <= float(c) <= 1.0:
            raise ValueError("第 " + str(i) + " 条置信度越界：" + str(c)
                             + "（" + GUIDE + "置信度必须在 [0,1]）")
        if float(ok) not in (0.0, 1.0):
            raise ValueError("第 " + str(i) + " 条命中标签不是 0/1：" + str(ok)
                             + "（" + GUIDE + "correct 只能是 0 或 1）")


def bins(confidences: Sequence[float], correct: Sequence[float],
         n_bins: int = 10) -> list[dict[str, Any]]:
    """置信度分箱 → 每箱 {lo, hi, count, mean_conf, accuracy}（空箱 count=0）。"""
    _check(confidences, correct)
    if not 1 <= int(n_bins) <= 100:
        raise ValueError("n_bins 越界：" + str(n_bins) + "（" + GUIDE + "取 1..100）")
    n_bins = int(n_bins)
    rows = []
    for k in range(n_bins):
        lo, hi = k / n_bins, (k + 1) / n_bins
        idx = [i for i, c in enumerate(confidences)
               if lo <= float(c) < hi or (k == n_bins - 1 and float(c) == 1.0)]
        if not idx:
            rows.append({"lo": round(lo, 4), "hi": round(hi, 4), "count": 0,
                         "mean_conf": None, "accuracy": None})
            continue
        mean_conf = sum(float(confidences[i]) for i in idx) / len(idx)
        acc = sum(float(correct[i]) for i in idx) / len(idx)
        rows.append({"lo": round(lo, 4), "hi": round(hi, 4), "count": len(idx),
                     "mean_conf": round(mean_conf, 6), "accuracy": round(acc, 6)})
    return rows


def ece(confidences: Sequence[float], correct: Sequence[float],
        n_bins: int = 10) -> float:
    """expected calibration error：Σ (count/N) · |accuracy − mean_conf|（0 = 完全校准）。"""
    rows = bins(confidences, correct, n_bins)
    total = sum(r["count"] for r in rows)
    acc = 0.0
    for row in rows:
        if not row["count"]:
            continue
        acc += (row["count"] / total) * abs(row["accuracy"] - row["mean_conf"])
    return round(acc, 6)


def reliability(confidences: Sequence[float], correct: Sequence[float],
                n_bins: int = 10) -> dict[str, Any]:
    """完整可靠性表（供报告引用）：**只给计数与偏离，不给综合评级**。"""
    rows = bins(confidences, correct, n_bins)
    return {"schema": SCHEMA, "n": len(confidences), "n_bins": int(n_bins),
            "bins": rows, "ece": ece(confidences, correct, n_bins),
            "note": "ECE 是偏离度不是质量分；报告里必须与分箱表一起给，不能只报一个数"}
