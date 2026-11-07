"""候选健康（candidate-insufficient）：处理「候选都合法、但都烂」这一类盲区。

盲区审计 B 型（覆盖≠判据）的典型：系统只处理「没有候选」，而「有一堆合法但无用的候选」照样往下走。
本模块把五条判据写成确定性函数（B1–B5），任一命中即判 candidate-insufficient：
- B1 无改善：没有任何候选声明它会改变状态（produces 全空）；
- B2 无锚点：没有任何候选带证据锚点（anchors 全空）；
- B3 修复覆盖为零：给了 broken_keys，但没有候选覆盖其中任何一个；
- B4 多样性塌缩：候选签名全相同（等于只有一个候选）；
- B5 全超预算：每个候选 cost 都超过 budget。

纪律：只判「够不够用」，不排序、不打分（排序是下游 planner 的事）。
"""
from __future__ import annotations

from typing import Any

SCHEMA = "nf-candidate-health/1"
VERDICT_OK = "candidate-ok"
VERDICT_INSUFFICIENT = "candidate-insufficient"
GUIDE = "修复指引："


def _signature(candidate: dict[str, Any]) -> str:
    produces = tuple(sorted(str(x) for x in candidate.get("produces") or []))
    repairs = tuple(sorted(str(x) for x in candidate.get("repairs") or []))
    return "|".join(produces) + "##" + "|".join(repairs)


def assess(candidates: Any, budget: int = 0,
           broken_keys: list[str] | None = None) -> dict[str, Any]:
    """评估候选集 → {schema, verdict, reasons[], counts}。"""
    if not isinstance(candidates, list):
        raise ValueError("candidates 必须是数组（" + GUIDE + "传候选列表）")
    if not candidates:
        return {"schema": SCHEMA, "verdict": VERDICT_INSUFFICIENT,
                "reasons": [{"code": "B0", "detail": "候选为空（" + GUIDE + "先产出候选）"}],
                "counts": {"candidates": 0}}
    keys = [str(x) for x in (broken_keys or [])]
    reasons: list[dict[str, Any]] = []

    if all(not (c.get("produces") or []) for c in candidates if isinstance(c, dict)):
        reasons.append({"code": "B1", "detail": "没有任何候选声明会改变状态（produces 全空）"})
    if all(not (c.get("anchors") or []) for c in candidates if isinstance(c, dict)):
        reasons.append({"code": "B2", "detail": "没有任何候选带证据锚点（anchors 全空）"})
    if keys:
        covered: set[str] = set()
        for cand in candidates:
            if isinstance(cand, dict):
                covered.update(str(x) for x in cand.get("repairs") or [])
        if not (covered & set(keys)):
            reasons.append({"code": "B3",
                            "detail": "修复覆盖为零（broken=" + "、".join(keys) + "）"})
    signatures = {_signature(c) for c in candidates if isinstance(c, dict)}
    if len(candidates) > 1 and len(signatures) == 1:
        reasons.append({"code": "B4",
                        "detail": "候选签名全相同（多样性塌缩，等于只有一个候选）"})
    if budget > 0 and all(
            isinstance(c, dict) and int(c.get("cost") or 0) > budget for c in candidates):
        reasons.append({"code": "B5",
                        "detail": "所有候选成本都超过预算 " + str(budget)})

    return {"schema": SCHEMA,
            "verdict": VERDICT_OK if not reasons else VERDICT_INSUFFICIENT,
            "reasons": reasons,
            "counts": {"candidates": len(candidates),
                       "distinct_signatures": len(signatures),
                       "budget": budget, "broken_keys": len(keys)}}
