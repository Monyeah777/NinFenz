"""已知残余过阻塞登记（机制借鉴 agent-guard deny-bash-patterns.txt:36-41 Known accepted residual）。

与 allowlist_expiry 的区别：那里管「豁免到期」，这里管**已接受的风险残留**
（明知会误伤/漏网但已知并记录），必须带理由与影响面。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    for e in entries:
        for k in ("id", "pattern", "reason", "impact"):
            if not str(e.get(k) or "").strip():
                issues.append("残余登记缺 %s：%r（修复指引：补该字段）" % (k, e.get("id")))
    return issues


def accepted(entries: List[Dict[str, Any]], hit: str) -> List[Dict[str, Any]]:
    """命中已知残余 → 返回命中的登记条目（空 = 非已知残余）。"""
    out = []
    for e in entries:
        try:
            if re.search(str(e.get("pattern")), hit):
                out.append(e)
        except re.error:  # 坏模式按「非已知残余」处理：跳过该条，不连累其余登记
            continue
    return out
