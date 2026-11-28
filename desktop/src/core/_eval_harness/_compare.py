"""eval_harness 私有分片：中位数/差值/反窄化指标比较（不给 p 值、不排序、不打分）。"""
from __future__ import annotations

from typing import Any

from ._base import GUIDE

COMPARE_SCHEMA = "nf-eval-compare/1"


def _value_table(runs: list[dict[str, Any]],
                 dims: list[str]) -> dict[str, dict[str, list[float]]]:
    """逐 run 逐 item 收值 → {cond: {dim: [值]}}（非数值丢弃）。"""
    table: dict[str, dict[str, list[float]]] = {}
    for run in runs:
        for item in run.get("items") or []:
            cond = str(item.get("condition"))
            bucket = table.setdefault(cond, {d: [] for d in dims})
            for dim in dims:
                value = item["values"].get(dim)
                if isinstance(value, (int, float)):
                    bucket[dim].append(float(value))
    return table


def _medians(table: dict[str, dict[str, list[float]]], cond_ids: list[str],
             dims: list[str]) -> dict[str, dict[str, float]]:
    """逐 cond×dim 中位数（空桶跳过）。"""
    medians: dict[str, dict[str, float]] = {}
    for cond in cond_ids:
        medians[cond] = {}
        for dim in dims:
            values = sorted(table.get(cond, {}).get(dim, []))
            if not values:
                continue
            mid = len(values) // 2
            medians[cond][dim] = (values[mid] if len(values) % 2
                                  else (values[mid - 1] + values[mid]) / 2)
    return medians


def _diffs(medians: dict[str, dict[str, float]], cond_ids: list[str],
           dims: list[str]) -> dict[str, dict[str, float]]:
    """各非 free 组相对 free 的中位数差（3 位小数）。"""
    baseline = medians.get("free", {})
    return {cond: {dim: round(medians[cond].get(dim, 0.0) - baseline.get(dim, 0.0), 3)
                   for dim in dims if dim in medians.get(cond, {})}
            for cond in cond_ids if cond != "free"}


def compare(protocol: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    """按协议比较：只给计数差与中位数 + 反窄化指标；不给 p 值、不排序、不打分。"""
    if not isinstance(runs, list) or not runs:
        raise ValueError("至少一次 run（" + GUIDE + "先 record_run）")
    sources = {str(r.get("source")) for r in runs}
    if "synthetic" in sources:
        raise ValueError("synthetic run 不能进比较结论（" + GUIDE + "演练数据只验 harness，不当证据）")
    cond_ids = [str(c.get("id")) for c in protocol["conditions"]]
    dims = [str(d.get("id")) for d in protocol["dimensions"]]
    table = _value_table(runs, dims)
    medians = _medians(table, cond_ids, dims)
    diffs = _diffs(medians, cond_ids, dims)
    narrowing = {cond: medians.get(cond, {}).get("table_external_mechanisms")
                 for cond in cond_ids}
    return {"schema": COMPARE_SCHEMA, "protocol_version": str(protocol.get("version")),
            "medians": medians, "diffs_vs_free": diffs,
            "narrowing_index": narrowing,
            "note": "只给计数差与中位数；不给 p 值、不排序、不合成总分",
            "warning": ("table_external_mechanisms 越低越说明被菜单窄化——"
                        "这是唯一专治「越建越窄」的指标")}
