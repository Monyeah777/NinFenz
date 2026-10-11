"""用例四字段 why/run/want/avoid（机制借鉴 axiomcodegraph tests/cases/*/case.json）。

把「工具以前给过的错误答案」固化成用例字段：avoid 必填、want 必填，
why 说明为何需要该用例——防用例退化成「只测happy path」。
"""
from __future__ import annotations

from typing import Any, Dict, List

REQUIRED = ("why", "run", "want", "avoid")


def make(why: str, run: str, want: str, avoid: str) -> Dict[str, str]:
    return {"why": why, "run": run, "want": want, "avoid": avoid}


def validate(case: Dict[str, Any]) -> List[str]:
    """四字段齐全且非空；avoid 必须写明**曾出现的错误答案**。"""
    issues: List[str] = []
    for k in REQUIRED:
        if not str(case.get(k) or "").strip():
            issues.append("用例缺 %s（修复指引：补 %s；avoid 写曾出现的错误答案）" % (k, k))
    return issues
