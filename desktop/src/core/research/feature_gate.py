"""Local feature gate: deterministic rollout/variants + local exposure log.

No network, no remote flag service. Buckets are sha256-derived from
(salt, flag, distinct_id); the same identity always gets the same bucket.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "nf-feature-gate/1"


@dataclass(frozen=True)
class Variant:
    key: str
    rollout_percentage: float


@dataclass(frozen=True)
class Flag:
    key: str
    active: bool = True
    rollout_percentage: float = 100.0
    variants: tuple[Variant, ...] = ()


@dataclass
class Exposure:
    flag: str
    variant: str | None
    distinct_id: str
    bucket: float
    at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def _bucket(salt: str, flag: str, distinct_id: str, purpose: str) -> float:
    raw = hashlib.sha256(f"{salt}|{flag}|{distinct_id}|{purpose}".encode()).digest()
    return (int.from_bytes(raw[:4], "big") / 2**32) * 100.0


class FeatureGate:
    def __init__(self, flags: list[Flag], salt: str = "nf-local") -> None:
        if not salt:
            raise ValueError("salt must not be empty")
        seen: set[str] = set()
        for flag in flags:
            if not flag.key or flag.key in seen:
                raise ValueError("duplicate or empty flag key: " + flag.key)
            seen.add(flag.key)
            if not 0 <= flag.rollout_percentage <= 100:
                raise ValueError("rollout_percentage out of range: " + flag.key)
            total = sum(v.rollout_percentage for v in flag.variants)
            if total > 100.0001:
                raise ValueError("variant percentages exceed 100: " + flag.key)
        self.flags = {p.key: p for p in flags}
        self.salt = salt
        self.exposures: list[Exposure] = []

    def evaluate(self, flag_key: str, distinct_id: str) -> dict[str, Any]:
        if not distinct_id:
            raise ValueError("distinct_id must not be empty")
        flag = self.flags.get(flag_key)
        if flag is None:
            return {"schema": SCHEMA, "enabled": False, "reason": "unknown_flag",
                    "flag": flag_key, "variant": None}
        if not flag.active:
            return {"schema": SCHEMA, "enabled": False, "reason": "inactive",
                    "flag": flag_key, "variant": None}
        bucket = _bucket(self.salt, flag_key, distinct_id, "rollout")
        if bucket >= flag.rollout_percentage:
            return {"schema": SCHEMA, "enabled": False, "reason": "not_in_rollout",
                    "flag": flag_key, "bucket": round(bucket, 6), "variant": None}
        variant = None
        if flag.variants:
            vb = _bucket(self.salt, flag_key, distinct_id, "variant")
            cursor = 0.0
            for item in flag.variants:
                cursor += item.rollout_percentage
                if vb < cursor:
                    variant = item.key
                    break
        result = {"schema": SCHEMA, "enabled": True, "reason": "match",
                  "flag": flag_key, "bucket": round(bucket, 6),
                  "variant": variant}
        self.exposures.append(Exposure(flag_key, variant, distinct_id, bucket))
        return result

    def exposures_for(self, flag_key: str) -> list[dict[str, Any]]:
        return [e.__dict__ for e in self.exposures if e.flag == flag_key]
