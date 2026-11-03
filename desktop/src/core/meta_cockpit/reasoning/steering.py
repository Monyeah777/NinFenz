"""候选 log 域先验偏置：p' ∝ p · exp(β · s)。

与 NF 驾驶舱的关系：驾驶舱每轮只给模型 ≤5 个安全候选，模型只能选。本模块
在这些候选上做**确定性**先验偏置，用于搜索平面的 PUCT 先验，而不是替模型
打分：

- p：均匀先验（``prior_source="uniform"``），即驾驶舱“只给候选、不预设结构
  偏好”；结构信息全部进入下面的 log 域项而不做隐式打分。
- s：可复算的确定性特征之和，∈[-1, 1]（``normalization="none"``，无 z-score）
  - 候选 resolves 数（对 6 个 need 归一化）
  - cost 惩罚（-cost/3）
  - task_profile 缺口命中（候选新增键 ∩ repair_keys）
  - 方法记忆命中（候选原子出现在 history 簇里的比例）
  - 校准账本平均可靠性（calibration_ledger）
- β 有硬上限（``MAX_BETA = 0.5``，研究报告 B 的 B_MAX）；超过即 clamp 并在
  audit 里记 ``beta_cap`` / ``clamped``。
- 若 steering 后 top-1 概率 ≥ ``DEGENERATE_THRESHOLD = 0.95``，视为退化：
  **关闭 steering**（退回结构先验），审计记 ``disabled``；回退后仍退化则截断。

所有输出都可复算；本模块不读取模型、不联网、不写 State。
"""

from __future__ import annotations

import hashlib
import json
import math

from . import bridge as nf

SCHEMA = "nf-steering-audit/1"
MAX_BETA = 0.5
DEGENERATE_THRESHOLD = 0.95
DEFAULT_BETA = 0.5
PROB_FLOOR = 1e-9
ROUND = 6

#: 信号权重（和为 1，保证 s ∈ [-1, 1] 的线性组合仍在 [-1, 1]）。
SIGNAL_WEIGHTS = {
    "resolves": 0.40,
    "cost": 0.15,
    "gap_match": 0.25,
    "method_memory": 0.10,
    "reliability": 0.10,
}
_WEIGHT_TOTAL = sum(abs(value) for value in SIGNAL_WEIGHTS.values())


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _canonical_digest(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def base_prior(candidates: list[dict]) -> list[float]:
    """均匀先验 p（``p_i = 1/n``）；空输入 fail-closed。

    结构信息（resolves/cost/gap/记忆/可靠性）全部由 ``s`` 的 log 域项承载，
    避免在公开审计里出现任何“隐式评分”。
    """

    if not isinstance(candidates, (list, tuple)) or not candidates:
        raise ValueError("candidates must be a non-empty list")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be an object")
        resolves = candidate.get("resolves", [])
        cost = candidate.get("cost")
        if not isinstance(resolves, (list, tuple)):
            raise ValueError("candidate resolves must be a list")
        if not _is_number(cost) or cost <= 0:
            raise ValueError("candidate cost must be positive")
    count = len(candidates)
    return [1.0 / count for _ in candidates]


def _validate_state(state) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    if not isinstance(state.get("artifact"), dict):
        raise ValueError("state must contain artifact object")


def _validate_candidates(candidates) -> list[dict]:
    if not isinstance(candidates, (list, tuple)) or not candidates:
        raise ValueError("candidates must be a non-empty list")
    contracts = nf.live_selector.CONTRACTS
    known_needs = set(nf.NEEDS)
    out = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate[{index}] must be an object")
        cluster = candidate.get("cluster")
        if not isinstance(cluster, (list, tuple)) or not cluster:
            raise ValueError("candidate cluster must be a non-empty list")
        if len(cluster) > nf.MAX_ATOMS or len(set(cluster)) != len(cluster):
            raise ValueError("candidate cluster must contain at most 3 unique atoms")
        for atom_id in cluster:
            if atom_id not in contracts:
                raise ValueError("candidate cluster references unknown atom")
        cost = candidate.get("cost")
        if not isinstance(cost, int) or isinstance(cost, bool) or cost < 1:
            raise ValueError("candidate cost must be a positive integer")
        resolves = candidate.get("resolves", [])
        if not isinstance(resolves, (list, tuple)) or not set(resolves) <= known_needs:
            raise ValueError("candidate resolves must be known need names")
        out.append(
            {
                "cluster": list(cluster),
                "cost": cost,
                "resolves": list(resolves),
                "effect": candidate.get("effect"),
            }
        )
    return out


def _reliability(state, ledger, atoms: list[str]) -> float:
    ledger = ledger if ledger is not None else nf.initial_ledger()
    if not isinstance(ledger, dict):
        raise ValueError("ledger must be an object")
    values = []
    for atom_id in atoms:
        record = ledger.get(atom_id)
        if not isinstance(record, dict) or not _is_number(record.get("reliability")):
            raise ValueError("ledger entry missing reliability")
        values.append(float(record["reliability"]))
    return sum(values) / len(values) if values else 0.0


def _signals(state, candidate, *, repair_keys, history_clusters, ledger) -> dict:
    before = nf.available_keys(state)
    after = nf.live_selector.simulate(tuple(candidate["cluster"]), state)
    adds = (after or set()) - before
    repairs = set(repair_keys)
    gap_hits = len(adds & repairs)
    gap_match = gap_hits / len(repairs) if repairs else 0.0
    memory_hits = sum(
        1
        for atom_id in candidate["cluster"]
        if any(atom_id in cluster for cluster in history_clusters)
    )
    return {
        "resolves": len(candidate["resolves"]) / len(nf.NEEDS),
        "cost": -(candidate["cost"] / nf.MAX_COST),
        "gap_match": gap_match,
        "method_memory": memory_hits / len(candidate["cluster"]),
        "reliability": _reliability(state, ledger, candidate["cluster"]),
        "gap_hits": gap_hits,
        "repair_key_count": len(repairs),
        "memory_hits": memory_hits,
        "adds": sorted(adds),
    }


def _combine(signals: dict) -> float:
    raw = sum(SIGNAL_WEIGHTS[key] * signals[key] for key in SIGNAL_WEIGHTS)
    return max(-1.0, min(1.0, raw / _WEIGHT_TOTAL))


def _softmax(logits: list[float]) -> list[float]:
    peak = max(logits)
    exps = [math.exp(value - peak) for value in logits]
    total = math.fsum(exps)
    return [value / total for value in exps]


def _truncate(posterior: list[float], threshold: float) -> list[float]:
    values = list(posterior)
    for _ in range(8):
        over = [index for index, value in enumerate(values) if value > threshold]
        if not over:
            break
        excess = math.fsum(values[index] - threshold for index in over)
        for index in over:
            values[index] = threshold
        free = [index for index in range(len(values)) if index not in over]
        mass = math.fsum(values[index] for index in free)
        if not free:
            break
        if mass > 0:
            for index in free:
                values[index] += excess * values[index] / mass
        else:
            share = excess / len(free)
            for index in free:
                values[index] += share
    total = math.fsum(values)
    return [value / total for value in values]


def steer(
    state: dict,
    candidates: list[dict],
    *,
    beta: float = DEFAULT_BETA,
    ledger: dict | None = None,
    max_beta: float = MAX_BETA,
    threshold: float = DEGENERATE_THRESHOLD,
) -> dict:
    """计算带审计向量的先验偏置。非法输入 fail-closed 抛 ValueError。"""

    _validate_state(state)
    checked = _validate_candidates(candidates)
    if not _is_number(beta) or not math.isfinite(beta) or beta < 0:
        raise ValueError("beta must be a finite non-negative number")
    if not _is_number(max_beta) or max_beta <= 0:
        raise ValueError("max_beta must be positive")
    if not _is_number(threshold) or not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")

    warnings: list[str] = []
    beta_applied = float(beta)
    if beta_applied > max_beta:
        beta_applied = float(max_beta)
        warnings.append("beta-clamped")

    priors = base_prior(checked)
    repair_keys = nf.repair_keys(state)
    history_clusters = nf.history_clusters(state)
    entries = []
    for candidate, prior in zip(checked, priors):
        signals = _signals(
            state,
            candidate,
            repair_keys=repair_keys,
            history_clusters=history_clusters,
            ledger=ledger,
        )
        score = _combine(signals)
        entries.append(
            {
                "cluster": candidate["cluster"],
                "cost": candidate["cost"],
                "resolves": candidate["resolves"],
                "prior": prior,
                "prior_terms": signals,
                "bias": beta_applied * score,
            }
        )

    logits = [
        math.log(max(entry["prior"], PROB_FLOOR)) + entry["bias"] for entry in entries
    ]
    posterior = _softmax(logits)

    # 退化保护：steering 把某个候选推到 top-1 ≥ 0.95 就不再允许它影响选择，
    # 关闭 steering 并退回均匀先验；回退后仍退化（均匀先验下只在 n==1 时发生）
    # 则截断概率质量。β ≤ 0.5 使这条路径在正常候选数下几乎不可能触发，保留
    # 作为安全阀。
    disabled = False
    if max(posterior) >= threshold:
        disabled = True
        warnings.append("steering-disabled")
        posterior = list(priors)
        if max(posterior) >= threshold:
            posterior = _truncate(posterior, threshold)
            warnings.append("prior-truncated")
    if len(posterior) == 1:
        warnings.append("single-candidate")

    degenerate = disabled
    clamped = bool(beta_applied < float(beta))
    for entry, value in zip(entries, posterior):
        entry["posterior"] = value
        entry["clamped"] = clamped
    audit = {
        "schema": SCHEMA,
        "candidate_count": len(entries),
        "prior_source": "uniform",
        "normalization": "none",
        "beta_requested": float(beta),
        "beta_applied": beta_applied,
        "beta_cap": float(max_beta),
        "clamped": clamped,
        "max_beta": float(max_beta),
        "degenerate_threshold": float(threshold),
        "degenerate": degenerate,
        "disabled": disabled,
        "warnings": list(dict.fromkeys(warnings)),
        "posterior": posterior,
        "candidates": entries,
        "no_model_scores": True,
    }
    audit["digest"] = _canonical_digest(
        {
            "beta_applied": beta_applied,
            "beta_cap": float(max_beta),
            "clamped": clamped,
            "threshold": threshold,
            "disabled": disabled,
            "prior_source": "uniform",
            "normalization": "none",
            "candidates": [
                {
                    "cluster": entry["cluster"],
                    "cost": entry["cost"],
                    "prior": round(entry["prior"], ROUND),
                    "prior_terms": entry["prior_terms"],
                    "bias": round(entry["bias"], ROUND),
                    "posterior": round(entry["posterior"], ROUND),
                }
                for entry in entries
            ],
        }
    )
    return audit


def prior_vector(state: dict, candidates: list[dict]) -> list[float]:
    """不做偏置时的结构先验（β=0 的等价物），用于对照实验。"""

    del state
    return base_prior(_validate_candidates(candidates))
