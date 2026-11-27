"""world_model 契约扫描器（machine_contract.world_model 可选确定性抽象状态层）。

定位：把 JEPA/H-JEPA 对“预测未来表征、而非生成像素/词元”的机制，收窄成 NF
协议层可无歧义机检的确定性契约：

- abstract_state：有限状态变量 + 初始值，变量名/类型/来源显式声明；
- transition：finite-state 相位图，每个相位显式声明 next/guard/writes；
- invariants：抽象状态必须长期成立的硬约束（如 tick 单调、相位有限）。

边界：本模块校验契约结构与语义，不训练/不运行神经网络，不对 JEPA 与生成式
路线的优劣作任何经验断言；外部有效性只来自用户实测，不由本扫描器伪造。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 实现分片：原模块逻辑在私有子包 _world_model/，本门面按原模块面显式再导出（API 不变）。
from core._world_model._part1 import (
    ITEM_KINDS,
    KINDS,
    _abstract_parts,
    _check_finite_sequence,
    _check_initial,
    _check_initial_keys,
    _check_initial_values,
    _check_invariants,
    _check_phase,
    _check_reachability,
    _check_slot_value,
    _check_values,
    _check_variable,
    _get_slot,
    _matches,
    _nonempty,
    _phases,
    _reachable_from,
    _set_slot,
    _slot_parts,
    _transition_parts,
    _variables,
    load_slots,
)
from core._world_model._part2 import (
    WorldModelViolation,
    _check_check_item,
    _check_checks,
    _check_slot_registry,
    build_graph,
    initial_state,
    trace_digest,
    validate_contract,
)
from core._world_model._part3 import WorldModelRuntime, advance_phase, phase_sequence, scan

# 契约面（门面按原模块面再导出；实现分片见同目录 _world_model/ 私有子包）：
#   def validate_contract( / def advance_phase( / def trace_digest( / def scan(
# 运行器 8 方法（WorldModelRuntime，在 _world_model 分片里）：validate_state、advance、
#   replay、extract_state、validate_concrete、advance_concrete、replay_concrete，
#   以及 trace_digest / advance_phase / scan 的模块级入口。
