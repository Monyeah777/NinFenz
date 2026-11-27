"""活体认知驾驶舱：每轮读 need → 组合 1-3 个原子 → 想一步 → 重新读 need。

无评分、无固定全程计划、无回执驱动。评分/审计属于外部质量门，不参与驾驶。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import copy
import re
from pathlib import Path

# 实现分片：原模块逻辑在私有子包 _cognitive_cockpit/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._cognitive_cockpit._part1 import (
    BUSINESS_TERMS,
    GAME_TERMS,
    REL_MAP,
    REQ_KEYS,
    TECH_TERMS,
    _enrich,
    _met,
    _payload,
    compose,
    infer_need,
    initial_state,
    parts_from,
    select_references,
)
from core.meta_cockpit._cognitive_cockpit._part2 import execute_cluster, think

from . import calibration_ledger as cal_ledger
from . import calibration_store as cal_store
from . import coherence, domain_sources, epistemic_agenda, method_memory, task_profile
from . import live_selector as ls
from . import meta_atom_runtime as atoms
from . import metacognitive_control as control
