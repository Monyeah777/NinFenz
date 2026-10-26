"""报告自陈工作树脏与 HEAD（机制借鉴 stashbase evals/README.md:45-50）。

「它说的 commit 不是实际跑的」是评测/审计最廉价也最致命的缺口；
本模块把 head 与 dirty 变成报告必填字段。
"""
from __future__ import annotations

from typing import Any, Dict, List


def describe(head: str, dirty_paths: List[str]) -> Dict[str, Any]:
    return {"head": head, "dirty": bool(dirty_paths), "paths": sorted(dirty_paths)}


def validate(rec: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if not str(rec.get("head") or "").strip():
        issues.append("报告缺 head（修复指引：写明实际运行的 commit）")
    if not isinstance(rec.get("dirty"), bool):
        issues.append("报告缺 dirty 布尔（修复指引：写明工作树是否脏）")
    if rec.get("dirty") and not (rec.get("paths") or []):
        issues.append("dirty=True 却未列脏文件（修复指引：列出未提交改动路径）")
    return issues
