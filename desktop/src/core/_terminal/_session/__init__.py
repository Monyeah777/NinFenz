"""terminal · _session（自 terminal.py 拆出；只移动代码，行为/文案不变）。"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

# 实现分片：原模块逻辑在私有子包 同包 _session/，本门面按原模块面显式再导出（API 不变）。
from core._terminal._session._part1 import SessionOptions
from core._terminal._session._part2 import Session

from .._completion import complete, render_completions
from .._const import BLOCKED_IN_SHELL, YES_WORDS
from .._forms import build_argv, form_by_id, form_missing, form_pending, render_form, render_forms
from .._history import load_history
from .._parse import _strip_comment, did_you_mean, needs_confirm, parse
from .._render import menu, render_commands, render_map, render_search, zone_detail
from .._session_io import save_session_state
from .._tables import FORMS
from .._ui import resolve_color
