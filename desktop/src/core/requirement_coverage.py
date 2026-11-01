"""需求 ↔ 判据双向覆盖台账（机制借鉴 poppyseed spec.ts:114-148 / objectui 覆盖度反向）。

L8 只判「judged_by 可解析」，judgement_coverage 只判「判据须有消费者」；
本模块补**反向**：每条规范条款必须有判据，或**显式登记计划**（否则缺席是静默的）。
"""
from __future__ import annotations

from typing import Any, Dict, List

LEVELS = ("MUST", "SHOULD", "MAY")


def uncovered(requirements: List[Dict[str, Any]], checks: List[Dict[str, Any]]) -> List[str]:
    """无 check 覆盖、又无显式 plan 的 MUST/SHOULD → issue 列表。"""
    covered = set()
    for c in checks:
        for r in (c.get("covers") or []):
            covered.add(str(r))
    issues: List[str] = []
    for r in requirements:
        rid = str(r.get("id"))
        level = r.get("level")
        if level not in LEVELS:
            issues.append("需求 %s level 越词表：%r（修复指引：取 %s）" % (rid, level, "/".join(LEVELS)))
            continue
        if rid in covered:
            continue
        if str(r.get("plan") or "").strip():
            continue          # 显式计划 = 合法缺席（可审计）
        if level in ("MUST", "SHOULD"):
            issues.append("需求 %s（%s）无判据且无计划（修复指引：补 check 的 covers，或登记 plan 说明何时补）"
                          % (rid, level))
    return issues


def orphan_checks(requirements: List[Dict[str, Any]], checks: List[Dict[str, Any]]) -> List[str]:
    """覆盖了不存在需求的 check → 悬空引用。"""
    known = {str(r.get("id")) for r in requirements}
    out: List[str] = []
    for c in checks:
        for r in (c.get("covers") or []):
            if str(r) not in known:
                out.append("check %s 覆盖了不存在的需求 %s（修复指引：改 covers 或登记该需求）"
                           % (c.get("id"), r))
    return out
