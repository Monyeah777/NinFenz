"""LLMWiki 编译器（WP-10，`nf wiki build/check/get/search/related/context`）。

纪律（WK-01…WK-08）：
- **Wiki 是投影，不是第二真源**：页面只由真源（registry/03 管线/05 资产/community DOMAIN_SPEC/
  protocol schemas）编译；页面只存 summary + spec_ref + digest + relations，**不复制正文**；
- 全输出确定性（同输入逐字节一致）；`check` 用真源现算 digest 比对 → 源变即陈旧；
- 覆盖：每类真源至少一页；ID 唯一；relations 目标可解析；
- 三入口：CLI（本模块）、`wiki/llms.txt`、`wiki/mcp.json`（MCP 工具清单）；
- 生成物 `wiki/` 禁手改：`nf wiki check` 依据真源 digest 判 stale，改生成物即红。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 实现分片：原模块逻辑在私有子包 _wiki_compiler/，本门面按原模块面显式再导出（API 不变）。
from core._wiki_compiler._part1 import (
    DIR_REL,
    GRAPH_REL,
    GUIDE,
    INDEX_REL,
    LLMS_REL,
    MCP_REL,
    PAGE_SCHEMA_REL,
    PAGES_REL,
    REGISTRY_REL,
    SCHEMA_GRAPH,
    SCHEMA_INDEX,
    SCHEMA_MCP,
    SCHEMA_PAGES,
    TYPES,
    PageOptions,
    _asset_entries,
    _dir_digest,
    _domain_specs,
    _llms_text,
    _mcp_doc,
    _page,
    _pipeline_files,
    _read_bytes,
    _registry_modules,
    _schema_files,
    _sha,
    build,
    render,
)
from core._wiki_compiler._part2 import (
    _committed,
    check,
    context,
    get,
    related,
    search,
    stale_issues,
    validate_pages,
    write,
)
