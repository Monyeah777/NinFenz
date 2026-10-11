"""规格主张的认识论标签（机制借鉴 restless-core 规格条目认知标签）。

NF 有 conformance L0-L3（协议一致性），但没有「这条主张有多强」这一维：
Core contract / Product hypothesis / Default pattern / Example。标 Core contract 者
必须指向**真实件或 check**，否则是空口号。
"""
from __future__ import annotations

from typing import Any, Dict, List

LABELS = ("core-contract", "product-hypothesis", "default-pattern", "example")


def validate(claims: List[Dict[str, Any]]) -> List[str]:
    """claims: {id, label, evidence?}。"""
    issues: List[str] = []
    for c in claims:
        cid = str(c.get("id"))
        label = c.get("label")
        if label not in LABELS:
            issues.append("主张 %s 标签越词表：%r（修复指引：取 %s）" % (cid, label, "/".join(LABELS)))
            continue
        if label == "core-contract" and not str(c.get("evidence") or "").strip():
            issues.append("主张 %s 标为 core-contract 却无实现件/check（修复指引：指向真实件或 checkN，或降档）" % cid)
    return issues
