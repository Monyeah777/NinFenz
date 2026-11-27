"""仓库只读索引池（RepoIndex）：把 MCP 工具的「每次全仓扫描」收敛为一次懒构建 + O(1) 查询。

设计（2026-10-23）：

- **按 family 懒构建**：modules / pipelines / assets / library / patterns / registry / docs
  各自在第一次被用到时建立；`McpRuntime.__init__` 不再全量扫仓库。
- **O(1) 寻址**：id / stem / key → 条目的倒排表；同一 family 内不再每次 glob/read。
- **失效**：
  * 成员变更：family 的目录清单 stamp（只列目录、不读正文）每 `TTL` 秒复核一次；
  * 内容变更：每次取用条目时 `stat(mtime_ns,size)` 校验，命中变化即重建该 family；
  * 读取失败/文件消失：视为失效并重建。
- **只读**：本模块不写仓库、不起进程；所有读取都走 `Path.read_text`/`json_doc.load`。

边界：索引是**进程内**的；跨进程/守护的持久化由调用方决定（daemon 已有自己的常驻层）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import re
import time
import urllib.parse as _up
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core import json_doc
from core import paths as _paths

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._repo_index import _part1 as _live_part1

# 实现分片：原模块逻辑在私有子包 _repo_index/，本门面按原模块面显式再导出（API 不变）。
from core._repo_index._part1 import (
    _ASSET_TOKEN,
    _MODULE_TITLE,
    DEFAULT_TTL,
    _glob,
    _keys_of_file,
    _rel,
    _stat,
    md_title,
    read_text,
    safe_path,
)
from core._repo_index._part2 import _INDEXES, MAX_INDEXES, RepoIndex, clear, get

_install_live_facade(__name__, {
    "MAX_RESOURCE_BYTES": _live_part1,
})

__all__ = ["RepoIndex", "clear", "get", "md_title", "read_text", "safe_path"]
