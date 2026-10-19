"""数据槽声明 grain / unit / clock（机制借鉴 nuke data-machine.md:71-87,161）。

「一行是什么意思 + 单位」是域中立且低成本的契约字段；缺它时聚合必然歧义。
"""
from __future__ import annotations

from typing import Any, Dict, List

CLOCKS = ("event", "ingest", "none")


def validate(slots: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    for s in slots:
        name = str(s.get("name"))
        for k in ("grain", "unit"):
            if not str(s.get(k) or "").strip():
                issues.append("数据槽 %s 缺 %s（修复指引：补该声明，明确一行是什么意思/单位）" % (name, k))
        if s.get("clock") is not None and s.get("clock") not in CLOCKS:
            issues.append("数据槽 %s clock 越词表：%r（修复指引：取 %s）"
                          % (name, s.get("clock"), "/".join(CLOCKS)))
    return issues
