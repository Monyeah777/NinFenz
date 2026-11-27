"""内容寻址的**持久**缓存：把「内容的纯函数」结果移出进程生命周期。

用途：执行层里最贵的几笔账（引用度普查、产出面逐件校验、一致性分级扫描…）都是**输入内容的
纯函数**，但每开一个新进程就要重付一遍。把它们按内容寻址落到盘上，新进程直接取回。

键 = `sha256(标签 | 代码面内容 | 运行时标签 | 调用方给的各段键)`

- **代码面内容**（`desktop/src/**/*.py` + `scripts/**/*`，实测 157 件 / 41 ms）：把「算这段的
  函数本身」也放进键里，于是 **改了算法必然换键**——不需要靠"记得手工 bump 版本标签"这种脆弱
  纪律（漏 bump 就等于悄悄拿旧算法的结果当新结果）。
- **运行时标签**：Python 版本 / 平台 / PyYAML 是否在场——软依赖的有无会改变结果。
- **调用方给的各段键**：各自的输入面内容指纹（例如产出面的 `INDEX_INPUTS`）。

落点（C1，2026-10-22）：**默认用户级、按被审仓库分段**——
`<用户缓存>/ninfenz/<repo-hash>/<tag>/<key>.json`（Windows 用 `%LOCALAPPDATA%`，
其余 `$XDG_CACHE_HOME`/`~/.cache`）。`NF_CACHE_DIR` 可显式指定；显式 `NARRATIVE_FORGE_HOME`
（测试/便携隔离）仍落 `<NF_HOME>/cache`。用户缓存不可写时**回退仓内 `.nf-cache/` 并 WARN**，
且回退目录必须带 `.nf-cache-owner` 标记（预置的伪造缓存目录无标记 ⇒ 拒绝收养/拒读）。

纪律（fail-closed）：
1. 读回必须**校验**（调用方给 `validate`）：结构不对 / 键集不符 / 半截 JSON → 一律当没命中；
2. 一切 IO **尽力而为**：写不进、读不到都静默回落重算，绝不影响命令结果；
3. `NF_NO_DISK_CACHE=1` 整体关闭（读写皆废）；
4. 每个标签只留最近 `KEEP` 份（按 mtime 裁剪），缓存不得无界增长。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core import json_doc

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade

from ._disk_cache import _part1 as _live_part1
from ._disk_cache import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _disk_cache/，本门面按原模块面显式再导出（API 不变）。
from ._disk_cache._part1 import (
    _CODE_FP,
    _KEEP,
    _PRUNE_COUNT,
    _ROOT,
    CODE_FACE,
    ENFORCE_EVERY,
    ENV_DIR,
    ENV_MAX_TOTAL,
    ENV_OFF,
    KEEP,
    MARKER,
    MAX_TOTAL_DEFAULT,
    PRUNE_EVERY_BIG,
    PRUNE_EVERY_SMALL,
    _adopt_fallback,
    _probe_writable,
    _repo_tag,
    _root_key,
    _user_cache_base,
    canonical,
    key,
    max_total,
    runtime_tag,
)
from ._disk_cache._part2 import (
    _CORE_DIR,
    _path,
    _reset_root_state,
    _resolve_root,
    count_files,
    defer_begin,
    defer_drop,
    defer_flush,
    deferring,
    dir_for,
    enabled,
    enforce_bounds,
    reset_code_fingerprint,
    store,
    store_failures,
)

_install_live_facade(__name__, {
    "_RUNTIME": _live_part1,
    "code_fingerprint": _live_part1,
    "LAST_STORE_ERROR": _live_part2,
    "STORE_FAILURES": _live_part2,
    "_DEFER": _live_part2,
    "_DISABLED": _live_part2,
    "_STORE_TICKS": _live_part2,
    "load": _live_part2,
    "prune": _live_part2,
    "root_dir": _live_part2,
})

# 读点：契约 JSON 解析一律走 core.json_doc.loads / core.json_doc.load（N11）；实现分片见同目录私有子包。
