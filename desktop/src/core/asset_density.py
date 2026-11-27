"""45 W2 · 资产键语义密度体检（资产质量维机检）。

对 community 各包 assets 与 05 用户自定义资产文件做密度体检：
- 键发现 = 文件名令牌 ∪ 正文键声明（`KEY` / "KEY": / ## KEY，与 AI 通道资源面同口径）；
- 统计每文件 键数/字符数，标出「无键文件」（多为附机制/中文名件，合法——入 unkeyed 计数不 FAIL）；
- FAIL 面只留：文件空或不可读（真异常）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import conformance_scan as csc
from core import disk_cache

# 导入闭包指纹：由调用方算（持久层不再反向依赖解析层，见 2026-09-29 拆环）
from core import import_graph as _ig
from core._asset_density import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _asset_density/，本门面按原模块面显式再导出（API 不变）。
from core._asset_density._part1 import (
    _CENSUS_CACHE,
    _CENSUS_CACHE_MAX,
    _FILE_COUNT_CACHE,
    _FILE_COUNT_CACHE_MAX,
    _KEYS_OF_CACHE,
    _KEYS_OF_CACHE_MAX,
    _MATCHERS,
    _MATCHERS_MAX,
    ASSET_INPUTS,
    CORPUS_PATTERNS,
    MAX_ASSET_FILE_BYTES,
    MAX_KEY_CHARS,
    MAX_KEYS,
    _keys_of,
    _scan_impl,
    scan,
)
from core._asset_density._part2 import (
    _Matcher,
    _matcher,
    _thickness_impl,
    count_keys,
    count_keys_additive,
    thickness_scan,
    usage_scan,
)

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade

_install_live_facade(__name__, {
    "MAX_BLOB_TEXT": _live_part2,
    "MAX_MATCHER_NODES": _live_part2,
})
