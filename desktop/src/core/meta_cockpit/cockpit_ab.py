"""Offline paired blind A/B harness for recorded cockpit outputs."""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 实现分片：原模块逻辑在私有子包 _cockpit_ab/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._cockpit_ab._part1 import (
    BALLOT_SCHEMA,
    BALLOT_VALIDATOR,
    BASE,
    RESULT_SCHEMA,
    RESULT_VALIDATOR,
    SCHEMA,
    VALIDATOR,
    AnalyzeOptions,
    PreregisterOptions,
    _binomial_tail,
    _canonical,
    _mapping,
    _pair_key,
    _prompt_set_digest,
    _sign_test_p,
    _wilson,
    build_blind_packets,
    digest,
    power_analysis,
    preregister,
    validate_experiment,
)
from core.meta_cockpit._cockpit_ab._part2 import analyze

from . import json_asset, secret_guard
from . import schema_compat as jsonschema
