"""发布物自证清单：生成器 + 逐件字节摘要 + 真源 SHA（机制借鉴 tokalator / o8 产物嵌双 SHA）。

补 NF「源码判据强、发布物判据弱」：产物清单自带生成器标识与逐件 sha256，
消费方可离线校验产物未被替换；同时强制「覆盖与局限」段（标明未覆盖面）。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List

from core.atoms import hash as hash_atom


def _sha(path: str) -> str:
    # 发布清单是防篡改锚点：直接分块重算，不能信任可能同 mtime/size 的快捷缓存。
    got = hash_atom.sha256_file(Path(path))
    if got is None:
        raise OSError("产物不可读：%s" % path)
    return got


def _safe_rel(rel: str) -> str:
    value = str(rel).replace("\\", "/")
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("产物路径必须是非空仓库相对路径：%r" % rel)
    return pure.as_posix()


def _root_digest(files: Dict[str, str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(str(files[rel])))
        digest.update(b"\1")
    return digest.hexdigest()


def _surface_files(root: str) -> set:
    base = Path(root)
    return {p.relative_to(base).as_posix() for p in base.rglob("*")
            if p.is_file() and not p.is_symlink()}


def build(root: str, paths: Iterable[str], generator: str, coverage: str,
          closed_surface: bool = False) -> Dict[str, Any]:
    """构造清单；coverage 为必填「覆盖与局限」段。"""
    if not coverage.strip():
        raise ValueError("缺「覆盖与局限」段（修复指引：写清本产物覆盖什么、不覆盖什么）")
    normalized = sorted({_safe_rel(rel) for rel in paths})
    if closed_surface:
        untracked = sorted(_surface_files(root) - set(normalized))
        if untracked:
            raise ValueError("封闭产物面存在未登记文件：%s（修复指引：纳入 paths 或移出产物目录）"
                             % ", ".join(untracked[:5]))
    files: Dict[str, str] = {}
    for rel in normalized:
        full = os.path.join(root, rel)
        files[rel] = _sha(full)
    return {"generator": generator, "coverage": coverage,
            "closed_surface": bool(closed_surface), "files": files,
            "root_sha256": _root_digest(files)}


def verify(manifest: Dict[str, Any], root: str) -> List[str]:
    """逐件重算 → 漂移清单。"""
    issues: List[str] = []
    if not str(manifest.get("coverage") or "").strip():
        issues.append("清单缺「覆盖与局限」段（修复指引：补 coverage）")
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return issues + ["清单 files 须为对象（修复指引：重建清单）"]
    normalized: Dict[str, str] = {}
    for raw_rel, want in files.items():
        try:
            rel = _safe_rel(str(raw_rel))
        except ValueError as exc:
            issues.append(str(exc))
            continue
        if not isinstance(want, str) or len(want) != 64:
            issues.append("产物摘要形状非法：%s（修复指引：重建清单）" % rel)
            continue
        normalized[rel] = want
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            issues.append("产物缺件：%s（修复指引：重建产物）" % rel)
            continue
        if _sha(full) != want:
            issues.append("产物已漂移：%s（修复指引：重跑生成器重建清单）" % rel)
    root_want = str(manifest.get("root_sha256") or "")
    if not files:
        return issues
    if not root_want:
        issues.append("清单缺 root_sha256（修复指引：重建清单以锚定整面）")
    elif root_want != _root_digest(normalized):
        issues.append("清单整面 Merkle 根不符（修复指引：重跑生成器重建清单）")
    if manifest.get("closed_surface") is True:
        untracked = sorted(_surface_files(root) - set(normalized))
        if untracked:
            issues.append("封闭产物面出现未登记文件：%s（修复指引：纳入清单或移出产物目录）"
                          % ", ".join(untracked[:5]))
    return issues
