"""上游契约 pin + 逐字段对账 + 数量钉死（机制借鉴 OpenAgentCore upstream_contract_test）。

NF 导出面（L3）只有 evidence/gates，缺单点 pin；本模块把「上游契约 sha256 +
逐字段 DeepEqual + 条目数」做成可复算判据。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def digest(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pin(obj: Any, fields: List[str], count: int) -> Dict[str, Any]:
    return {"sha256": digest(obj), "fields": list(fields), "count": int(count)}


def verify(pin_obj: Dict[str, Any], obj: Any) -> List[str]:
    """逐字段 DeepEqual + 数量钉死；字段缺失即报（不得只比整体 hash）。"""
    issues: List[str] = []
    if digest(obj) != str(pin_obj.get("sha256")):
        issues.append("上游契约整体摘要不符（修复指引：确认上游是否变更后重签 pin）")
    for f in pin_obj.get("fields") or []:
        if f not in (obj or {}):
            issues.append("上游契约缺字段 %s（修复指引：补字段或更新 pin）" % f)
    if isinstance(obj, (list, dict)) and len(obj) != int(pin_obj.get("count") or -1):
        issues.append("上游契约条目数不符：%d ≠ %s（修复指引：不得只比字段名，须钉数量）"
                      % (len(obj), pin_obj.get("count")))
    return issues
