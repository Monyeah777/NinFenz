"""集合原子：N 方对账（差异明细）/ 子集判定（缺哪些）。只回数据，不判 PASS/FAIL。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def reconcile(groups: Mapping[str, Iterable[str]]) -> dict[str, Any]:
    """N 方集合对账 → {"only_in": {组名: [仅本组有的项]}, "counts": {组名: 项数}}。

    只报「只有本组有」的项，是刻意的定向：门禁里最常见的失败形态正是「某一方多出来一件」，
    而「共同缺项」由调用方拿 required 面与交集比（那是 subset 的活）。两边都报会让同一条
    差异在两个键里各出现一次，修复指引反而更难读。

    顺序稳定：组名按传入顺序，组内项按字典序——差异明细因此可逐字节比对（CAP_DETERMINISTIC）。
    """
    normalized: dict[str, set] = {str(name): set(items) for name, items in groups.items()}
    only_in: dict[str, list[str]] = {}
    for name, items in normalized.items():
        others: set = set()
        for other_name, other_items in normalized.items():
            if other_name != name:
                others |= other_items
        only_in[name] = sorted(items - others)
    return {"only_in": only_in, "counts": {name: len(items) for name, items in normalized.items()}}


def subset(required: Iterable[str], available: Iterable[str]) -> list[str]:
    """required 中**没有**出现在 available 里的项（排序）；空列表 = 子集关系成立。"""
    have = set(available)
    return sorted({item for item in required if item not in have})
