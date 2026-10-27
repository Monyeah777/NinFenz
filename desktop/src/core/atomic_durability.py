"""原子替换后的平台耐久性与权限边界。"""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path


def replace(tmp: str, path: Path, attempts: int = 10, backoff: float = 0.05) -> None:
    """`os.replace` 后 fsync 父目录；Windows 替换占用按短退避重试。"""
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            fsync_directory(path.parent)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(backoff)


def fsync_directory(path: Path) -> None:
    """持久化目录项；Windows 无对应稳定语义，显式跳过。"""
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def existing_mode(path: Path) -> int | None:
    """返回待替换普通文件的权限位；新文件继续使用 `mkstemp` 的 0600。"""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:  # 目标尚不存在：新文件保留 mkstemp 的 0600
        return None
    return stat.S_IMODE(mode) if stat.S_ISREG(mode) else None


def preserve_mode(fd: int, path: Path) -> None:
    """关闭临时文件前恢复既有目标权限；非 POSIX 保持平台默认语义。"""
    mode = existing_mode(path)
    if os.name != "nt" and mode is not None:
        os.fchmod(fd, mode)
