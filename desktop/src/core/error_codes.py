"""错误码中央登记 + 抛出/呈现分离（借鉴 loomvault/iskills）：码唯一、稳定、每条带 message+fix；
两种词法并存——大写码（NF_*）与 ABI 稳定面 cc.<syscall>.<reason>（见 docs/ccos/abi-v0.md）；
抛出侧只给 code+params，文案由呈现层注入。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

#: 两种词法：大写码（NF_*）与 ABI 码 cc.<syscall>.<reason>（对外稳定面，不得改大写/缩写）
_CODE = re.compile(r"^(?:[A-Z][A-Z0-9_]{2,39}|cc\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)$")


def validate(registry: Dict[str, Any]) -> List[str]:
    """登记册校验：id 唯一且合词法、每条含 message 与 fix。"""
    issues: List[str] = []
    seen = set()
    for e in registry.get("codes") or []:
        cid = str(e.get("id") or "")
        if not _CODE.match(cid):
            issues.append("错误码 %r 不合词法（修复指引：大写码 "
                          "^[A-Z][A-Z0-9_]{2,39}$，或 ABI 码 cc.<syscall>.<reason>）" % cid)
        if cid in seen:
            issues.append("错误码重复：%s（修复指引：合并或改号）" % cid)
        seen.add(cid)
        for k in ("message", "fix"):
            if not str(e.get(k) or "").strip():
                issues.append("错误码 %s 缺 %s（修复指引：补该字段）" % (cid, k))
    return issues


def lookup(registry: Dict[str, Any], code: str) -> Tuple[str, str]:
    """→ (message, fix)；未登记码 raise（fail-closed，不得静默放行）。"""
    for e in registry.get("codes") or []:
        if e.get("id") == code:
            return str(e.get("message")), str(e.get("fix"))
    raise ValueError("未登记错误码：%s（修复指引：先在 protocol/error_codes.json 登记）" % code)


def make(code: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """抛出侧只给 code+params；文案由呈现层查表注入。"""
    return {"code": code, "params": dict(params or {})}
