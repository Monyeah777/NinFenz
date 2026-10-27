"""MCP 可缓存结果的服务端边界。"""
from __future__ import annotations

from typing import Any

MAX_CACHE_TTL_MS = 3_600_000


def cacheable(payload: dict, ttl_ms: int, cache_scope: str) -> dict[str, Any]:
    """补齐规范保留键；payload 不得覆盖缓存上限或缓存边界。"""
    if isinstance(ttl_ms, bool) or not isinstance(ttl_ms, int):
        raise TypeError("ttlMs 必须是整数")
    if cache_scope not in ("public", "private"):
        raise ValueError("cacheScope 必须是 public 或 private")
    out: dict[str, Any] = {}
    out.update(payload)
    out["resultType"] = "complete"
    out["ttlMs"] = min(max(0, ttl_ms), MAX_CACHE_TTL_MS)
    out["cacheScope"] = cache_scope
    return out
