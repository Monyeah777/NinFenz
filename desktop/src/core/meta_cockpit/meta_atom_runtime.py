"""元认知原子执行器：33 原子的确定性执行与节点轨迹。

- SPECS：每个原子的必需输入、输出键、输出类型；
- EXECUTORS：33 个原子执行器；元原子实现真实逻辑，内容原子适配现有指标；
- execute_node：按节点 atoms 顺序执行，任一失败即 fail-closed。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

# 实现分片：原模块逻辑在私有子包 _meta_atom_runtime/，本门面按原模块面显式再导出（API 不变）。
from core.meta_cockpit._meta_atom_runtime._part1 import (
    SPECS,
    _c_allocate,
    _c_select,
    _c_sequence,
    _c_switch,
    _digest,
    _e_adjudicate,
    _e_audit,
    _e_benchmark,
    _e_falsify,
    _e_verify,
    _fail,
    _i_cluster,
    _i_compose,
    _i_hierarchy,
    _i_merge,
    _i_reconcile,
    _k_abstract,
    _k_classify,
    _k_define,
    _k_instantiate,
    _k_partition,
    _k_quantify,
    _k_relate,
    _k_represent,
    _m_check,
    _m_compare,
    _m_estimate,
    _m_observe,
    _m_trace,
    _target,
)
from core.meta_cockpit._meta_atom_runtime._part2 import (
    EXECUTORS,
    _c_stop,
    _e_calibrate,
    _i_transfer,
    _k_criterion,
    _k_standard,
    _m_detect,
    execute_atom,
    execute_node,
)
