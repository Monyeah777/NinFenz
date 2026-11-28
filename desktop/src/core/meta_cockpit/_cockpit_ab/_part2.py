"""core.cockpit_ab 私有实现分片 2/2（对外只经 core.cockpit_ab 门面导入）：analyze"""

from __future__ import annotations

from collections import Counter

from core.meta_cockpit import secret_guard

from ._part1 import (
    BALLOT_VALIDATOR,
    RESULT_VALIDATOR,
    AnalyzeOptions,
    _mapping,
    _sign_test_p,
    _wilson,
    build_blind_packets,
    digest,
    validate_experiment,
)


def _thresholds(document: dict, opts: AnalyzeOptions) -> dict:
    registered = document["analysis_plan"]["thresholds"]
    overrides = {
        "min_pairs": opts.min_pairs,
        "min_effect": opts.min_effect,
        "alpha": opts.alpha,
        "min_judges": opts.min_judges,
        "min_agreement": opts.min_agreement,
        "min_pairs_per_model": opts.min_pairs_per_model,
    }
    if any(value is not None and value != registered[key] for key, value in overrides.items()):
        raise ValueError("analysis thresholds differ from preregistration")
    return registered


def _ballot_checks(ballots: list[dict]) -> None:
    ballot_issues = [error.message for error in BALLOT_VALIDATOR.iter_errors(ballots)]
    if ballot_issues:
        raise ValueError("invalid ballots: " + "; ".join(ballot_issues))
    ballot_secrets = secret_guard.find(ballots, "$.ballots")
    if ballot_secrets:
        raise ValueError(
            "sensitive data in ballots: "
            + ",".join("{} ({})".format(item["path"], item["kind"]) for item in ballot_secrets)
        )


def _group_ballots(ballots: list[dict], mapping: dict) -> tuple[dict[str, list[dict]], list[str]]:
    issues: list[str] = []
    grouped: dict[str, list[dict]] = {}
    ballot_keys = set()
    for ballot in ballots:
        pair_id = ballot.get("pair_id")
        if pair_id not in mapping:
            issues.append("unknown pair")
            continue
        if ballot.get("winner") not in {"A", "B", "tie"}:
            issues.append("invalid winner")
            continue
        if not isinstance(ballot.get("judge_id"), str) or not ballot["judge_id"]:
            issues.append("missing judge id")
            continue
        key = (pair_id, ballot["judge_id"])
        if key in ballot_keys:
            issues.append("duplicate ballot: {}/{}".format(*key))
            continue
        ballot_keys.add(key)
        grouped.setdefault(pair_id, []).append(ballot)
    return grouped, issues


def _pair_outcome(votes: list[dict], mapping: dict, pair_id: str) -> str:
    counts = Counter(ballot["winner"] for ballot in votes)
    if not votes:
        return "missing"
    if counts["tie"] >= max(counts["A"], counts["B"]) or counts["A"] == counts["B"]:
        return "tie"
    label = "A" if counts["A"] > counts["B"] else "B"
    return mapping[pair_id][label]


def _agreement(labels: list[str]) -> tuple[float | None, bool]:
    if len(labels) < 2:
        return None, False
    comparisons = 0
    agrees = 0
    for left in range(len(labels)):
        for right in range(left + 1, len(labels)):
            comparisons += 1
            agrees += labels[left] == labels[right]
    return agrees / comparisons, len(set(labels)) == 1


def _outcomes(
    mapping: dict, grouped: dict[str, list[dict]]
) -> tuple[list[str], dict[str, list[str]], list[float], int]:
    outcomes = []
    model_outcomes: dict[str, list[str]] = {}
    agreement_values = []
    unanimous = 0
    for pair_id in sorted(mapping):
        votes = grouped.get(pair_id, [])
        outcome = _pair_outcome(votes, mapping, pair_id)
        outcomes.append(outcome)
        model_id = mapping[pair_id]["trials"]["baseline"]["model_id"]
        model_outcomes.setdefault(model_id, []).append(outcome)
        labels = [ballot["winner"] for ballot in votes]
        agreement, is_unanimous = _agreement(labels)
        if agreement is not None:
            agreement_values.append(agreement)
            unanimous += is_unanimous
    return outcomes, model_outcomes, agreement_values, unanimous


def _per_model(model_outcomes: dict[str, list[str]]) -> dict:
    per_model = {}
    for model_id, values in sorted(model_outcomes.items()):
        model_guided = values.count("guided")
        model_baseline = values.count("baseline")
        model_decisive = model_guided + model_baseline
        model_rate = model_guided / model_decisive if model_decisive else 0.5
        per_model[model_id] = {
            "pairs": len(values),
            "guided_wins": model_guided,
            "baseline_wins": model_baseline,
            "ties": values.count("tie"),
            "guided_win_rate": round(model_rate, 6),
        }
    return per_model


def _mean_agreement(agreement_values: list[float]) -> float | None:
    if not agreement_values:
        return None
    return round(sum(agreement_values) / len(agreement_values), 6)


def _insufficient(stats: dict, thresholds: dict) -> bool:
    if len(stats["mapping"]) < thresholds["min_pairs"]:
        return True
    if stats["decisive"] < thresholds["min_pairs"]:
        return True
    if stats["judge_count"] < thresholds["min_judges"]:
        return True
    return bool(stats["sparse_models"])


def _guided_better(stats: dict, thresholds: dict) -> bool:
    return (
        stats["low"] > 0.5
        and stats["rate"] - 0.5 >= thresholds["min_effect"]
        and stats["p_value"] <= thresholds["alpha"]
    )


def _baseline_better(stats: dict, thresholds: dict) -> bool:
    return (
        stats["high"] < 0.5
        and 0.5 - stats["rate"] >= thresholds["min_effect"]
        and stats["p_value"] <= thresholds["alpha"]
    )


def _decision(stats: dict, thresholds: dict) -> str:
    if _insufficient(stats, thresholds):
        return "insufficient-evidence"
    if stats["agreement_value"] < thresholds["min_agreement"]:
        return "judge-disagreement"
    if _guided_better(stats, thresholds):
        return "guided-better"
    if _baseline_better(stats, thresholds):
        return "baseline-better"
    return "inconclusive"


def _result(
    document: dict, stats: dict, thresholds: dict, per_model: dict, decision: str
) -> dict:
    return {
        "schema": "nf-cockpit-ab-analysis/1",
        "experiment_id": document["experiment_id"],
        "pairs": len(stats["mapping"]),
        "planned_pairs": document["analysis_plan"]["planned_pairs"],
        "decisive": stats["decisive"],
        "guided_wins": stats["guided"],
        "baseline_wins": stats["baseline"],
        "ties": stats["ties"],
        "missing": stats["missing"],
        "guided_win_rate": round(stats["rate"], 6),
        "ci95": [round(stats["low"], 6), round(stats["high"], 6)],
        "effect_vs_half": round(stats["rate"] - 0.5, 6),
        "sign_test_p": round(stats["p_value"], 8),
        "judge_count": stats["judge_count"],
        "judge_agreement": {
            "mean_pairwise": _mean_agreement(stats["agreement_values"]),
            "unanimous_pairs": stats["unanimous"],
            "rated_pairs": len(stats["agreement_values"]),
        },
        "per_model": per_model,
        "decision": decision,
        "thresholds": dict(thresholds),
        "analysis_plan_digest": document["analysis_plan"]["plan_digest"],
        "power_plan": document["analysis_plan"]["power_plan"],
        "packet_digest": stats["packet_digest"],
        "ballots_digest": stats["ballots_digest"],
    }


def _stats(
    document: dict,
    mapping: dict,
    model_outcomes: dict,
    agreement_values: list[float],
    unanimous: int,
    thresholds: dict,
) -> tuple[dict, dict]:
    outcomes = [outcome for values in model_outcomes.values() for outcome in values]
    guided = outcomes.count("guided")
    baseline = outcomes.count("baseline")
    ties = outcomes.count("tie")
    missing = outcomes.count("missing")
    decisive = guided + baseline
    rate = guided / decisive if decisive else 0.5
    low, high = _wilson(guided, decisive)
    p_value = _sign_test_p(guided, decisive)
    per_model = _per_model(model_outcomes)
    stats = {
        "mapping": mapping,
        "guided": guided,
        "baseline": baseline,
        "ties": ties,
        "missing": missing,
        "decisive": decisive,
        "rate": rate,
        "low": low,
        "high": high,
        "p_value": p_value,
        "agreement_values": agreement_values,
        "agreement_value": (sum(agreement_values) / len(agreement_values)
                            if agreement_values else 0.0),
        "unanimous": unanimous,
        "sparse_models": [
            model_id for model_id, values in per_model.items()
            if values["pairs"] < thresholds["min_pairs_per_model"]
        ],
        "packet_digest": build_blind_packets(document)["packet_digest"],
    }
    return stats, per_model


def analyze(document: dict, ballots: list[dict], opts: AnalyzeOptions | None = None) -> dict:
    opts = opts if opts is not None else AnalyzeOptions()
    issues = validate_experiment(document)
    if issues:
        raise ValueError("invalid experiment: " + "; ".join(issues))
    _ballot_checks(ballots)
    thresholds = _thresholds(document, opts)
    mapping = _mapping(document)
    grouped, ballot_issues = _group_ballots(ballots, mapping)
    if ballot_issues:
        raise ValueError("invalid ballots: " + "; ".join(ballot_issues))

    outcomes, model_outcomes, agreement_values, unanimous = _outcomes(mapping, grouped)
    del outcomes
    stats, per_model = _stats(document, mapping, model_outcomes, agreement_values, unanimous, thresholds)
    stats["judge_count"] = len({ballot["judge_id"] for ballot in ballots})
    stats["ballots_digest"] = digest(ballots)
    decision = _decision(stats, thresholds)
    result = _result(document, stats, thresholds, per_model, decision)
    issues = [error.message for error in RESULT_VALIDATOR.iter_errors(result)]
    if issues:
        raise ValueError("invalid analysis: " + "; ".join(issues))
    result["digest"] = digest(result)
    return result
