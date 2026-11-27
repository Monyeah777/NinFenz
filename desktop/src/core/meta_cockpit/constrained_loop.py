"""约束选择完整回合循环：候选 → 选择 → 执行 → 校准 → 重编译。"""

# ruff: noqa: F401 - 门面按原模块面重新导出（实现在 _constrained_loop/ 私有子包）。
from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass
from pathlib import Path

# 实现分片：原模块逻辑在私有子包 _constrained_loop/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._constrained_loop._base import (
    SECRET_PATTERNS,
    ContextualResponse,
    LoopOptions,
    complete,
    completion_gaps,
    contextual_policy,
    first_policy,
    safe_error,
    stop,
)
from core.meta_cockpit._constrained_loop._run import run

from . import calibration_ledger as cl
from . import calibration_store as cs
from . import cognitive_cockpit as cc
from . import coherence, context_pack, method_memory, secret_guard, task_profile
from . import constrained_choice as cons
from . import live_selector as ls
from . import session_journal as journal
