"""PyO3 扩展（nf_pyengine）的进程内原语包装：sha256 / float_repr，含 stdlib 回退。

与 core.rust_engine（常驻 worker）**并行、分工不同**：

- `rust_engine` 管**面级**加速（stats / layers / receipts / conformance 整面走常驻 worker）；
- 本模块管**原语级**（单次 sha256 / float repr 的进程内调用，零子进程、零序列化往返）。

边界（诚实）：扩展（engine/rust/pyo3 → `nf_pyengine.pyd`）不在场时回退 stdlib
（`hashlib.sha256` / `repr`）——本模块永远可用，不把「装了 Rust 工具链」变成调用前提。
"""
from __future__ import annotations

import hashlib
from typing import Any, Optional

_engine: Optional[Any] = None
_loaded = False


def _load() -> Optional[Any]:
    global _engine, _loaded
    if _loaded:
        return _engine
    _loaded = True
    try:
        import nf_pyengine as m  # type: ignore[import-not-found]
    except ImportError:
        _engine = None
    else:
        _engine = m
    return _engine


def sha256(data: bytes) -> bytes:
    """与 `hashlib.sha256(data).digest()` 逐字节一致；扩展在场则走 Rust。"""
    m = _load()
    if m is not None:
        return bytes(m.sha256(data))
    return hashlib.sha256(data).digest()


def float_repr(x: float) -> str:
    """与 CPython `repr(float)` 逐字节一致；扩展在场则走 Rust。"""
    m = _load()
    if m is not None:
        return str(m.float_repr(x))
    return repr(x)


__all__ = ["float_repr", "sha256"]
