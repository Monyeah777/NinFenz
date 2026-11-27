"""mcp_runtime · _runtime（自 mcp_runtime.py 拆出；只移动代码，行为/文案不变）。"""

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用），实现在私有子包。
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, TextIO

from core import json_doc, repo_index, trust_boundary

# 实现分片：原模块逻辑在私有子包 同包 _runtime/，本门面按原模块面显式再导出（API 不变）。
from core._mcp._runtime._part2 import McpRuntime

from .._const import (
    _DECODE_ERROR,
    _NOT_IMPLEMENTED,
    _TOO_LONG,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    LEGACY_PROTOCOL_VERSION,
    MAX_MESSAGE_BYTES,
    MAX_URI_CHARS,
    META_PROTOCOL_VERSION,
    META_SERVER_INFO,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    SUPPORTED_VERSIONS,
    UNSUPPORTED_PROTOCOL_VERSION,
)
from .._tool_defs import PROMPT_DEFS, TOOL_DEFS
from .._tools import TOOL_ALIASES, TOOL_HANDLERS, _prompt_assemble_guide
from .._uris import (
    UnknownUriError,
    _discover_instructions,
    _extra_params_issue,
    _repo_resource_templates,
    _repo_root,
    _repo_uri_source,
    _sources_of,
    _texts_of,
    _trust_note,
    _uri_escaped_alias,
)
from .._wire import _echoable_id, _err, _err_at, _iter_lines, _valid_request_id, _write_response
