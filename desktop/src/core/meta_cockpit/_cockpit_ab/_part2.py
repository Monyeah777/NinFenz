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


def analyze(document: dict, ballots: list[dict], opts: AnalyzeOptions | None = None) -> dict:
    opts = opts if opts is not None else AnalyzeOptions()
    min_pairs = opts.min_pairs
    min_effect = opts.min_effect
    alpha = opts.alpha
    min_judges = opts.min_judges
    min_agreement = opts.min_agreement
    min_pairs_per_model = opts.min_pairs_per_model
    issues = validate_experiment(document)
    if issues:
        raise ValueError("invalid experiment: " + "; ".join(issues))
    ballot_issues = [error.message for error in BALLOT_VALIDATOR.iter_errors(ballots)]
    if ballot_issues:
        raise ValueError("invalid ballots: " + "; ".join(ballot_issues))
    ballot_secrets = secret_guard.find(ballots, "$.ballots")
    if ballot_secrets:
        raise ValueError(
            "sensitive data in ballots: "
            + ",".join("{} ({})".format(item["path"], item["kind"]) for item in ballot_secrets)
        )
    registered = document["analysis_plan"]["thresholds"]
    overrides = {
        "min_pairs": min_pairs,
        "min_effect": min_effect,
        "alpha": alpha,
        "min_judges": min_judges,
        "min_agreement": min_agreement,
        "min_pairs_per_model": min_pairs_per_model,
    }
    if any(value is not None and value != registered[key] for key, value in overrides.items()):
        raise ValueError("analysis thresholds differ from preregistration")
    min_pairs = registered["min_pairs"]
    min_effect = registered["min_effect"]
    alpha = registered["alpha"]
    min_judges = registered["min_judges"]
    min_agreement = registered["min_agreement"]
    min_pairs_per_model = registered["min_pairs_per_model"]
    mapping = _mapping(document)
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
    if issues:
        raise ValueError("invalid ballots: " + "; ".join(issues))

    outcomes = []
    model_outcomes: dict[str, list[str]] = {}
    agreement_values = []
    unanimous = 0
    for pair_id in sorted(mapping):
        votes = grouped.get(pair_id, [])
        counts = Counter(ballot["winner"] for ballot in votes)
        if not votes:
            outcome = "missing"
        elif counts["tie"] >= max(counts["A"], counts["B"]) or counts["A"] == counts["B"]:
            outcome = "tie"
        else:
            label = "A" if counts["A"] > counts["B"] else "B"
            outcome = mapping[pair_id][label]
        outcomes.append(outcome)
        model_id = mapping[pair_id]["trials"]["baseline"]["model_id"]
        model_outcomes.setdefault(model_id, []).append(outcome)
        labels = [ballot["winner"] for ballot in votes]
        if len(labels) >= 2:
            comparisons = 0
            agrees = 0
            for left in range(len(labels)):
                for right in range(left + 1, len(labels)):
                    comparisons += 1
                    agrees += labels[left] == labels[right]
            agreement_values.append(agrees / comparisons)
            unanimous += len(set(labels)) == 1

    guided = outcomes.count("guided")
    baseline = outcomes.count("baseline")
    ties = outcomes.count("tie")
    missing = outcomes.count("missing")
    decisive = guided + baseline
    rate = guided / decisive if decisive else 0.5
    low, high = _wilson(guided, decisive)
    p_value = _sign_test_p(guided, decisive)
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
    judge_count = len({ballot["judge_id"] for ballot in ballots})
    agreement_value = sum(agreement_values) / len(agreement_values) if agreement_values else 0.0
    sparse_models = [
        model_id for model_id, values in per_model.items() if values["pairs"] < min_pairs_per_model
    ]
    if (
        len(mapping) < min_pairs
        or decisive < min_pairs
        or judge_count < min_judges
        or sparse_models
    ):
        decision = "insufficient-evidence"
    elif agreement_value < min_agreement:
        decision = "judge-disagreement"
    elif low > 0.5 and rate - 0.5 >= min_effect and p_value <= alpha:
        decision = "guided-better"
    elif high < 0.5 and 0.5 - rate >= min_effect and p_value <= alpha:
        decision = "baseline-better"
    else:
        decision = "inconclusive"
    mean_agreement = (
        round(sum(agreement_values) / len(agreement_values), 6) if agreement_values else None
    )
    result = {
        "schema": "nf-cockpit-ab-analysis/1",
        "experiment_id": document["experiment_id"],
        "pairs": len(mapping),
        "planned_pairs": document["analysis_plan"]["planned_pairs"],
        "decisive": decisive,
        "guided_wins": guided,
        "baseline_wins": baseline,
        "ties": ties,
        "missing": missing,
        "guided_win_rate": round(rate, 6),
        "ci95": [round(low, 6), round(high, 6)],
        "effect_vs_half": round(rate - 0.5, 6),
        "sign_test_p": round(p_value, 8),
        "judge_count": len({ballot["judge_id"] for ballot in ballots}),
        "judge_agreement": {
            "mean_pairwise": mean_agreement,
            "unanimous_pairs": unanimous,
            "rated_pairs": len(agreement_values),
        },
        "per_model": per_model,
        "decision": decision,
        "thresholds": {
            "min_pairs": min_pairs,
            "min_effect": min_effect,
            "alpha": alpha,
            "min_judges": min_judges,
            "min_agreement": min_agreement,
            "min_pairs_per_model": min_pairs_per_model,
        },
        "analysis_plan_digest": document["analysis_plan"]["plan_digest"],
        "power_plan": document["analysis_plan"]["power_plan"],
        "packet_digest": build_blind_packets(document)["packet_digest"],
        "ballots_digest": digest(ballots),
    }
    issues = [error.message for error in RESULT_VALIDATOR.iter_errors(result)]
    if issues:
        raise ValueError("invalid analysis: " + "; ".join(issues))
    result["digest"] = digest(result)
    return result
