"""装载条目级状态：只有 stale 阻断，其余解释后照发（机制借鉴 stashbase context.ts:1-5,213-299）。

06 §2.4 装载校验现为布尔全过、全阻断——缺一件资产会让整轮不可跑。
本模块把处置分档：stale（内容已变）阻断；missing/outdated 记 warn 但继续。
"""
from __future__ import annotations

from typing import Any, Dict, List

BLOCKING = ("stale",)


def evaluate(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """entries: {id, expected_digest, actual_digest, optional?} → {blocking, warn, ok}。"""
    blocking: List[Dict[str, Any]] = []
    warn: List[Dict[str, Any]] = []
    ok: List[Dict[str, Any]] = []
    for e in entries:
        eid = str(e.get("id"))
        exp, act = e.get("expected_digest"), e.get("actual_digest")
        if exp is not None and act is not None and exp != act:
            item = {"id": eid, "state": "stale", "reason": "内容摘要不符（批准/锚定失效）"}
            blocking.append(item)
        elif not e.get("actual_digest"):
            warn.append({"id": eid, "state": "missing", "reason": "取不到内容；若可选则继续"})
        else:
            ok.append({"id": eid, "state": "ok"})
    return {"blocking": blocking, "warn": warn, "ok": ok}
