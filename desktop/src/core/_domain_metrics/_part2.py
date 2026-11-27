"""core.domain_metrics 私有实现分片 2/2（对外只经 core.domain_metrics 门面导入）： 等"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, List, Sequence

from ._part1 import (
    DIGITS,
    _flag,
    _r,
    agreement,
    calibration,
    classification,
    drift,
    exact_judgement,
    extraction,
    generation,
    latency_cost,
    preference,
    regression,
    retrieval,
)


def contract_compliance(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """契约合规口径：合规率 + 缺字段分布（缺字段数最多的前 5 项，便于定位修复）。"""
    n = len(rows)
    ok = sum(1 for r in rows if _flag(r, "valid") == 1)
    missing: Dict[str, int] = {}
    for r in rows:
        for f in str(r.get("missing_fields", "")).replace("|", ",").replace(";", ",").split(","):
            f = f.strip()
            if f:
                missing[f] = missing.get(f, 0) + 1
    top = sorted(missing.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {"family": "contract_compliance", "n": n, "compliance_rate": _r(ok / n),
            "violations": n - ok,
            "missing_top": [{"field": k, "count": v} for k, v in top]}


FAMILIES: Dict[str, Callable[..., Dict[str, Any]]] = {
    "classification": classification,
    "retrieval": retrieval,
    "extraction": extraction,
    "generation": generation,
    "regression": regression,
    "calibration": calibration,
    "agreement": agreement,
    "preference": preference,
    "exact_judgement": exact_judgement,
    "latency_cost": latency_cost,
    "drift": drift,
    "contract_compliance": contract_compliance,
}


# ------------------------------------------------------------------ 确定性夹具

class _Rng:
    """线性同余（确定性夹具专用）：同种子同序列；不使用 random（避免全局状态）。"""

    def __init__(self, seed: str) -> None:
        self.state = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16)

    def next(self) -> float:
        self.state = (1103515245 * self.state + 12345) % (2 ** 31)
        return self.state / float(2 ** 31)

    def pick(self, items: Sequence[Any]) -> Any:
        return items[int(self.next() * len(items)) % len(items)]

    def between(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.next()


def synthesize(family: str, seed: str, n: int = 0) -> List[Dict[str, str]]:
    """按族生成确定性样例夹具（**合成数据**：口径可复算、可核；不代表真实测量结果）。"""
    r = _Rng("%s|%s" % (family, seed))
    rows: List[Dict[str, str]] = []
    if family == "classification":
        for i in range(n or 24):
            gold = r.pick(["pos", "neg"])
            hit = r.next() < 0.8
            pred = gold if hit else ("neg" if gold == "pos" else "pos")
            rows.append({"case_id": "c%02d" % i, "gold": gold, "pred": pred,
                         "score": "%.4f" % (r.between(0.55, 0.99) if gold == "pos"
                                            else r.between(0.01, 0.45))})
        return rows
    if family == "retrieval":
        for q in range(n or 3):
            rel_idx = {int(r.between(0, 6)), int(r.between(0, 6))}
            for rk in range(6):
                rows.append({"query_id": "q%d" % q, "rank": str(rk + 1),
                             "relevant": "1" if rk in rel_idx else "0"})
        return rows
    if family == "extraction":
        fields = ["品牌", "型号", "价格", "日期", "数量", "单位"]
        for i in range(n or 12):
            gold = sorted({r.pick(fields), r.pick(fields)})
            pred = sorted(set(gold) | ({r.pick(fields)} if r.next() < 0.3 else set()))
            rows.append({"case_id": "e%02d" % i,
                         "gold_fields": json.dumps(gold, ensure_ascii=False),
                         "pred_fields": json.dumps(pred, ensure_ascii=False)})
        return rows
    if family == "generation":
        words = ["模型", "口径", "评测", "样本", "结论", "边界"]
        for i in range(n or 12):
            ref = "".join(r.pick(words) for _ in range(5))
            out = ref if r.next() < 0.4 else "".join(r.pick(words) for _ in range(5))
            rows.append({"case_id": "g%02d" % i, "reference": ref, "output": out})
        return rows
    if family == "regression":
        for i in range(n or 16):
            gold = r.between(-2.0, 2.0)
            rows.append({"case_id": "r%02d" % i, "gold": "%.4f" % gold,
                         "pred": "%.4f" % (gold + r.between(-0.25, 0.25))})
        return rows
    if family == "calibration":
        for i in range(n or 20):
            p = r.between(0.05, 0.95)
            rows.append({"case_id": "k%02d" % i, "prob": "%.4f" % p,
                         "gold": "1" if r.next() < p else "0"})
        return rows
    if family == "agreement":
        for i in range(n or 20):
            a = r.pick(["T", "F"])
            rows.append({"case_id": "a%02d" % i, "a": a,
                         "b": a if r.next() < 0.85 else ("F" if a == "T" else "T")})
        return rows
    if family == "preference":
        for i in range(n or 16):
            human = r.pick(["a", "b"])
            rows.append({"case_id": "p%02d" % i, "human": human,
                         "judge": human if r.next() < 0.7 else r.pick(["a", "b", "tie"])})
        return rows
    if family == "exact_judgement":
        for t in range(n or 4):
            for i in range(4):
                rows.append({"task_id": "t%d" % t, "sample": str(i + 1),
                             "passed": "1" if r.next() < 0.5 else "0"})
        return rows
    if family == "latency_cost":
        for i in range(n or 20):
            rows.append({"case_id": "l%02d" % i,
                         "latency_ms": "%.1f" % r.between(120.0, 900.0),
                         "tokens_in": str(int(r.between(200, 1800))),
                         "tokens_out": str(int(r.between(50, 600)))})
        return rows
    if family == "drift":
        for i in range(n or 8):
            e = r.between(0.05, 0.20)
            rows.append({"bucket": "b%d" % i, "expected": "%.4f" % e,
                         "actual": "%.4f" % max(0.001, e + r.between(-0.03, 0.03))})
        return rows
    if family == "contract_compliance":
        fields = ["available_ts", "unit", "currency", "version", "owner"]
        for i in range(n or 20):
            ok = r.next() < 0.8
            miss = "" if ok else "|".join(sorted({r.pick(fields), r.pick(fields)}))
            rows.append({"case_id": "v%02d" % i, "valid": "1" if ok else "0",
                         "missing_fields": miss})
        return rows
    raise ValueError("未登记夹具族：%r" % family)


def rows_to_csv(rows: Sequence[Dict[str, str]]) -> str:
    """夹具 → CSV（列序 = 首行键序；确定性）。"""
    if not rows:
        return ""
    cols = list(rows[0].keys())
    out = [",".join(cols)]
    for r in rows:
        out.append(",".join('"%s"' % str(r.get(c, "")).replace('"', '""') for c in cols))
    return "\n".join(out) + "\n"


def evaluate(family: str, rows: Sequence[Dict[str, str]], **params) -> Dict[str, Any]:
    fn = FAMILIES.get(family)
    if fn is None:
        raise ValueError("未登记度量族：%r（可选：%s）" % (family, sorted(FAMILIES)))
    body = fn(rows, **params)
    body["digits"] = DIGITS
    body["note"] = ("样例集上的口径值（非模型能力声明）；口径公式见 docs/domain-packs.md；"
                    "本报告由 core/domain_metrics.py 确定性复算（T4）")
    return body
