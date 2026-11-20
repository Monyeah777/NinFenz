"""Pre-conclusion checks for a feature-flag experiment.

Pure functions; no query engines. Blocking findings mean the experiment is
not yet valid to conclude, not that the product is wrong.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA = "nf-experiment-health/1"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # error|warning
    detail: str


@dataclass(frozen=True)
class Snapshot:
    key: str
    variants: tuple[str, ...]
    exposures: dict[str, int]
    metric_events: int
    min_samples: int = 100
    bucketing_changed: bool = False
    forced_variant: bool = False
    metric_immature: bool = False


def health(snapshot: Snapshot) -> dict[str, Any]:
    f: list[Finding] = []
    if len(snapshot.variants) < 2:
        f.append(Finding("few_variants", "error", "need at least two variants"))
    if any(not v for v in snapshot.variants):
        f.append(Finding("empty_variant", "error", "variant key must not be empty"))
    total = sum(max(0, int(v)) for v in snapshot.exposures.values())
    if total <= 0:
        f.append(Finding("no_exposures", "error", "no exposures recorded"))
    elif total < snapshot.min_samples:
        f.append(Finding("low_sample", "error",
                         f"{total} exposures < min {snapshot.min_samples}"))
    for variant in snapshot.variants:
        if snapshot.exposures.get(variant, 0) <= 0:
            f.append(Finding("empty_arm", "error", "no exposure for " + variant))
    if snapshot.metric_events <= 0:
        f.append(Finding("no_metric_events", "error", "metric event count is zero"))
    if snapshot.bucketing_changed:
        f.append(Finding("bucketing_changed", "error", "bucketing changed during the experiment"))
    if snapshot.forced_variant:
        f.append(Finding("forced_variant", "error", "a variant was forced"))
    if snapshot.metric_immature:
        f.append(Finding("metric_immature", "error", "metric window is not mature"))
    counts = [int(snapshot.exposures.get(v, 0)) for v in snapshot.variants]
    if counts and min(counts) > 0 and max(counts) > 3 * min(counts):
        f.append(Finding("imbalanced_arms", "warning", "exposure ratio exceeds 3x"))
    blockers = [x for x in f if x.severity == "error"]
    return {"schema": SCHEMA, "key": snapshot.key,
            "status": "blocked" if blockers else "ok",
            "can_conclude": not blockers,
            "findings": [x.__dict__ for x in f],
            "total_exposures": total}
