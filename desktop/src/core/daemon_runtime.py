"""Daemon lifecycle policy: security events, lifetime, and log placement."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import plog, security_audit


def security_event(event: str, **fields: Any) -> None:
    payload = plog.security_event(
        plog.get_logger(__name__), event, actor="local-client", **fields
    )
    security_audit.record(payload)


def lifetime_expired(started: float, now: float, max_lifetime: float) -> bool:
    return max_lifetime > 0 and (now - started) >= max_lifetime


def log_path() -> Path:
    """Stable owner-only daemon stderr location."""
    from core import storage

    return Path(storage.default_home()) / "daemon.log"


def configure_watcher(root: Path, enabled: bool, install) -> Any:
    """Start the optional directory watcher, falling back without stale cache state."""
    if not enabled:
        return None
    from core import watch as watch_module

    watcher = watch_module.DirWatcher(root)
    if watcher.start():
        install(watcher)
        return watcher
    install(None)
    print(
        "目录监听不可用（平台未实现或打开失败）→ 不启用响应缓存，行为与常规守护一致",
        file=sys.stderr,
    )
    return None
