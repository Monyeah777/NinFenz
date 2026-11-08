"""分组报告（Model Cards / 分组评估的最小可核件）：**先分组，再汇总**。

为什么（第 47 轮，对应筛选台账 #13 与评测设计包 `ev.effect_and_variance`）：
只报一个总体数字会掩盖「某些子群更差」；论文台账的结论是「按条件分组报告」，
但此前本仓没有把这条做成可核的东西。本模块只做三件事：

1. `summarize`：按分组键给每组的 n / 均值 / 样本标准差（**不评分**）；
2. `verify`：检查「分组不足」——某组 n<2 时不能据此谈方差/波动；
3. `render_table`：文本表（给人看），与 `summarize` 同源。

纪律：没有分组维度的「总体均值」不能单独作为结论（`verify` 会报 missing_groups），
这条对应评测设计包常见错法「只报均值不报方差」。
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

GUIDE = "修复指引："
SCHEMA = "nf-grouped-report/1"


def summarize(rows: Sequence[dict[str, Any]], group_key: str,
              metric: str) -> dict[str, Any]:
    """按 group_key 分组 → 每组 {n, mean, sd}（总体也一并给出，但仅作对照）。"""
    if not rows:
        raise ValueError("行为空（" + GUIDE + "至少给一行 {分组键, 指标}）")
    groups: dict[str, list[float]] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or group_key not in row or metric not in row:
            raise ValueError("第 " + str(i) + " 行缺字段（" + GUIDE + "需要 " + group_key
                             + " 与 " + metric + "）")
        try:
            value = float(row[metric])
        except (TypeError, ValueError) as exc:
            raise ValueError("第 " + str(i) + " 行的 " + metric + " 不是数字（" + GUIDE
                             + "别混入字符串/空值）") from exc
        groups.setdefault(str(row[group_key]), []).append(value)
    out = {}
    for name, values in sorted(groups.items()):
        n = len(values)
        mean = sum(values) / n
        sd = (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5 if n > 1 else None
        out[name] = {"n": n, "mean": round(mean, 6),
                     "sd": None if sd is None else round(sd, 6)}
    all_values = [float(row[metric]) for row in rows]
    overall_mean = sum(all_values) / len(all_values)
    return {"schema": SCHEMA, "group_key": group_key, "metric": metric,
            "groups": out,
            "overall": {"n": len(all_values), "mean": round(overall_mean, 6)},
            "note": "overall 只作对照；结论必须按组给（只报总体会掩盖子群差异）"}


def verify(doc: dict[str, Any]) -> list[str]:
    """分组报告体检：分组数、单样本组（不能谈方差）、缺分组。"""
    issues: list[str] = []
    if not isinstance(doc, dict) or str(doc.get("schema")) != SCHEMA:
        return ["报告 schema 不符（" + GUIDE + "需要 " + SCHEMA + "）"]
    groups = doc.get("groups") or {}
    if not groups:
        issues.append("没有分组（" + GUIDE + "只报总体均值不能支撑分组结论）")
    elif len(groups) < 2:
        issues.append("只有 " + str(len(groups)) + " 个分组（" + GUIDE
                      + "至少两个分组才谈得上「按条件对比」）")
    for name, stat in groups.items():
        if int(stat.get("n") or 0) < 2:
            issues.append("分组 " + str(name) + " 只有 " + str(stat.get("n"))
                          + " 个样本（" + GUIDE + "n<2 不能谈方差/波动）")
    return issues


def render_table(doc: dict[str, Any]) -> str:
    """文本表（与 summarize 同源）：组 | n | mean | sd。"""
    lines = ["| 组 | n | mean | sd |", "|---|---|---|---|"]
    for name, stat in (doc.get("groups") or {}).items():
        lines.append("| " + str(name) + " | " + str(stat["n"]) + " | "
                     + str(stat["mean"]) + " | "
                     + ("—" if stat["sd"] is None else str(stat["sd"])) + " |")
    overall = doc.get("overall") or {}
    if overall:
        lines.append("| _(总体，仅对照)_ | " + str(overall.get("n")) + " | "
                     + str(overall.get("mean")) + " | — |")
    return "\n".join(lines) + "\n"
