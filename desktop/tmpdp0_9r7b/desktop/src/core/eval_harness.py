"""评测标准模板：用例真源 + 显式触发 + 成本/时点标注 + 结果回写（机制借鉴 pj-nx evals / 311 eval.yml）。

NF 有 drill/fixtures/perf_budget，但无统一「评测面」与外部验证记事模板；
本模块给出用例摘要、结果记录与校验（成本与时点必填，禁匿名结果）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

TRIGGERS = ("author-explicit", "ci-scheduled", "local-manual")


def case_digest(cases: Any) -> str:
    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(case_id: str, ok: bool, cost_usd: float, at: str, trigger: str) -> Dict[str, Any]:
    return {"case_id": case_id, "ok": bool(ok), "cost_usd": float(cost_usd),
            "at": at, "trigger": trigger}


def validate(rec: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for k in ("case_id", "ok", "cost_usd", "at", "trigger"):
        if k not in rec:
            issues.append("评测记录缺 %s（修复指引：补该字段）" % k)
    if rec.get("trigger") not in TRIGGERS:
        issues.append("trigger 越词表：%r（修复指引：取 %s；外部验证须 author-explicit）"
                      % (rec.get("trigger"), "/".join(TRIGGERS)))
    if not str(rec.get("at") or "").strip():
        issues.append("评测记录缺时点 at（修复指引：写 ISO 时间）")
    return issues
