"""as-of 取数纪律：评测某时点结论只许用其之前已知的输入（机制借鉴 nuke AGENTS.md:8 / README.md:40-41）。

防前视/泄漏：用了晚于评测时点的输入即判红。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from core import iso8601


def usable_inputs(inputs: List[Dict[str, Any]], as_of: str) -> List[str]:
    """known_at <= as_of 的输入 id。"""
    cutoff = iso8601.parse_instant(as_of)
    if cutoff is None:
        raise ValueError("as_of 不是 ISO-8601 日期/时间：%r（修复指引：用 YYYY-MM-DD 或带时区的 "
                         "ISO 时间）" % (as_of,))
    out: List[str] = []
    for item in inputs:
        known = iso8601.parse_instant(item.get("known_at"))
        if known is not None and known <= cutoff:
            out.append(str(item.get("id")))
    return out


def check(inputs: List[Dict[str, Any]], as_of: str, used_ids: Iterable[str]) -> List[str]:
    """用了 as_of 之后才知道的输入 → 前视泄漏。"""
    cutoff = iso8601.parse_instant(as_of)
    if cutoff is None:
        return ["as_of 不是 ISO-8601 日期/时间：%r（修复指引：用 YYYY-MM-DD 或带时区的 ISO 时间）"
                % (as_of,)]
    late = set()
    invalid: List[str] = []
    for item in inputs:
        known = iso8601.parse_instant(item.get("known_at"))
        if known is None:
            invalid.append(str(item.get("id")))
            continue
        if known > cutoff:
            late.add(str(item.get("id")))
    issues: List[str] = []
    if invalid:
        issues.append("输入 known_at 非 ISO-8601：%s（修复指引：统一为 YYYY-MM-DD 或带时区的 "
                      "ISO 时间；无法解析的输入按不可知处理）" % "、".join(sorted(invalid)))
    issues += ["前视泄漏：评测时点 %s 之前不可知却被使用：%s（修复指引：只用 known_at<=as_of 的输入）"
               % (as_of, x) for x in sorted(set(used_ids) & late)]
    return issues
