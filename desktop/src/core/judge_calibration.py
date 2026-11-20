"""LLM-as-judge 校准：judge 与 human 的一致性、分类别可靠度、位置/长度偏差。

本模块补的是「judge 分数有了，但是否可自动用」这一层：只读已记录的
human/judge 标签，离线、纯标准库、无 API 调用。

为什么（内部差距）：`domain_metrics.agreement` 能算整体 Cohen's kappa，
但没有回答「哪个类别可以 auto-grade、哪个类别必须人工」；也没有检查
position/order bias 和 verbosity bias。没有这两层，平均 kappa 会把
一个类别的高分掩盖另一个类别的反相关。

纪律：
- 输入必须显式给出 human/judge 标签；缺字段 fail-closed 报错；
- 分类别结论必须同时满足样本量下限与 kappa 阈值，不能凭少量样本判可靠；
- 位置探针只读 pair 记录，不重跑 judge；没有 pair 记录就报 absent；
- 长度相关只作为偏差信号，不当作质量分。
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from core import domain_metrics as dm

SCHEMA = "nf-judge-calibration/1"
GUIDE = "修复指引："


def _require(rows: Sequence[Mapping[str, str]], fields: Sequence[str]) -> None:
    if not rows:
        raise ValueError("校准样本为空（" + GUIDE + "至少给一条 human/judge 标签）")
    for i, row in enumerate(rows):
        for field in fields:
            if field not in row or str(row[field]).strip() == "":
                raise ValueError("第 " + str(i) + " 条缺字段 " + field
                                 + "（" + GUIDE + "逐条补齐后再算）")


def _wilson(successes: int, n: int, z: float = 1.96) -> dict[str, float]:
    if n == 0:
        return {"low": 0.0, "high": 0.0}
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))) / denom
    return {"low": round(max(0.0, center - margin), 6),
            "high": round(min(1.0, center + margin), 6)}


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return 0.0 if sxx == 0 or syy == 0 else sxy / math.sqrt(sxx * syy)


def _agreement(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    out = dm.agreement([{"a": str(r["human"]), "b": str(r["judge"])} for r in rows])
    # domain_metrics 对「双方都只用一个标签」走 _safe_div 返回 0（退化保护）。
    # 校准语义下这是完美一致，按 Cohen 惯例记 1.0；否则常量标签会被误判不可靠。
    if out["observed_agreement"] == 1.0 and out["expected_agreement"] == 1.0:
        out["cohen_kappa"] = 1.0
    return out


def _position(rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    pairs = [r for r in rows if str(r.get("pick_original", "")).strip()
             and str(r.get("pick_swapped", "")).strip()]
    flips = [r for r in pairs if str(r["pick_original"]) != str(r["pick_swapped"])]
    first = sum(1 for r in flips
                if str(r["pick_original"]) == "a" and str(r["pick_swapped"]) == "b")
    return {"n": len(pairs), "flips": len(flips),
            "flip_rate": round(len(flips) / len(pairs), 6) if pairs else None,
            "first_position_wins": first,
            "note": "没有 pair 记录时为 absent：不把「未测」当「无偏差」"}


def _verbosity(rows: Sequence[Mapping[str, str]], positive_label: str) -> dict[str, Any]:
    lengths = [float(len(str(r.get("output", "")))) for r in rows]
    scores = [1.0 if str(r["judge"]) == positive_label else 0.0 for r in rows]
    passed = [n for n, s in zip(lengths, scores, strict=True) if s == 1.0]
    failed = [n for n, s in zip(lengths, scores, strict=True) if s == 0.0]
    return {"n": len(rows), "correlation": round(_pearson(lengths, scores), 6),
            "mean_len_pass": round(sum(passed) / max(1, len(passed)), 6),
            "mean_len_fail": round(sum(failed) / max(1, len(failed)), 6),
            "note": "相关是偏差信号，不是质量分"}


def calibrate(rows: Sequence[Mapping[str, str]], kappa_threshold: float = 0.6,
              min_category_n: int = 8, positive_label: str = "pass") -> dict[str, Any]:
    """返回整体/分类别 kappa、Wilson CI、偏差探针与可自动评审 verdict。"""
    _require(rows, ("category", "human", "judge"))
    if not 0.0 <= float(kappa_threshold) <= 1.0:
        raise ValueError("kappa_threshold 越界（" + GUIDE + "取 [0,1]）")
    if int(min_category_n) < 1:
        raise ValueError("min_category_n 必须 >=1（" + GUIDE + "给正整数）")

    overall = _agreement(rows)
    n = len(rows)
    correct = sum(1 for r in rows if str(r["human"]) == str(r["judge"]))
    ci = _wilson(correct, n)

    groups: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        groups.setdefault(str(row["category"]), []).append(row)
    categories: list[dict[str, Any]] = []
    for name in sorted(groups):
        grp = groups[name]
        agr = _agreement(grp)
        kappa = float(agr["cohen_kappa"])
        categories.append({
            "category": name,
            "n": len(grp),
            "accuracy": agr["observed_agreement"],
            "kappa": kappa,
            "reliable": len(grp) >= int(min_category_n) and kappa >= float(kappa_threshold),
        })
    categories.sort(key=lambda c: (c["kappa"], c["category"]))

    return {
        "schema": SCHEMA,
        "n": n,
        "accuracy": overall["observed_agreement"],
        "accuracy_ci": ci,
        "kappa": overall["cohen_kappa"],
        "kappa_threshold": float(kappa_threshold),
        "min_category_n": int(min_category_n),
        "categories": categories,
        "reliable": [c["category"] for c in categories if c["reliable"]],
        "not_reliable": [c["category"] for c in categories if not c["reliable"]],
        "position": _position(rows),
        "verbosity": _verbosity(rows, positive_label),
        "disagreements": [{"category": str(r["category"]), "human": str(r["human"]),
                           "judge": str(r["judge"])}
                          for r in rows if str(r["human"]) != str(r["judge"])][:20],
        "note": "结论只对样本集成立；无样本的类别不判可靠，也不判不可靠",
    }
