"""Offline paired blind A/B harness for recorded cockpit outputs."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from . import json_asset, secret_guard
from . import schema_compat as jsonschema

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "cockpit_ab.schema.json")
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
RESULT_SCHEMA = json_asset.load(BASE / "cockpit_ab_result.schema.json")
RESULT_VALIDATOR = jsonschema.Draft202012Validator(RESULT_SCHEMA)
BALLOT_SCHEMA = json_asset.load(BASE / "cockpit_ab_ballots.schema.json")
BALLOT_VALIDATOR = jsonschema.Draft202012Validator(BALLOT_SCHEMA)
ARMS = {"baseline", "guided"}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pair_key(trial: dict) -> tuple[str, str, int]:
    return (trial["prompt_id"], trial["model_id"], int(trial["seed"]))


def _prompt_set_digest(trials: list[dict]) -> str:
    facts = sorted(
        {
            (
                item["prompt_id"],
                item["prompt"],
                item["model_id"],
                int(item["seed"]),
            )
            for item in trials
        }
    )
    return digest(facts)


def _binomial_tail(n: int, start: int, p: float) -> float:
    if start > n:
        return 0.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(start, n + 1))


def power_analysis(
    effect: float, alpha: float = 0.05, target_power: float = 0.80, max_pairs: int = 500
) -> dict:
    if not 0 < effect <= 0.5:
        raise ValueError("effect must be in (0, 0.5]")
    if not 0 < alpha <= 0.2 or not 0.5 < target_power < 1:
        raise ValueError("invalid alpha or target power")
    alternative = 0.5 + effect
    for n in range(2, max_pairs + 1):
        critical = next((k for k in range(n + 1) if _binomial_tail(n, k, 0.5) <= alpha / 2), None)
        if critical is None:
            continue
        power = _binomial_tail(n, critical, alternative)
        if power >= target_power:
            return {
                "method": "two-sided-exact-sign",
                "effect": effect,
                "alpha": alpha,
                "target_power": target_power,
                "required_pairs": n,
                "estimated_power": round(power, 6),
            }
    raise ValueError("required sample exceeds max_pairs")


def preregister(
    document: dict,
    min_pairs: int = 8,
    min_effect: float = 0.10,
    alpha: float = 0.05,
    min_judges: int = 2,
    min_agreement: float = 0.60,
    min_pairs_per_model: int = 3,
    target_power: float | None = None,
    max_pairs: int = 500,
    planned_pairs: int | None = None,
) -> dict:
    result = json_asset.roundtrip(document)
    actual_pairs = len({_pair_key(trial) for trial in document["trials"]})
    planned_pairs = actual_pairs if planned_pairs is None else planned_pairs
    if planned_pairs != actual_pairs:
        raise ValueError("planned pairs differ from trial pairs")
    power_plan = None
    if target_power is not None:
        power_plan = power_analysis(
            min_effect, alpha=alpha, target_power=target_power, max_pairs=max_pairs
        )
        min_pairs = max(min_pairs, power_plan["required_pairs"])
    if planned_pairs < min_pairs:
        raise ValueError("planned pairs below preregistered minimum")
    plan = {
        "schema": "nf-cockpit-ab-plan/1",
        "thresholds": {
            "min_pairs": min_pairs,
            "min_effect": min_effect,
            "alpha": alpha,
            "min_judges": min_judges,
            "min_agreement": min_agreement,
            "min_pairs_per_model": min_pairs_per_model,
        },
        "prompt_set_digest": _prompt_set_digest(document["trials"]),
        "power_plan": power_plan,
        "planned_pairs": planned_pairs,
    }
    plan["plan_digest"] = digest(plan)
    result["analysis_plan"] = plan
    return result


def validate_experiment(document: dict) -> list[str]:
    issues = [error.message for error in VALIDATOR.iter_errors(document)]
    if issues:
        return issues
    plan = document["analysis_plan"]
    expected_prompt_digest = _prompt_set_digest(document["trials"])
    plan_payload = {
        "schema": plan["schema"],
        "thresholds": plan["thresholds"],
        "prompt_set_digest": plan["prompt_set_digest"],
        "power_plan": plan["power_plan"],
        "planned_pairs": plan["planned_pairs"],
    }
    if plan["prompt_set_digest"] != expected_prompt_digest:
        issues.append("analysis plan prompt set mismatch")
    if plan["plan_digest"] != digest(plan_payload):
        issues.append("analysis plan digest mismatch")
    grouped: dict[tuple[str, str, int], list[str]] = {}
    paired: dict[tuple[str, str, int], list[dict]] = {}
    for trial in document["trials"]:
        pair = _pair_key(trial)
        grouped.setdefault(pair, []).append(trial["arm"])
        paired.setdefault(pair, []).append(trial)
        if secret_guard.find(trial["output"], "$.trials[{}].output".format(trial["trial_id"])):
            issues.append("sensitive data in output: " + trial["trial_id"])
        if secret_guard.find(trial["prompt"], "$.trials[{}].prompt".format(trial["trial_id"])):
            issues.append("sensitive data in prompt: " + trial["trial_id"])
        actual = hashlib.sha256(trial["output"].encode("utf-8")).hexdigest()
        if actual != trial["output_digest"]:
            issues.append("output digest mismatch: " + trial["trial_id"])
    if plan["planned_pairs"] != len(paired):
        issues.append("planned pair count mismatch")
    for pair, arms in grouped.items():
        if sorted(arms) != ["baseline", "guided"]:
            issues.append(f"unpaired or duplicate arm: {pair}")
            continue
        left, right = paired[pair]
        if left["prompt"] != right["prompt"]:
            issues.append(f"prompt mismatch: {pair}")
        if left["generation"] != right["generation"]:
            issues.append(f"generation settings mismatch: {pair}")
        if left["resource_budget"] != right["resource_budget"]:
            issues.append(f"resource budget mismatch: {pair}")
        if any(item["status"] != "completed" for item in (left, right)):
            issues.append(f"incomplete trial: {pair}")
        if any(item["truncated"] for item in (left, right)):
            issues.append(f"truncated trial: {pair}")
    return issues


def _mapping(document: dict) -> dict[str, dict]:
    grouped: dict[tuple[str, str, int], dict] = {}
    for trial in document["trials"]:
        grouped.setdefault(_pair_key(trial), {})[trial["arm"]] = trial
    result = {}
    for pair, arms in grouped.items():
        pair_id = digest(
            {
                "experiment_id": document["experiment_id"],
                "pair": pair,
            }
        )[:24]
        bit = (
            hashlib.sha256(
                _canonical(
                    {
                        "experiment_id": document["experiment_id"],
                        "pair_id": pair_id,
                        "salt": document["blind_salt"],
                    }
                )
            ).digest()[0]
            & 1
        )
        result[pair_id] = {
            "A": "baseline" if bit == 0 else "guided",
            "B": "guided" if bit == 0 else "baseline",
            "trials": arms,
        }
    return result


def build_blind_packets(document: dict) -> dict:
    issues = validate_experiment(document)
    if issues:
        raise ValueError("invalid experiment: " + "; ".join(issues))
    mapping = _mapping(document)
    packets = []
    for pair_id in sorted(mapping):
        item = mapping[pair_id]
        options = {}
        for label in ("A", "B"):
            trial = item["trials"][item[label]]
            options[label] = {
                "output": trial["output"],
                "output_digest": trial["output_digest"],
            }
        packets.append(
            {
                "pair_id": pair_id,
                "prompt": item["trials"]["baseline"]["prompt"],
                "options": options,
                "instruction": "Choose A, B, or tie by goal fit and evidence warrant.",
            }
        )
    return {
        "schema": "nf-cockpit-blind-packets/1",
        "experiment_id": document["experiment_id"],
        "packets": packets,
        "packet_digest": digest(packets),
    }


def _wilson(wins: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.5, 0.5
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def _sign_test_p(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1))
    return min(1.0, 2 * tail / (2**n))


def analyze(
    document: dict,
    ballots: list[dict],
    min_pairs: int | None = None,
    min_effect: float | None = None,
    alpha: float | None = None,
    min_judges: int | None = None,
    min_agreement: float | None = None,
    min_pairs_per_model: int | None = None,
) -> dict:
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
