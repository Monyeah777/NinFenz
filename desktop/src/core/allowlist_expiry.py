"""登记条目带有效期（机制借鉴 openmake audit-gate.cjs:31-47）。

NF 的 IMPORT_RESIDUE / SINK_ALLOW / coupling_baseline 是「登记即永久」；
本模块给登记条目加 expires 与使用台账：到期复红、长期未用报 unused（不得虚挂）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from core import iso8601


def expired(entries: List[Dict[str, Any]], as_of: str) -> List[str]:
    """expires < as_of → 到期复红。"""
    cutoff = iso8601.parse_instant(as_of)
    if cutoff is None:
        return ["as_of 不是 ISO-8601 日期/时间：%r（修复指引：用 YYYY-MM-DD 或带时区的 ISO 时间）"
                % (as_of,)]
    out: List[str] = []
    for e in entries:
        raw = e.get("expires")
        if not str(raw or "").strip():
            continue
        exp = iso8601.parse_instant(raw)
        if exp is None:
            out.append("登记 %s 的 expires 非 ISO-8601：%r（修复指引：用 YYYY-MM-DD 或带时区的 "
                       "ISO 时间）" % (e.get("id"), raw))
        elif exp < cutoff:
            out.append("登记 %s 已于 %s 到期（修复指引：处理掉或重新评审续期）" % (e.get("id"), raw))
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
        if str(e.get("expires") or "").strip() and not iso8601.is_iso_instant(e.get("expires")):
            issues.append("登记 %s 的 expires 非 ISO-8601：%r（修复指引：用 YYYY-MM-DD 或带时区的 "
                          "ISO 时间）" % (e.get("id"), e.get("expires")))
    return issues
