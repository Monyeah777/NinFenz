"""摘要原子：字节 / 文件 / 目录树 → sha256 十六进制串（只回摘要，**不比对**）。"""
from __future__ import annotations

import functools
import hashlib
from collections.abc import Iterable
from pathlib import Path

from core.atoms import fs

from . import _wake


def sha256_bytes(data: bytes) -> str:
    """字节的 sha256（小写十六进制）。"""
    _wake("hash.sha256_bytes")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    """文件的 sha256；不在场 / 不可读 → None。

    用**分块**读取：门禁里被摘要的对象包含大件（payload / 报告），一次读进内存在实测里是
    峰值内存的主要来源，而字节数对哈希没有影响。
    """
    _wake("hash.sha256_file")
    digest = hashlib.sha256()
    try:
        with open(Path(path), "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


@functools.lru_cache(maxsize=256)
def _sha256_file_key(path: str, mtime_ns: int, size: int) -> str | None:
    """（path, mtime, size）→ 分块摘要；键含 mtime/size，内容变即换键。"""
    _ = (mtime_ns, size)
    return sha256_file(Path(path))


def sha256_file_cached(path: Path) -> str | None:
    """带 (mtime,size) 失效键的分块文件摘要；不可读 → None。"""
    _wake("hash.sha256_file_cached")
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    return _sha256_file_key(str(p.resolve()), int(st.st_mtime_ns), int(st.st_size))


def tree_digest(root: Path, skip: Iterable[str] = ()) -> str | None:
    """目录树的稳定摘要：按相对路径排序后，逐件混入 (路径, 文件 sha256)；根不在场 → None。

    形状固定为 posix 的相对路径（与 fs.walk_files 同口径），所以同一棵树在不同平台、
    不同文件系统遍历顺序下给出同一个摘要——这正是 CAP_DETERMINISTIC 需要的输入。
    """
    _wake("hash.tree_digest")
    if not fs.dir_exists(root):
        return None
    digest = hashlib.sha256()
    root_path = Path(root)
    for rel in fs.walk_files(root, skip):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update((sha256_file_cached(root_path / rel) or "").encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
