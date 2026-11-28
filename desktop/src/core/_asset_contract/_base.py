"""asset_contract 私有子模块 _base：基础层：严格 JSON 读、摘要、schema 声明缓存、仓库件集合与 resolve。

门面 core.asset_contract 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import json_doc, repo_face
from core.atoms import hash as hash_atom

from ._const import DECL_REL, SCHEMA, _MISSING



# ---------------------------------------------------------------- 基础
def _strict_json(text: str) -> Any:
    """严格如 RFC 8259：NaN/Infinity 不是 JSON 常量，出现即报错（不静默收下）。"""
    return json_doc.loads(text, dict, what="资产契约文本", strict_constants=True)



def digest_of(path: Path) -> str:
    """文件内容摘要（防篡改判据的单一口径：sha256 十六进制）。"""
    got = hash_atom.sha256_file_cached(path)
    if got is None:
        raise OSError("文件不可读：%s" % path)
    return got



@functools.lru_cache(maxsize=256)
def _schema_doc_cached(path: str, mtime_ns: int, size: int) -> Dict[str, Any]:
    _ = (mtime_ns, size)
    doc = _strict_json(Path(path).read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}



@functools.lru_cache(maxsize=16)
def _declaration_doc_cached(path: str, mtime_ns: int, size: int) -> Dict[str, Any]:
    _ = (mtime_ns, size)
    doc = _strict_json(Path(path).read_text(encoding="utf-8"))
    return doc if isinstance(doc, dict) else {}



def _declaration_doc(root: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    p = Path(root) / DECL_REL
    if not p.is_file():
        return None, ("缺数字资产契约声明 %s（修复指引：新建并写入 schema=%s 与 data/code/script 三面）"
                      % (DECL_REL, SCHEMA))
    try:
        st = p.stat()
        return _declaration_doc_cached(str(p.resolve()), int(st.st_mtime_ns),
                                       int(st.st_size)), None
    except OSError as exc:
        return None, "%s 不可读：%s（修复指引：修好权限或路径）" % (DECL_REL, exc)
    except ValueError as exc:
        return None, "%s 不可读或不是合法 JSON：%s（修复指引：修好语法）" % (DECL_REL, exc)



def _schema_doc(root: str, rel: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """schema 内容按 `(path, mtime, size)` 只读一次；扫描热路径不再逐件重开同一 schema。"""
    p = Path(root) / rel
    try:
        st = p.stat()
        return _schema_doc_cached(str(p.resolve()), int(st.st_mtime_ns), int(st.st_size)), None
    except OSError as exc:
        return None, "读不到 %s：%s（修复指引：核对声明里的路径在场）" % (rel, exc)
    except ValueError as exc:
        return None, "%s 不是合法 JSON：%s" % (rel, exc)



def _read(root: str, rel: str) -> Tuple[Optional[str], Optional[str]]:
    """读文本件 → (text, issue)。缺件/不可读不抛裸异常，如实报问题（扫描要能出报告）。"""
    p = Path(root) / rel
    try:
        return p.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, "读不到 %s：%s（修复指引：核对声明里的路径在场）" % (rel, exc)
    except UnicodeDecodeError as exc:
        return None, "%s 不是 UTF-8：%s（修复指引：转成 UTF-8 再入库）" % (rel, exc)



#: root → 仓库件集合（或 None = 采集失败：退回全量 glob）。一次进程内记忆。
_REPO_FILES: dict[str, set | None] = {}

_RESOLVE_MEMO: dict[tuple[str, str, str], List[str]] | None = None

#: 只在一次 `scan()` 作用域内复用仓库件集合；直接 `resolve()` 调用一律现算（防陈旧缓存）。
_REPO_SCOPE = False



def _repo_files(root: str) -> set | None:
    """→ 仓库件集合（根相对 posix 路径）；采集失败 → None（退回文件系统 glob）。

    为什么需要（2026-10-22 基线修复）：`glob` 会把**构建产物**也算进 `files` 统计——实测
    `engine/dotnet/**/*.cs` 在「build 过」的树上多出 3–9 个 `obj/` 生成件，于是同一个提交
    在不同机器上得到不同的 `files` 计数，机器可读报告（root_digest）因此**不可复核**。
    口径复用 `core.repo_face.walk_repo_paths`（全仓扫描面的**单一出处**：跳过 VCS/工具缓存/
    `.gitignore` 覆盖面）⇒ 计数只看仓库件，与「build 没 build」无关。
    非 git 目录（单测夹具 / 临时树）：`walk_repo_paths` 只按静态目录名剪枝，仍回全量件，
    夹具语义不变。
    """
    base = Path(os.path.abspath(str(root)))       # walk 产出绝对路径：基准同口径，才不 ValueError
    # 只对**仓根**（含 linked worktree 的 .git 指针文件）记忆：单测夹具目录会在同一进程里
    # 继续加件，缓存会把后加的件吞掉（实测 test_asset_contract 的 schema_siblings 用例）。
    cacheable = (base / ".git").exists()
    key = str(base)
    if cacheable and _REPO_SCOPE and key in _REPO_FILES:
        return _REPO_FILES[key]
    got: set | None = None
    try:
        got = {p.relative_to(base).as_posix() for p in repo_face.walk_repo_paths(str(root))}
    except (OSError, ValueError):
        got = None
    if cacheable and _REPO_SCOPE:
        _REPO_FILES[key] = got
    return got



def clear_repo_files_cache() -> None:
    """清空仓库件集合缓存（daemon 每请求 / 显式失效用）。"""
    global _REPO_SCOPE, _RESOLVE_MEMO
    _REPO_FILES.clear()
    _RESOLVE_MEMO = None
    _REPO_SCOPE = False



def _begin_repo_scope() -> None:
    global _REPO_SCOPE, _RESOLVE_MEMO
    _REPO_FILES.clear()
    _RESOLVE_MEMO = {}
    _REPO_SCOPE = True



def _end_repo_scope() -> None:
    global _REPO_SCOPE, _RESOLVE_MEMO
    _REPO_FILES.clear()
    _RESOLVE_MEMO = None
    _REPO_SCOPE = False



def resolve(root: str, spec: Dict[str, Any]) -> List[str]:
    """声明 → 命中的仓库相对路径列表（`path` 单件 / `glob` 多件，后者稳定排序）。

    `glob` 命中面按**受跟踪件**收窄（见 `_tracked_files`）：构建产物不算契约面。
    """
    r = Path(root)
    if spec.get("path"):
        rel = str(spec["path"]).replace("\\", "/")
        return _resolve_path(r, rel)
    pat = str(spec.get("glob") or "")
    if not pat:
        return []
    return _resolve_glob(r, root, pat)


def _memo_key(r: Path, kind: str, value: str) -> tuple:
    """解析结果缓存键（根绝对路径 + 声明种类 + 值）。"""
    return (str(r.resolve()), kind, value)


def _resolve_path(r: Path, rel: str) -> List[str]:
    """`path` 单件声明解析（缓存命中优先）。"""
    key = _memo_key(r, "path", rel)
    if _RESOLVE_MEMO is not None and key in _RESOLVE_MEMO:
        return list(_RESOLVE_MEMO[key])
    got = [rel] if (r / rel).is_file() else []
    if _RESOLVE_MEMO is not None:
        _RESOLVE_MEMO[key] = list(got)
    return got


def _glob_repo(repo_files, pat: str) -> List[str]:
    """受跟踪件面里按 glob 匹配（稳定排序）。"""
    from core import conformance_scan as csc
    return sorted(rel for rel in repo_files if csc.match_rel(rel, pat))


def _resolve_glob(r: Path, root: str, pat: str) -> List[str]:
    """`glob` 多件声明解析（缓存命中优先；命中面按受跟踪件收窄）。"""
    key = _memo_key(r, "glob", pat)
    if _RESOLVE_MEMO is not None and key in _RESOLVE_MEMO:
        return list(_RESOLVE_MEMO[key])
    repo_files = _repo_files(root)
    if repo_files is not None:
        got = _glob_repo(repo_files, pat)
    else:
        got = sorted(p.relative_to(r).as_posix()
                     for p in r.glob(pat) if p.is_file())
    if _RESOLVE_MEMO is not None:
        _RESOLVE_MEMO[key] = list(got)
    return got



def _dig(obj: Any, path: str) -> Any:
    """按点号路径取值（dict 键 / list 下标）；取不到返回哨兵（不抛异常）。"""
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur
