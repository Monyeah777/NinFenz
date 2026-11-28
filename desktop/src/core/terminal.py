#!/usr/bin/env python3
"""NF 终端（`nf shell`）——端壳退役后的人机交互入口（纯 stdlib · 确定性 · 可注入）。

定位（对齐 `docs/L3_FROZEN.md`「能力入口一律落 CLI」）：
桌面 GUI 端壳与打包线已于 2026-09-09 永久退役，公开面收敛为「协议 + core 库 + CLI」，
人机交互面随之真空。本模块补的**不是**第二套命令面，而是把**既有** CLI 命令面按能力菜单
组织成可交互会话：读一行 → 解析 → 闸门 → 分派 → 打印。命令真源仍是 `scripts/nf.py`
的 argparse 面——`ZONES` 的每条示例命令都由 verify check39 解析断言，菜单指向死命令即红。

三条硬约束（与仓库红线同源）：
1. **零第三方依赖**：只用 stdlib。刻意不用 curses（Windows 无该模块）与 PySide6 等
   GUI 工具包（PySide6 只服务 CCV3 卡面写入，与终端无关）。
2. **确定性**：同一输入两次运行逐字节一致——`nf shell --exec` 是回归面，也是 check39 的判据。
3. **安全闸门**：写入类命令默认拒跑，须显式确认（交互输入 yes，或调用方显式 `--yes`）。
   终端不替使用者拍板；`serve`（长驻服务）与 `shell`（递归会话）在会话内给指引而非执行。

分层：本模块只做「解析 / 菜单 / 渲染 / 闸门 / 会话状态机」，**不 import scripts/nf.py**——
执行由调用方以 `runner(argv) -> int` 注入，故 core 层保持零 CLI 反向依赖，单测可完全离线。
"""
from __future__ import annotations

from dataclasses import dataclass

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
from typing import Any

# 依赖面：实现在 _terminal 子包；本行履约原模块对 core 的 import 边（勿删）。
# 终端纪律：默认无色（NO_COLOR 一票否决），非 TTY 逐字节确定（硬契约）。
# 规范 JSON 编码单源：surface_digest 在 _terminal._surface 走 attest.canonical（审计 Z1）。
# 读点：会话状态落盘/读回在 _terminal._session_io，仍走 json_doc.loads / json_doc.load（N11）。
from core import atomic_write, attest, json_doc, storage

from ._terminal._baseline import (
    TERMINAL_BASELINE,
    _expect_hits,
    baseline_argv_issues,
    baseline_table,
    baseline_tmp_dir,
    portable_rows,
    render_baseline,
    run_baseline,
    writable_dir_probe,
)
from ._terminal._catalog import (
    families_for,
    families_without_zone,
    family_of,
    family_table,
    zone_by_key,
    zone_table,
    zones_of_family,
)
from ._terminal._completion import (
    _restore_msys_partial,
    complete,
    install_readline,
    readline_available,
    render_completions,
)
from ._terminal._const import (
    _RESET,
    _STYLES,
    _WIDE_RANGES,
    BASELINE_DEEP_MAX_MS,
    BASELINE_DEFAULT_MAX_MS,
    BASELINE_FORBIDDEN_FLAGS,
    BASELINE_TMP,
    BLOCKED_IN_SHELL,
    CONFIRM_FLAG_PAIRS,
    CONFIRM_FLAGS,
    CONFIRM_VERBS,
    PROMPT,
    QUIT_WORDS,
    SESSION_SCHEMA,
    SHELL_VERSION,
    SLASH_HELP,
    SLASH_WORDS,
    SURFACE_MODULE_HEAD,
    SURFACE_MODULE_PATH,
    SURFACE_SCHEMA,
    SURFACE_SOURCE,
    YES_WORDS,
    Intent,
)
from ._terminal._forms import (
    build_argv,
    form_action_dict,
    form_by_id,
    form_missing,
    form_pending,
    form_table,
    render_form,
    render_forms,
    zone_action_dicts,
)
from ._terminal._history import (
    append_history,
    default_history_path,
    load_history,
)
from ._terminal._parse import (
    _lev,
    _slash_intent,
    _strip_comment,
    _strip_nf,
    did_you_mean,
    example_resolves,
    needs_confirm,
    parse,
    search,
    split_args,
)
from ._terminal._render import (
    banner,
    menu,
    render_commands,
    render_map,
    render_search,
    zone_detail,
)
from ._terminal._script import (
    _statements,
    run_file,
    run_lines,
    run_script,
)
from ._terminal._session import Session, SessionOptions
from ._terminal._session_io import (
    load_session_state,
    save_session_state,
)
from ._terminal._session_run import RunOptions, run_session
from ._terminal._surface import (
    _surface_params,
    render_surface,
    render_surface_module,
    surface_digest,
    surface_module_text,
    surface_payload,
    surface_sync_issues,
)
from ._terminal._tables import (
    FAMILIES,
    FORM_EXEMPT,
    FORMS,
    ZONES,
)
from ._terminal._ui import (
    _row,
    char_width,
    clip,
    display_width,
    highlight,
    pad_to,
    resolve_color,
    style,
    term_width,
)


from ._terminal._selfcheck import (  # 门面 re-export：自检判据实现已拆到子包
    DeepCheckOptions,
    deep_check,
    self_check,
)
