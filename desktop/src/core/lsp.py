"""NF LSP 服务器（编辑器接管面：诊断 / 补全 / 悬停 / 跳定义 / 大纲 / quickfix）。

内部差距实证（2026-10-07 审计）：本模块此前只有「full-sync 诊断 + quickfix」——
- 诊断位置恒为 `(0,0)`（autofix 规则）或零宽（正文 lint），**编辑器无法定位到正文**；
- 没有 didClose（长驻会话状态泄漏、旧诊断不清）；initialize 忽略 rootUri / capabilities；
- 没有 NF 领域智能（模块 id / 资产键 / 事件名 / 层位 id / 管线 id 的补全、悬停、跳定义）；
- 未 shutdown 直接 exit 也回 0（LSP 规范要求 1）；
- 编辑器装配面为零：没有任何生成好的客户端配置，使用者要照文档手抄。
于是「IDE 集成」在门禁里只剩一个布尔（check33 旧第 5 面只断言 codeActionProvider 为真）。

本版把编辑器面做成**可机检的协议行为**：
1. 传输：LSP 标准 `Content-Length` 分帧（与 MCP 的换行分隔不同，互不混用），坏帧不杀会话；
2. 能力：full-sync（openClose + save）、诊断、quickfix、补全、悬停、跳定义、文档大纲、
   工作区符号；`positionEncoding` 按客户端能力协商（默认 utf-16，位置一律按 UTF-16 码元折算）；
3. 领域智能：符号表单一真相来自 `core/nf_language`（不另造标准）；
4. 装配：`render_client_config()` 生成 Neovim / Emacs(eglot) / Helix 的现成配置
   （`nf lsp --print-config <editor>`）——**只覆盖内置 LSP 客户端的编辑器**；VS Code 类
   需要扩展宿主，本仓无编辑器可装载验证，按诚实标注留给使用者，不假称已适配（见 docs/lsp.md）。

纪律：只读分析 + 只在客户端**显式请求** codeAction 时给编辑；本模块不自行写盘。

**包含性（2026-10-10 审计 X2，P1）**：客户端 uri 与 initialize.rootUri 都是不可信输入。
磁盘读取一律先过 realpath 包含性（边界 = 会话根），根外一律返回空；rootUri 只有「在场目录
且落在启动根内」才被采纳。同仓库 MCP 面早有这道纪律（mcp_runtime._tool_pipeline_read），
LSP 面此前漏了——一个 uri 就能读出工作区外任意文件的**全文**（CWE-22 → CWE-200）。
"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO, Tuple
from urllib.parse import quote, unquote, urlparse

from core import autofix, nf_language

# 活状态/可 patch 面：读取与赋值一律转发到真实持有模块（实现见 core/_facades）。
from core._facades import install as _install_live_facade
from core._lsp import _part2 as _live_part2

# 实现分片：原模块逻辑在私有子包 _lsp/，本门面按原模块面显式再导出（API 不变）。
from core._lsp._part1 import (
                             _FENCE,
                             _REQUIRED_CAPS,
                             _URI_SAFE,
                             COMPLETION_KIND,
                             M_CODE_ACTION,
                             M_COMPLETION,
                             M_DEFINITION,
                             M_DID_CHANGE,
                             M_DID_CLOSE,
                             M_DID_OPEN,
                             M_DID_SAVE,
                             M_DOCUMENT_SYMBOL,
                             M_EXIT,
                             M_FOLDING_RANGE,
                             M_HOVER,
                             M_INITIALIZE,
                             M_INITIALIZED,
                             M_REFERENCES,
                             M_SHUTDOWN,
                             M_WORKSPACE_SYMBOL,
                             METHOD_NOT_FOUND,
                             SERVER_NAME,
                             SERVER_VERSION,
                             _within_root,
                             path_to_uri,
                             uri_to_path,
)
from core._lsp._part2 import _REQUESTS, _error
from core._lsp._part3 import (
                             LspServer,
                             _check_capabilities,
                             _check_intelligence,
                             _check_lifecycle,
                             _client_config_issues,
                             _folding_issues,
                             _references_issues,
)
from core._lsp._part4 import check, scan
from core.lsp_client import CLIENT_EDITORS, render_client_config
from core.lsp_doc import (  # noqa: E402
                             diagnose,
                             folding_ranges,
                             outline,
                             prefix_before,
                             text_edits,
                             u16_col,
                             word_span,
)

#: 传输分帧（线格式）独立成 core/lsp_framing.py；这里只做转口，调用方口径不变
from core.lsp_framing import BAD_FRAME, read_message, write_message  # noqa: E402
from core.lsp_params import (
                             INVALID_PARAMS,
                             INVALID_REQUEST,
                             SERVER_NOT_INITIALIZED,
                             advise_request,
                             did_change_text,
                             did_open_payload,
                             lifecycle_problem,
)

_install_live_facade(__name__, {
    "INDEX_TTL_S": _live_part2,
})
