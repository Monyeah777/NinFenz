"""评测标准模板：用例真源 + 显式触发 + 成本/时点标注 + 结果回写（机制借鉴 pj-nx evals / 311 eval.yml）。

NF 有 drill/fixtures/perf_budget，但无统一「评测面」与外部验证记事模板；
本模块给出用例摘要、结果记录与校验（成本与时点必填，禁匿名结果）。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Dict, List

from core import iso8601

TRIGGERS = ("author-explicit", "ci-scheduled", "local-manual")
_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def case_digest(cases: Any) -> str:
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(case_id: str, ok: bool, cost_usd: float, at: str, trigger: str) -> Dict[str, Any]:
    try:
        cost = float(cost_usd)
    except (TypeError, ValueError) as exc:
        raise ValueError("cost_usd 须为数值：%r" % (cost_usd,)) from exc
    rec = {"case_id": case_id, "ok": bool(ok), "cost_usd": cost,
           "at": at, "trigger": trigger}
    issues = validate(rec)
    if issues:
        raise ValueError("评测记录非法：%s" % "；".join(issues))
    return rec


def validate(rec: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for k in ("case_id", "ok", "cost_usd", "at", "trigger"):
        if k not in rec:
            issues.append("评测记录缺 %s（修复指引：补该字段）" % k)
    if rec.get("trigger") not in TRIGGERS:
        issues.append("trigger 越词表：%r（修复指引：取 %s；外部验证须 author-explicit）"
                      % (rec.get("trigger"), "/".join(TRIGGERS)))
    if not isinstance(rec.get("ok"), bool):
        issues.append("ok 须为布尔：%r（修复指引：用 true/false）" % (rec.get("ok"),))
    case_id = rec.get("case_id")
    if not isinstance(case_id, str) or not _CASE_ID.match(case_id):
        issues.append("case_id 非法：%r（修复指引：字母数字起头，[A-Za-z0-9._:-]，≤128 字符）"
                      % (case_id,))
    cost = rec.get("cost_usd")
    if (isinstance(cost, bool) or not isinstance(cost, (int, float))
            or not math.isfinite(float(cost)) or float(cost) < 0):
        issues.append("cost_usd 须为非负有限数：%r（修复指引：成本用 USD 数值，禁止 NaN/Infinity/负数）"
                      % (cost,))
    if not iso8601.is_iso_instant(rec.get("at")):
        issues.append("时点 at 须为 ISO-8601：%r（修复指引：如 2026-10-11T00:00:00Z 或 "
                      "2026-10-11）" % (rec.get("at"),))
    return issues
