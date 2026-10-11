"""登记条目带有效期（机制借鉴 openmake audit-gate.cjs:31-47）。

NF 的 IMPORT_RESIDUE / SINK_ALLOW / coupling_baseline 是「登记即永久」；
本模块给登记条目加 expires 与使用台账：到期复红、长期未用报 unused（不得虚挂）。
"""
from __future__ import annotations

from typing import Any, Dict, List


def expired(entries: List[Dict[str, Any]], as_of: str) -> List[str]:
    """expires < as_of → 到期复红。"""
    out: List[str] = []
    for e in entries:
        exp = str(e.get("expires") or "")
        if exp and exp < as_of:
            out.append("登记 %s 已于 %s 到期（修复指引：处理掉或重新评审续期）" % (e.get("id"), exp))
    return out


def unused(entries: List[Dict[str, Any]], used_ids) -> List[str]:
    """已登记但从未被使用 → unused（挂账不得虚挂）。"""
    used = set(used_ids)
    return ["登记 %s 长期未使用（修复指引：删除该登记或补使用证据）" % e.get("id")
            for e in entries if str(e.get("id")) not in used]


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    """每条登记须有 id / reason / expires（无期挂账 = 永久豁免，禁止）。"""
    issues: List[str] = []
    for e in entries:
        for k in ("id", "reason", "expires"):
            if not str(e.get(k) or "").strip():
                issues.append("登记缺 %s：%r（修复指引：补该字段；无期挂账禁止）" % (k, e.get("id")))
    return issues
