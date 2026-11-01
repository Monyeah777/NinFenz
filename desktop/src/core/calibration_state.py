"""标定态：样本不足只报 CALIBRATION 不判红（机制借鉴 stashbase evals/README.md:67-74）。

防「未观测的目标数字悄悄变成发布门禁」：样本不足时结论降级为标定态，
不参与硬门；样本齐了才进 gated。
"""
from __future__ import annotations

CALIBRATION = "calibration"
GATED = "gated"
UNJUDGED = "unjudged"


def state(samples: int, min_samples: int) -> str:
    if samples <= 0:
        return UNJUDGED
    return GATED if samples >= min_samples else CALIBRATION


def gate(st: str, verdict: str) -> str:
    """标定态/未判定下的 verdict 不参与硬门：fail 降级为 calibration（不判红）。"""
    if st in (CALIBRATION, UNJUDGED) and verdict == "fail":
        return CALIBRATION
    return verdict
