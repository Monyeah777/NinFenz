"""贡献点须带 since 来源版本（机制借鉴 tianshu builtin-since-hygiene.test.ts）。

NF 全仓 since 零命中；本模块把「自何版本引入」变成可校验字段。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def validate(entries: List[Dict[str, Any]]) -> List[str]:
    issues: List[str] = []
    for e in entries:
        cid = str(e.get("id"))
        since = str(e.get("since") or "")
        if not since:
            issues.append("贡献点 %s 缺 since（修复指引：写明自何版本引入）" % cid)
        elif not _SEMVER.match(since):
            issues.append("贡献点 %s since 非法：%r（修复指引：用 X.Y.Z）" % (cid, since))
    return issues


def covers(entries: List[Dict[str, Any]], version: str) -> List[str]:
    """某版本起可用的贡献点。"""
    def _key(v: str):
        return tuple(int(x) for x in v.split("."))
    return [str(e.get("id")) for e in entries if str(e.get("since") or "0.0.0") and _key(str(e.get("since"))) <= _key(version)]
