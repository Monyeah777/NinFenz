#!/usr/bin/env python3
"""职能坐标（ADR-0006）—— 与抽象阶梯轴**正交**的第二轴：核内逐件、核外按规则。

**这是什么**：阶梯轴回答「它在哪一阶」（契约/资产/引擎/出口），本轴回答「它在工坊里干什么」。
实测「阶梯轴对核内零分辨力」：`desktop/src/core` 的 .py **全部**落「引擎」一阶——
所以职能轴不是重复登记，而是**新增信息**。

**七个职能**（封闭集，见 `protocol/LAYERS.json` 的 `roles.vocabulary`）：
`floor`（身份/寻址/注册，两核共用地板）· `prod`（件·装配律·派生）· `verify`（声明·见证·判据）·
`projection`（真源→渲染→落点）· `support`（基础设施）· `app`（实例与内容）· `entry`（入口面）。

**坐标可推导**（ADR-0006 决策 2）：角色由**规则**批量命中（`roles.rules`，先命中先算），
核内件再由**结构信号**逐件收窄；**职能句**一律取自该件**自述**（.py 取模块 docstring 首句）——
即「职能句必须可从证据推导」，不是手填。

**三条可判定性**（ADR-0006 决策 3；并入 check27 的阶梯面，**不新增 check 序号**，遵 ADR-0002）：
1. **全覆盖**：仓库件（`repo_face.walk_repo_paths`）每一件至少命中一个坐标；核内件（floor/prod/verify）
   不得落到兜底规则；核内 `.py` 必须有自述（无自述 = FAIL，因为职能句无处可推）。
2. **规则不漂**：每条规则至少命中 1 件；投影件（`protocol/role_coordinates.json`）与实时重算一致。
3. **核内一致**：`verify` 是**只读判据**——自带写盘入口须在 `roles.write_exceptions` 逐条登记理由
   （未登记的写入口 = FAIL；例外表只许缩小，是待清的投影成本）。

性能纪律：文件面**只枚举一次**（`repo_face.walk_repo_paths` 内含 git 子进程），规则匹配在内存里做。

纪律：纯标准库；只读（唯显式 `write()` 落投影）；同输入同输出。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import atomic_write, json_doc, repo_face

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._role_model import _part1 as _live_part1

# 实现分片：原模块逻辑在私有子包 _role_model/，本门面按原模块面显式再导出（API 不变）。
from core._role_model._part1 import (
    _SCAN_DEF,
    _VERB,
    _WRITE_NAMES,
    DECL_REL,
    KERNEL_ROLES,
    PROJECTION_REL,
    ROLES,
    SCHEMA,
    _glob_re,
    _leading_docstring,
    _projection_impl,
    _rule_hits,
    _self_line_uncached,
    _signal_role,
    _signal_role_uncached,
    _text_of,
    _text_scope,
    coordinate,
    files_of,
    load,
    projection,
    self_line,
    writes_disk,
)
from core._role_model._part2 import (
    _coverage_issues,
    _kernel_issues,
    _projection_drift,
    _scan_impl,
    _vocab_issues,
    _write_channel_issues,
    scan,
    write,
)

_install_live_facade(__name__, {
    "_SELF_MEMO": _live_part1,
    "_SIGNAL_MEMO": _live_part1,
    "_TEXT_MEMO": _live_part1,
})
