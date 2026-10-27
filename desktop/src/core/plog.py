"""v2.8.0 波C D4：可观测性 —— logging 级别体系（41 规划 D 组杂务）。

规则：
- 库/服务诊断走 logging（默认 INFO，级别可调），handler 绑定 **stderr**——
  绝不污染 stdout（MCP stdio 协议面只写 JSON-RPC；CLI 用户面输出保持）。
- 库层不自造 print 诊断；既有 CLI 用户面 print（结果/产物路径）为输出协议，保留。

用法：from core import plog; log = plog.get_logger(__name__)
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from typing import Any

_CONFIGURED = False
_SECRET = re.compile(
    r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._~+/=-]{16,})"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f\u2028\u2029\u0085]")


def sanitize(value: Any, limit: int = 2048) -> str:
    """把不可信诊断值压成单行，并遮蔽常见凭据形态。"""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    text = _CONTROL.sub(lambda match: f"\\u{ord(match.group(0)):04x}", text)
    text = _SECRET.sub("[REDACTED]", text)
    return text[:max(0, int(limit))]


def security_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """记录一条单行安全事件；字段值一律转义并遮蔽凭据形态。"""
    payload = {"event": sanitize(event, 128)}
    payload.update({sanitize(key, 64): sanitize(value) for key, value in fields.items()})
    logger.warning(json.dumps(payload, ensure_ascii=True, sort_keys=True,
                              separators=(",", ":")))


def get_logger(name: str, level: int = logging.INFO) -> "logging.Logger":
    """取模块 logger；首次调用自动初始化 stderr handler（幂等）。"""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.Formatter.converter = time.gmtime
        logging.basicConfig(
            level=level,
            format="%(asctime)sZ %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
            stream=sys.stderr,
        )
        _CONFIGURED = True
    return logging.getLogger(name)
