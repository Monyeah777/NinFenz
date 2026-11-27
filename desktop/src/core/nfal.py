"""NFA-L 中端/后端 · 符号面 + 静态检查 + 三值求值 + NFIR。

定位：声明层（YAML 围栏 + protocol/schema 的 JSON-Schema IDL）不变，本模块补命令层——
把 Pipeline.structure.flow[].condition 从自由字符串升为可静态检查、可执行、可复算的
guard 表达式（见 core.nf_expr）。

边缘全借（不新造第二份事实）：
- 世界状态符号 = protocol/world_slots.json 的 slots（登记全名 + kind）
- 事件符号   = protocol/event_registry.json 的 events
- token 面   = 模块 machine_contract 的 outputs + io_types（复用 core.pipelinerun 索引）
- 类型词表   = 01 第 7 节 io_types
- 判决三态   = core.decision_layer 的 pass/fail/abstain（abstain 永不折算 pass）
- 声明装载 / 形状校验 = core.conformance_scan / core.schema_lint（不重实现）

命令层是封闭小核：函数集见 FUNCS，无用户函数、无循环、无赋值、无 I/O。
纯标准库；只读无副作用（除 CLI 层的打印）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc

# 实现分片：原模块逻辑在私有子包 _nfal/，本门面按原模块面显式再导出（API 不变）。
from core._nfal._part1 import (
    _IMPLICIT_TRUE,
    _KIND_MAP,
    _LIT_TYPES,
    EXPR_PREFIX,
    FUNCS,
    NUMERIC,
    SCHEMA,
    UNKNOWN,
    SymbolTable,
    _accepts,
    _infer_arith,
    _infer_cmp,
    _io_kinds,
    _join,
    _kind_to_type,
    _load_events,
    _load_state_kinds,
    _load_tokens,
    _pos_of,
    _read_json,
    _ref_type,
    _rel_result,
    _require,
    _Unknown,
    diag,
)
from core._nfal._part2 import (
    _apply,
    _bool3,
    _div,
    _ed,
    _eval_arith,
    _eval_bin,
    _eval_call,
    _eval_cmp,
    _eval_cond,
    _eval_in,
    _eval_logic,
    _eval_un,
    _exc_diag,
    _infer,
    _infer_bin,
    _infer_call,
    _infer_coll,
    _infer_cond,
    _infer_un,
    _num,
    _walk,
    check_condition,
    check_expression,
    evaluate,
    infer_type,
)
from core._nfal._part3 import (
    _edge_row,
    _fence_pipeline,
    _layer_row,
    _module_refs,
    _verdict,
    build_ir,
    canonical,
    eval_guard,
    load_decl,
    verdict_of,
)
from core.nf_expr import LexError, ParseError, parse, strip_pos

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。

# 诊断码（实现在同目录 _nfal/ 私有子包）：E0201、E0202、E0301、E0302、E0304、E0310。
