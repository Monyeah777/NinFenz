"""43 A1 —— 协议层 IDL 校验器（自实现 JSON-schema 子集 + 全量件扫描）。

零第三方 JSON-schema 实现红线：本模块自实现子集校验（type/required/
properties/propertyNames/enum/pattern/minLength/minItems/maxItems/minimum
+ additionalProperties），不引 jsonschema。YAML 解析复用仓库既有 PyYAML
依赖（verify check16 已用）。

扫描对象（见 protocol/README.md）：
- contract  模块头 machine_contract（04_模块库 + community/*/modules）
- module    registry.json modules[]（02 §2 投影）
- pipeline  管线声明 Pipeline（03_管线库 + community/*/pipelines）
- protocol  community/*/protocol.yaml（01 §6.1）
- asset     05_资产库/provenance.json assets[]（S2 台账）

用法：schema_lint.scan('.') -> (issues: list[str], stats: dict)
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core import conformance_scan as _csc  # 统一 YAML 加载器 / 围栏解析缓存真源
from core import json_doc

# enum/const 的值相等口径复用叶子件 json_schema.json_equal（唯一实现）——2026-10-10 审计 Y4：
# 此前 enum 只写在 string 分支里，{type: boolean, enum: [true]} 对 False 静默放行，而
# json_schema 会拒；同一语义两套校验器宽窄分叉，且分叉点落在「放过去」的那一侧。
from core import json_schema as _js  # noqa: E402 - 叶子件（不 import 任何 core 模块），无环

# 实现分片：原模块逻辑在私有子包 _schema_lint/，本门面按原模块面显式再导出（API 不变）。
from core._schema_lint._part1 import (
    _DOC_LINT_CACHE,
    _DOC_LINT_CACHE_MAX,
    _PATH_PLACEHOLDER,
    DIALECT,
    LINT_INPUTS,
    MAX_DEPTH,
    SCHEMA_DIR,
    SUBSET_ALLOWED_KEYS,
    _face_paths,
    _fence_yaml,
    _lint_doc_cached,
    _read_json,
    _schema_fp,
    check_schema_files,
    discover,
    load_schema,
    subset_key_violations,
    subset_validate,
)
from core._schema_lint._part2 import _lint_obj_cached, _scan_impl, scan

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
