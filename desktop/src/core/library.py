"""NF 云端图书馆（library/）机器面：frontmatter 真源 → INDEX/ALIAS 投影 + 检索索引。

机制借鉴 OKF v0.2（Google Open Knowledge Format，markdown + YAML frontmatter，纯文本可读、
可 diff、可移植），按 NF 现有纪律收窄落地：

- **单一真相源（I5）**：条目文件头 frontmatter = 真源；`INDEX.md` / `ALIAS.md` 一律由本模块
  重生成（投影），不再人机混写。
- **OKF 三族字段**：provenance(`sources`) / trust(`generated`,`verified`,`attestation`) /
  lifecycle(`status`,`stale_after`)——把「从哪来 / 谁验过 / 还作数吗」变成一等字段。
- **未知键保留**：消费方不得因未识别字段拒收（对齐 OKF 扩展规则）。

纪律：纯标准库（自实现 YAML 子集解析，不用第三方）；写盘只由 `write_projection` 一处发生。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 条目读取迁到叶子件（见 core/library_entries.py）；此处兼容转发，调用点零改动。
from core import atomic_write

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._library import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _library/，本门面按原模块面显式再导出（API 不变）。
from core._library._part1 import (
    _DATE,
    _ID,
    ALIAS_REL,
    BEGIN_INDEX,
    BEGIN_MIRROR,
    END_INDEX,
    END_MIRROR,
    INDEX_REL,
    MIRRORS,
    RECOMMENDED_KEYS,
    REQUIRED_KEYS,
    STATUSES,
    _cell,
    _replace_region,
    _rewrite_frontmatter,
    _tokens,
    build_index,
    check_projection,
    render_alias,
    render_index_block,
    render_mirror_block,
    search,
    write_projection,
)
from core._library._part2 import (
    AttestationOptions,
    set_attestation,
    set_status,
    to_manifest,
    verify,
)

# `parse_frontmatter` 是**对外转发面**（audit / decisions / handover / patterns /
# postmortem 与本仓测试都 `from core.library import parse_frontmatter`）：本文件里确实
# 没有调用点，删掉会破兼容（2026-10-01 实测：删后 test_library.TestFrontmatter 两例 ERROR）。
# `ENTRY_GLOB` / `read_entry` 同样是旧转发，但全仓**零消费者** ⇒ 2026-10-01 已删。
from core.library_entries import entries, parse_frontmatter

_install_live_facade(__name__, {
    "entry_digest": _live_part2,
})
