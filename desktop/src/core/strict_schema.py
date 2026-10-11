"""严格 schema：未知键即失败并点名 JSON 路径（机制借鉴 o8 workspace-manifest.md:104-113）。

「未知键忽略」会让拼写错误静默通过；本模块报出越界键的完整 JSON 路径。
"""
from __future__ import annotations

from typing import Any, Iterable, List


def check(obj: Any, allowed: Iterable[str], path: str = "$") -> List[str]:
    """仅对**对象**判顶层键；嵌套对象递归。"""
    allowed_set = set(allowed)
    issues: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in allowed_set:
                issues.append("未知键：%s.%s（修复指引：登记进词表或改拼写）" % (path, k))
            issues.extend(check(v, allowed_set if isinstance(v, dict) else (), "%s.%s" % (path, k)))
    return issues
