"""双源知识架构门禁（权威分层 / 消化可追溯 / 查询有序 / 时效 / 可见性）。

真源两份：`protocol/knowledge_sources.json`（声明）与 `protocol/transform_log.json`（消化记录）。
机制借鉴（一句式）：编译时机按数据域选择——本地沉淀走写入时编译、外部变化走查询时检索。

判据（全部可证）：
- 词表：authority ∈ {contract, reference}、kind ∈ {local-compiled, external-retrieval}、
  visibility ∈ {public, internal, restricted}；id 唯一；locator 必须指向仓库内真实件（防纸面源）。
- 权威分层：reference 级**必须** `requires_source_label: true`（外部数据须标注来源、不得写死）；
  contract 级必须 `false` 且 kind=local-compiled。
- 时效：contract 级用 `stale_after` 策略；reference 级必须给 `ttl`（ttl_days>0）或 `no-cache`。
- 查询有序：`query_order` 必须是全部源 id 的一个排列，且**全部 contract 级排在全部 reference 级之前**。
- 消化可追溯：每条 transform 记录的 `from` 必须是已声明 reference 源、`to` 必须是仓库内真实件且
  digest 与记录一致；标 `promoted: true` 者必须齐三档证据 + 复核人/复核时间非空。

纪律：本模块只读声明与文件，不自造知识、不联网、零第三方依赖。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core import atomic_write, json_doc

# 实现分片：原模块逻辑在私有子包 _knowledge/，本门面按原模块面显式再导出（API 不变）。
from core._knowledge._part1 import (
    _DATED,
    _MODULE_ID,
    AUTHORITIES,
    DECL_REL,
    FRESH_CONTRACT,
    FRESH_REFERENCE,
    KINDS,
    LOG_REL,
    LOG_SCHEMA,
    REQUIRED_ENTRY,
    REQUIRED_SRC,
    SCHEMA,
    TIERS,
    TRIGGERS,
    USAGE_REL,
    USAGE_SCHEMA,
    VISIBILITIES,
    VISIBILITY_RANK,
    _auth,
    _module_ids,
    _read_json,
    load_decl,
    load_log,
    load_usage,
    reference_ids,
    resolve_order,
    scan,
    sha256_file,
    sources,
    verify_transform,
    visible_ids,
)
from core._knowledge._part2 import (
    harvest_frequency,
    lint,
    verify_reuse,
    verify_usage,
    write_log,
    write_usage,
)

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
