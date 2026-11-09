"""Bounded daemon transport inputs and local-socket hardening."""
from __future__ import annotations

import os
import socket

MAX_REQUEST_BYTES = 1 << 20
MAX_RESPONSE_BYTES = 16 << 20
MAX_ARGV_CHARS = 8192
MAX_ARGV_TOTAL = 65536
MAX_CWD_CHARS = 32768


def configure_server_socket(sock: socket.socket) -> None:
    """Windows uses exclusive binding; elsewhere reuse only after close."""
    if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    elif os.name != "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def check_argv_size(argv) -> None:
    """Reject request amplification before the CLI sees untrusted arguments."""
    if not isinstance(argv, list):
        return
    for arg in argv:
        if isinstance(arg, str) and len(arg) > MAX_ARGV_CHARS:
            raise ValueError(
                f"单个参数超过上限 {MAX_ARGV_CHARS} 字符"
                "（修复指引：正文/长文本先落盘，改传路径）"
            )
    total = sum(len(arg) for arg in argv if isinstance(arg, str))
    if total > MAX_ARGV_TOTAL:
        raise ValueError(
            f"参数合计超过上限 {MAX_ARGV_TOTAL} 字符"
            "（修复指引：减少参数，或改传文件路径）"
        )
