"""跨进程文件锁：Windows msvcrt / POSIX fcntl。"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path


def _try_lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(  # type: ignore[attr-defined]
            handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
        )  # type: ignore[attr-defined]


def _acquire_lock(handle, timeout: float) -> None:
    """非阻塞重试直到拿到独占锁；超时抛 TimeoutError。"""
    started = time.monotonic()
    while True:
        try:
            _try_lock(handle)
            return
        except OSError as exc:
            if time.monotonic() - started >= timeout:
                raise TimeoutError("lock timeout") from exc
            time.sleep(0.01)


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(  # type: ignore[attr-defined]
            handle.fileno(), fcntl.LOCK_UN
        )  # type: ignore[attr-defined]


@contextmanager
def locked(path: str | Path, timeout: float = 5.0):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    handle = open(lock_path, "a+b")  # noqa: SIM115 - lock lives across the yield
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    acquired = False
    try:
        _acquire_lock(handle, timeout)
        acquired = True
        yield
    finally:
        if acquired:
            _unlock(handle)
        handle.close()
