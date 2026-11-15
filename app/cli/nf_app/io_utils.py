"""UTF-8 stdio / 原子写 / 严格读。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .canonical import JsonParseError, canonical_bytes, loads_strict, sha256_hex
from .errors import AppError


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def read_bytes(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except FileNotFoundError as exc:
        raise AppError("NF-E-004", message=f"文件不存在: {path}", fix="检查路径拼写/工作目录") from exc
    except IsADirectoryError as exc:
        raise AppError("NF-E-004", message=f"是目录而非文件: {path}", fix="给出具体文件路径") from exc
    except OSError as exc:
        raise AppError("NF-E-004", message=f"读取失败: {path}: {exc}", fix="检查路径与权限") from exc


def read_text(path: Path) -> str:
    data = read_bytes(path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(
            "NF-E-004",
            message=f"文件不是 UTF-8: {path}",
            fix="转成 UTF-8（无 BOM）后重试",
        ) from exc


def read_json(path: Path) -> Any:
    data = read_bytes(path)
    try:
        return loads_strict(data)
    except JsonParseError as exc:
        raise AppError(
            "NF-E-004",
            message=f"输入 JSON 解析失败: {path}: {exc}",
            fix="检查 JSON 语法；nf-canonical/1 只允许整数（禁浮点/NaN）且禁重复键",
        ) from exc


def sha256_file(path: Path) -> str:
    return sha256_hex(read_bytes(path))


def ensure_dir(path: Path) -> Path:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError("NF-E-004", message=f"创建目录失败: {path}: {exc}", fix="检查路径与权限") from exc
    return Path(path)


def write_bytes_atomic(path: Path, data: bytes) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=".nf-tmp-", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise AppError("NF-E-004", message=f"写入失败: {path}: {exc}", fix="检查路径与权限") from exc
    return path


def json_bytes(obj: Any, *, canonical: bool = True) -> bytes:
    """canonical=True：nf-canonical/1 字节（无尾换行）；False：人读缩进 JSON。"""
    if canonical:
        return canonical_bytes(obj)
    import json

    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json_atomic(path: Path, obj: Any, *, canonical: bool = True) -> Path:
    return write_bytes_atomic(path, json_bytes(obj, canonical=canonical))


def rel_posix(target: Path, base: Path) -> str:
    """产物引用用相对 POSIX 路径（禁绝对路径/.. 越界）。"""
    target = Path(target).resolve()
    base = Path(base).resolve()
    try:
        rel = target.relative_to(base)
    except ValueError:
        try:
            rel = Path(os.path.relpath(target, base))
        except ValueError as exc:
            raise AppError("NF-E-003", message=f"路径不在项目目录内: {target}", fix="把产物放进项目目录") from exc
        if str(rel).split(os.sep)[0] == "..":
            raise AppError(
                "NF-E-003",
                message=f"路径在项目目录之外（引用必须是相对 POSIX 路径）: {target}",
                fix="把产物移进项目目录，或用 --out 指定项目内目录",
            )
    return rel.as_posix()
