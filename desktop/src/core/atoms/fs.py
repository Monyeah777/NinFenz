"""文件系统原子：判在场 / 读正文 / 列举目录 / 遍历仓库件（只回数据，缺席即 None 或空集合）。"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from core import repo_face

from . import _wake


def file_exists(path: Path) -> bool:
    """该路径是否**是普通文件**；不在场 / 不可探测 → False。"""
    _wake("fs.file_exists")
    try:
        return Path(path).is_file()
    except OSError:
        return False


def dir_exists(path: Path) -> bool:
    """该路径是否**是目录**；不在场 / 不可探测 → False。"""
    _wake("fs.dir_exists")
    try:
        return Path(path).is_dir()
    except OSError:
        return False


def read_text(path: Path, encoding: str = "utf-8") -> str | None:
    """正文（保留原样换行）；不在场 / 不可读 / 解码失败 → None。"""
    _wake("fs.read_text")
    try:
        return Path(path).read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError):
        return None


def iter_entries(directory: Path) -> list[tuple[str, bool, int]]:
    """→ [(名称, 是否目录, 字节数)]，**按名称排序**（顺序稳定是判据可复现的前提）。

    目录不在场 → []。
    """
    _wake("fs.iter_entries")
    try:
        entries = sorted(Path(directory).iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    out: list[tuple[str, bool, int]] = []
    for entry in entries:
        try:
            is_dir = entry.is_dir()
            size = 0 if is_dir else entry.stat().st_size
        except OSError:
            is_dir, size = False, 0
        out.append((entry.name, is_dir, size))
    return out


def walk_files(root: Path, skip: Iterable[str] = ()) -> list[str]:
    """仓库件（跳过 VCS / 工具缓存 / .gitignore 覆盖面，另可按**目录名**补跳）。

    → 排序后的 posix 相对路径。

    扫描面判据只有一份：repo_face.walk_repo_paths（2026-10-03 审计：各扫描器自持排除表
    会让生成物以「第二份正文」身份进面）。本原子再做一件事——把 Path 归一成
    **posix 相对路径**，这样不同平台上的判据输入是同一串字节。
    """
    _wake("fs.walk_files")
    root_abs = Path(root).resolve()
    skip_names = {str(name) for name in skip}
    out: list[str] = []
    for path in repo_face.walk_repo_paths(str(root_abs)):
        try:
            rel = Path(path).resolve().relative_to(root_abs)
        except (OSError, ValueError):
            continue
        if skip_names and any(part in skip_names for part in rel.parts[:-1]):
            continue
        out.append(rel.as_posix())
    return sorted(out)
