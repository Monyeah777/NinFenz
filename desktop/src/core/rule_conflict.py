"""规则同秩冲突显式报错 + 声明/文件顺序永无语义（机制借鉴 oh-my-pi cascade.ts:1-36）。

NF 的「唯一匹配」已覆盖发布方唯一；本模块补**规则面**：同秩同匹配的两条规则必须
显式报冲突（不得静默择一），且应用顺序由 (rank, id) 决定，与声明顺序无关。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def stable_order(rules: List[Dict[str, Any]]) -> List[str]:
    """确定性序：(rank, id) 升序——声明/文件顺序不入语义。"""
    return [str(r.get("id")) for r in sorted(rules, key=lambda r: (int(r.get("rank") or 0), str(r.get("id"))))]


def conflicts(rules: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """同 rank 且同 match 的两条规则 → 冲突对（显式报，不静默）。"""
    out: List[Tuple[str, str]] = []
    seen: Dict[Tuple[int, str], str] = {}
    for r in rules:
        key = (int(r.get("rank") or 0), str(r.get("match") or ""))
        rid = str(r.get("id"))
        if key in seen and seen[key] != rid:
            out.append((seen[key], rid))
        else:
            seen[key] = rid
    return out
