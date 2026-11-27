"""core.domain_metrics 私有实现分片 1/2（对外只经 core.domain_metrics 门面导入）：DIGITS 等"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from core import conformance_scan as csc
from core import json_doc

DIGITS = 6


def _r(x: float) -> float:
    return round(float(x), DIGITS)


def _safe_div(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b


# ------------------------------------------------------------------ 输入装载

def load_rows(path: str | Path) -> Tuple[List[Dict[str, str]], str]:
    p = Path(path)
    try:
        text = csc.read_text_cached(p)      # 共享语料读：同一次只读调用内同件只读一遍
    except OSError as exc:
        return [], "不可读：%s" % exc
    rows = [dict(r) for r in csv.DictReader(text.splitlines())]
    if not rows:
        return [], "空表（%s）" % p.name
    return rows, ""


def _num(row: Dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("列 %s 非数值：%r" % (key, row.get(key))) from exc


def _flag(row: Dict[str, str], key: str) -> int:
    v = str(row.get(key, "")).strip().lower()
    if v in ("1", "true", "yes", "y", "正", "是"):
        return 1
    if v in ("0", "false", "no", "n", "负", "否"):
        return 0
    raise ValueError("列 %s 非 0/1：%r" % (key, row.get(key)))


def _pair_wins(pos: Sequence[float], neg: Sequence[float]) -> float:
    """逐对胜负（并列 0.5）：ROC-AUC 的 Mann-Whitney 分子。"""
    wins = 0.0
    for s in pos:
        for t in neg:
            wins += 1.0 if s > t else (0.5 if s == t else 0.0)
    return wins


def _auc(pairs: Sequence[Tuple[float, int]]) -> float:
    """ROC-AUC（Mann-Whitney 口径，并列取平均秩）。"""
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return 0.0
    return _pair_wins(pos, neg) / (len(pos) * len(neg))


# ------------------------------------------------------------------ 度量族

def _confusion(rows: Sequence[Dict[str, str]],
               labels: List[str]) -> Dict[str, Dict[str, int]]:
    cm = {g: {p: 0 for p in labels} for g in labels}
    for r in rows:
        cm[str(r["gold"])][str(r["pred"])] += 1
    return cm


def _per_label(cm: Dict[str, Dict[str, int]],
               labels: List[str]) -> Dict[str, Dict[str, float]]:
    per: Dict[str, Dict[str, float]] = {}
    for l in labels:
        tp = cm[l][l]
        fp = sum(cm[g][l] for g in labels if g != l)
        fn = sum(cm[l][p] for p in labels if p != l)
        p = _safe_div(tp, tp + fp)
        rc = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * p * rc, p + rc)
        per[l] = {"precision": _r(p), "recall": _r(rc), "f1": _r(f1),
                  "support": tp + fn}
    return per


def _macro(per: Dict[str, Dict[str, float]], labels: List[str]) -> Dict[str, float]:
    return {k: _r(sum(per[l][k] for l in labels) / len(labels))
            for k in ("precision", "recall", "f1")}


def _roc_auc(rows: Sequence[Dict[str, str]]) -> float:
    return _r(_auc([(float(r["score"]), _flag(r, "gold")) for r in rows]))


def classification(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """分类口径：accuracy / macro P-R-F1 / 混淆矩阵（混淆键 = 出现过的 gold 标签，字典序）。"""
    labels = sorted({str(r["gold"]) for r in rows} | {str(r["pred"]) for r in rows})
    cm = _confusion(rows, labels)
    n = len(rows)
    correct = sum(cm[l][l] for l in labels)
    per = _per_label(cm, labels)
    macro = _macro(per, labels)
    out: Dict[str, Any] = {
        "family": "classification",
        "n": n,
        "accuracy": _r(correct / n),
        "macro": macro,
        "confusion": {g: cm[g] for g in labels},
        "per_label": per,
    }
    if all(str(r["gold"]) in ("0", "1") for r in rows) and all("score" in r for r in rows):
        out["roc_auc"] = _roc_auc(rows)
    return out


def _query_metrics(items: List[Tuple[int, int]], k: int) -> Tuple[float, float, float,
                                                                        float, float]:
    """单查询的 recall@k / precision@k / RR / NDCG@k / AP。"""
    rel = [y for _rk, y in sorted(items)]
    topk = rel[:k]
    total_rel = sum(rel)
    recall = _safe_div(sum(topk), total_rel)
    precision = _safe_div(sum(topk), k)
    rr = 0.0
    for i, y in enumerate(rel, 1):
        if y:
            rr = 1.0 / i
            break
    dcg = sum(y / math.log2(i + 1) for i, y in enumerate(rel[:k], 1))
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(total_rel, k) + 1))
    ndcg = _safe_div(dcg, ideal)
    hits, ap = 0, 0.0
    for i, y in enumerate(rel, 1):
        if y:
            hits += 1
            ap += hits / i
    return recall, precision, rr, ndcg, _safe_div(ap, total_rel)


def retrieval(rows: Sequence[Dict[str, str]], k: int = 5, **_kwargs) -> Dict[str, Any]:
    """检索口径：recall@k / precision@k / MRR / NDCG@k / MAP（按 query_id 分组，rank 升序）。"""
    groups: Dict[str, List[Tuple[int, int]]] = {}
    for r in rows:
        groups.setdefault(str(r["query_id"]), []).append(
            (int(_num(r, "rank")), _flag(r, "relevant")))
    recalls, precisions, rrs, ndcgs, aps = [], [], [], [], []
    for _q, items in sorted(groups.items()):
        recall, precision, rr, ndcg, ap = _query_metrics(items, k)
        recalls.append(recall)
        precisions.append(precision)
        rrs.append(rr)
        ndcgs.append(ndcg)
        aps.append(ap)
    return {
        "family": "retrieval", "k": k, "queries": len(groups), "n": len(rows),
        "recall_at_k": _r(sum(recalls) / len(recalls) if recalls else 0.0),
        "precision_at_k": _r(sum(precisions) / len(precisions) if precisions else 0.0),
        "mrr": _r(sum(rrs) / len(rrs) if rrs else 0.0),
        "ndcg_at_k": _r(sum(ndcgs) / len(ndcgs) if ndcgs else 0.0),
        "map": _r(sum(aps) / len(aps) if aps else 0.0),
    }


def extraction(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """抽取口径：整条精确匹配 + 字段级 P/R/F1（gold_fields / pred_fields = JSON 数组）。"""
    em, tp, fp, fn = 0, 0, 0, 0
    for r in rows:
        g = set(json_doc.loads(r["gold_fields"], list, what="gold_fields"))
        p = set(json_doc.loads(r["pred_fields"], list, what="pred_fields"))
        if g == p:
            em += 1
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
    pr = _safe_div(tp, tp + fp)
    rc = _safe_div(tp, tp + fn)
    return {"family": "extraction", "n": len(rows), "exact_match": _r(em / len(rows)),
            "field_precision": _r(pr), "field_recall": _r(rc),
            "field_f1": _r(_safe_div(2 * pr * rc, pr + rc)),
            "tp": tp, "fp": fp, "fn": fn}


def generation(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """生成口径（确定性代理）：精确匹配率 + 字符级 F1 + 词序不敏感的集合 F1。"""
    em, char_f1, set_f1 = 0, [], []
    for r in rows:
        g, p = str(r["reference"]), str(r["output"])
        if g == p:
            em += 1
        gs, ps = set(g), set(p)
        prec, rec = _safe_div(len(gs & ps), len(ps)), _safe_div(len(gs & ps), len(gs))
        char_f1.append(_safe_div(2 * prec * rec, prec + rec))
        gt, pt = set(g.split()), set(p.split())
        p2, r2 = _safe_div(len(gt & pt), len(pt)), _safe_div(len(gt & pt), len(gt))
        set_f1.append(_safe_div(2 * p2 * r2, p2 + r2))
    n = len(rows)
    return {"family": "generation", "n": n, "exact_match": _r(em / n),
            "char_f1": _r(sum(char_f1) / n), "token_set_f1": _r(sum(set_f1) / n)}


def _squared_errors(g: Sequence[float], p: Sequence[float]) -> List[float]:
    return [(a - b) ** 2 for a, b in zip(g, p, strict=True)]


def regression(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """回归口径：MAE / RMSE / R² / MAPE（MAPE 仅在 gold≠0 的样本上计算，样本数显式给出）。"""
    g = [_num(r, "gold") for r in rows]
    p = [_num(r, "pred") for r in rows]
    n = len(rows)
    mae = sum(abs(a - b) for a, b in zip(g, p, strict=True)) / n
    rmse = math.sqrt(sum(_squared_errors(g, p)) / n)
    mg = sum(g) / n
    ss_tot = sum((a - mg) ** 2 for a in g)
    ss_res = sum(_squared_errors(g, p))
    nz = [(a, b) for a, b in zip(g, p, strict=True) if a != 0]
    mape = (sum(abs((a - b) / a) for a, b in nz) / len(nz)) if nz else 0.0
    return {"family": "regression", "n": n, "mae": _r(mae), "rmse": _r(rmse),
            "r2": _r(1 - _safe_div(ss_res, ss_tot)), "mape": _r(mape),
            "mape_samples": len(nz)}


def _calibration_buckets(pairs: Sequence[Tuple[float, int]], n: int,
                        bins: int) -> Tuple[List[Dict[str, Any]], float]:
    """等宽分箱（空箱跳过）→ (可靠性桶明细, ECE)。"""
    buckets: List[Dict[str, Any]] = []
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if not sel:
            continue
        conf = sum(p for p, _ in sel) / len(sel)
        acc = sum(y for _, y in sel) / len(sel)
        ece += (len(sel) / n) * abs(conf - acc)
        buckets.append({"range": "[%.1f,%.1f]" % (lo, hi), "n": len(sel),
                        "confidence": _r(conf), "accuracy": _r(acc),
                        "gap": _r(abs(conf - acc))})
    return buckets, ece


def calibration(rows: Sequence[Dict[str, str]], bins: int = 10, **_kwargs) -> Dict[str, Any]:
    """校准口径：ECE（等宽分箱，空箱跳过并给出非空箱数）/ Brier / 可靠性桶明细。"""
    pairs = [(_num(r, "prob"), _flag(r, "gold")) for r in rows]
    if any(not (0.0 <= p <= 1.0) for p, _ in pairs):
        raise ValueError("prob 必须在 [0,1]")
    n = len(pairs)
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    buckets, ece = _calibration_buckets(pairs, n, bins)
    return {"family": "calibration", "n": n, "bins": bins,
            "nonempty_bins": len(buckets), "ece": _r(ece), "brier": _r(brier),
            "buckets": buckets}


def agreement(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """标注一致性口径：Cohen's kappa（两标注者，公式 κ = (po − pe)/(1 − pe)）+ 原始一致率。"""
    labels = sorted({str(r["a"]) for r in rows} | {str(r["b"]) for r in rows})
    n = len(rows)
    cm = {x: {y: 0 for y in labels} for x in labels}
    for r in rows:
        cm[str(r["a"])][str(r["b"])] += 1
    po = sum(cm[l][l] for l in labels) / n
    pe = sum((sum(cm[l].values()) / n) * (sum(cm[g][l] for g in labels) / n)
             for l in labels)
    return {"family": "agreement", "n": n, "labels": len(labels),
            "observed_agreement": _r(po), "expected_agreement": _r(pe),
            "cohen_kappa": _r(_safe_div(po - pe, 1 - pe)),
            "confusion": {x: cm[x] for x in labels}}


def preference(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """偏好/对齐口径：一致率 + 胜率（ties 单列，不计入胜率分母之外）。"""
    n = len(rows)
    agree = sum(1 for r in rows if str(r["judge"]).strip() == str(r["human"]).strip())
    win = sum(1 for r in rows if str(r["judge"]).strip() == "a")
    loss = sum(1 for r in rows if str(r["judge"]).strip() == "b")
    tie = n - win - loss
    return {"family": "preference", "n": n, "agreement": _r(agree / n),
            "win": win, "loss": loss, "tie": tie,
            "win_rate_excl_tie": _r(_safe_div(win, win + loss))}


def exact_judgement(rows: Sequence[Dict[str, str]], k: int = 4, **_kwargs) -> Dict[str, Any]:
    """形式化/问答判定口径：pass@1 与 pass@k（无偏估计，Chen et al. 2021 口径）。

    pass@k = 1 − C(n−c, k)/C(n, k)，n = 每题采样数，c = 其中通过数；c=0 记为 0，n<k 时该题跳过并计数。
    """
    groups: Dict[str, List[int]] = {}
    for r in rows:
        groups.setdefault(str(r["task_id"]), []).append(_flag(r, "passed"))
    pass1, passk, skipped, used = [], [], 0, 0
    for _t, ys in sorted(groups.items()):
        n, c = len(ys), sum(ys)
        pass1.append(c / n)
        if n < k:
            skipped += 1
            continue
        used += 1
        if c == 0:
            passk.append(0.0)
            continue
        if n - c < k:
            passk.append(1.0)
            continue
        num = 1.0
        for i in range(k):
            num *= (n - c - i) / (n - i)
        passk.append(1 - num)
    return {"family": "exact_judgement", "k": k, "tasks": len(groups), "n": len(rows),
            "pass_at_1": _r(sum(pass1) / len(pass1) if pass1 else 0.0),
            "pass_at_k": _r(sum(passk) / len(passk) if passk else 0.0),
            "tasks_used_for_passk": used, "tasks_skipped_insufficient_samples": skipped}


def latency_cost(rows: Sequence[Dict[str, str]], price_per_1k_in: float = 0.0,
                 price_per_1k_out: float = 0.0, **_kwargs) -> Dict[str, Any]:
    """服务口径：时延分位（最近秩法，显式说明）+ 吞吐 + 成本/1k 调用（单价显式传入）。"""
    lat = sorted(_num(r, "latency_ms") for r in rows)

    def pct(q: float) -> float:
        idx = max(0, min(len(lat) - 1, math.ceil(q * len(lat)) - 1))
        return _r(lat[idx])

    tin = sum(_num(r, "tokens_in") for r in rows)
    tout = sum(_num(r, "tokens_out") for r in rows)
    n = len(rows)
    cost = (tin / 1000.0) * price_per_1k_in + (tout / 1000.0) * price_per_1k_out
    return {"family": "latency_cost", "n": n,
            "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
            "mean_ms": _r(sum(lat) / n), "max_ms": _r(lat[-1]),
            "tokens_in": int(tin), "tokens_out": int(tout),
            "price_per_1k_in": _r(price_per_1k_in),
            "price_per_1k_out": _r(price_per_1k_out),
            "cost_total": _r(cost), "cost_per_1k_calls": _r(cost / n * 1000)}


def drift(rows: Sequence[Dict[str, str]], **_kwargs) -> Dict[str, Any]:
    """分布漂移口径：PSI（Population Stability Index）= Σ(p−q)·ln(p/q)，空桶用 1e-6 平滑并显式记档。"""
    eps = 1e-6
    psi = 0.0
    detail = []
    for r in rows:
        p = _num(r, "expected") + eps
        q = _num(r, "actual") + eps
        term = (p - q) * math.log(p / q)
        psi += term
        detail.append({"bucket": r.get("bucket", ""), "expected": _r(p), "actual": _r(q),
                       "term": _r(term)})
    return {"family": "drift", "buckets": len(rows), "psi": _r(psi),
            "smoothing_epsilon": eps, "detail": detail}
