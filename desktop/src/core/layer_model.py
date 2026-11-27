#!/usr/bin/env python3
"""抽象阶梯（protocol/LAYERS.json）—— 真源唯一 + 生成投影 + 语义判据。

**这是什么**：NF 的分层此前只有四套互不相干的「层」词汇（L0-L3 依赖治理编号 / P00-P80
管线层位 / mount_layers 模块挂载层 / 标准目录 layer），而「谁在动」（终端、AI）与
「被加工的物」（协议、资产）混在一根梯子上。本模块把阶梯收成**两轴 + 纵切**：

- **抽象轴四阶**：契约 → 资产 → 引擎 → 出口（越往下越稳定、越贵改）；
- **入口面**：只登记角色（人机 / AI 装配线 / MCP / 图书馆取件），永不作为真源；
- **验证纵切**：门禁与证据切过四阶，故不是「层」。

**分工**（遵 ADR-0003 断言表 kind 封闭集）：
- 形状类断言（声明件在场、生成区在场、无绝对路径）→ `protocol/assertions.json` 一行数据；
- 语义类判据（归属互斥 / 接口面子集 / 依赖向下 / 入口非真源 / 退役阶不被依赖 …）→ 留本模块代码。

**单一真源 + 生成投影**：`protocol/LAYERS.json` 是唯一真源；`docs/layers.md` 的生成区与
`nf layers` 的输出都是它的投影——生成区与实时渲染不一致即 FAIL（L10）。

本模块纯 stdlib、纯只读（除显式 `--write` 渲染），确定性（同输入同输出）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import ast
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write, json_doc
from core import conformance_scan as csc
from core import face_key as _fk
from core import role_model as _roles

# 实现分片：原模块逻辑在私有子包 _layer_model/，本门面按原模块面显式再导出（API 不变）。
from core._layer_model._part1 import (
    _CHECK_DEF,
    _ENTRY_IMPORT_CACHE,
    _ENTRY_IMPORT_CACHE_MAX,
    _ENTRY_IMPORT_RE,
    _JUDGE_ASSERTION,
    _JUDGE_CHECK,
    ASSERTIONS_REL,
    DECL_REL,
    DOC_REL,
    ENTRY_MODULE_NAMES,
    MARK_BEGIN,
    MARK_END,
    SCHEMA,
    VERIFY_REL,
    _arr,
    _derived_files,
    _entry_imports,
    _exists,
    _expand,
    _expand_many,
    _expand_one,
    _glob_root,
    _is_glob,
    _obj,
    _pattern_to_regex,
    _rule_l1,
    _rule_l1_assets,
    _rule_l1_files,
    _walk_files,
    load,
    tier_faces,
)
from core._layer_model._part2 import (
    _collect_judged_refs,
    _region_of,
    _rule_issues,
    _rule_l2,
    _rule_l3,
    _rule_l4,
    _rule_l5,
    _rule_l6,
    _rule_l7,
    _rule_l8,
    _rule_l9,
    _rule_l10,
    _table,
    _walk_cycle,
    _WalkContext,
    render_markdown,
)
from core._layer_model._part3 import (
    _READ_FACE,
    _scan_impl,
    face_fingerprint,
    patterns,
    scan,
    write_region,
)

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
