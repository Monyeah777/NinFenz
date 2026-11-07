"""跨进程文件锁：Windows msvcrt / POSIX fcntl。"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path


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
    started = time.monotonic()
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                    break
                except OSError as exc:
                    if time.monotonic() - started >= timeout:
                        raise TimeoutError("lock timeout") from exc
                    time.sleep(0.01)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(  # type: ignore[attr-defined]
                        handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )  # type: ignore[attr-defined]
                    acquired = True
                    break
                except OSError as exc:
                    if time.monotonic() - started >= timeout:
                        raise TimeoutError("lock timeout") from exc
                    time.sleep(0.01)
        yield
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(  # type: ignore[attr-defined]
                    handle.fileno(), fcntl.LOCK_UN
                )  # type: ignore[attr-defined]
        handle.close()
