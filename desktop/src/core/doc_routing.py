"""文档「文件 → 何时读」路由索引（机制借鉴 caprock .ai/00-index.md）。

NF 有 AGENT_START/ROUTES，但无「什么情况下读哪件」的表；本模块提供构造/校验/查询。
"""
from __future__ import annotations

from typing import Any, Dict, List


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    """每条须有 file 与 when；file 不得重复。"""
    issues: List[str] = []
    seen = set()
    for e in entries:
        f = str(e.get("file") or "")
        if not f or not str(e.get("when") or "").strip():
            issues.append("路由条目缺 file/when：%r（修复指引：补两字段）" % e)
        if f in seen:
            issues.append("路由条目重复 file：%s（修复指引：合并为一条）" % f)
        seen.add(f)
    return issues


def lookup(entries: List[Dict[str, Any]], keyword: str) -> List[str]:
    """按关键字在 when 里子串匹配 → 文件清单（大小写不敏感）。"""
    k = (keyword or "").strip().lower()
    return [str(e["file"]) for e in entries if k and k in str(e.get("when", "")).lower()]
