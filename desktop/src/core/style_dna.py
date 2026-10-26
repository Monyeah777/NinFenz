"""档位 DNA 的「适用面」字段 + 门强制（机制借鉴 duyet/aidr dna/README.md:3-15）。

NF 的 STYLE_DNA 资产键 schema 仅 {dna_id,name,rule}、无适用面、无强制；
本模块要求每条 DNA 声明 applies_to（空 = 不适用任何面 = 应当删除）。
"""
from __future__ import annotations

import fnmatch
from typing import Any, Dict, List


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    """每条须有 dna_id / name / rule / applies_to（非空列表）。"""
    issues: List[str] = []
    for e in entries:
        for k in ("dna_id", "name", "rule"):
            if not str(e.get(k) or "").strip():
                issues.append("DNA 条目缺 %s：%r（修复指引：补该字段）" % (k, e.get("dna_id")))
        if not (e.get("applies_to") or []):
            issues.append("DNA %s 缺适用面 applies_to（修复指引：给出适用路径/通配；不适用任何面则应删条目）"
                          % e.get("dna_id"))
    return issues


def for_path(entries: List[Dict[str, Any]], path: str) -> List[str]:
    """反查：该路径适用哪些 DNA。"""
    out = []
    for e in entries:
        for p in e.get("applies_to") or []:
            if fnmatch.fnmatch(path, str(p)):
                out.append(str(e.get("dna_id")))
                break
    return out
