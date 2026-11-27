"""conformance_scan 私有子模块 _walk：枚举层：scandir 单遍枚举 / 段级 glob 匹配 / 子树清单 / 模块文档清单。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import functools
import os
import re
from pathlib import Path

from ._resident import _Entry, _RESIDENT_DIR_MAX, _resident_key, _resident_under
from . import _resident as _rs
from . import _memo as _memo



def matches_any(rel: str, patterns) -> bool:
    """仓库相对路径是否落在任一模式内（语义与 `iter_files` 同源：`**` 跨目录、`*` 不跨）。

    两侧都按 `lower()` 归一：① 监听给的是**小写**相对路径，而模式里有 `INDEX.json` 这种大写；
    ② 归一后若「本该不匹配却被判成匹配」，后果只是**多算一次**（安全方向）——反过来才会陈旧。
    """
    segs = [s.lower() for s in str(rel).replace("\\", "/").split("/")]
    for pat in patterns:
        if _match_parts(segs, _compiled_parts(str(pat).replace("\\", "/").lower())):
            return True
    return False



def match_rel(rel: str, pattern: str) -> bool:
    """仓库相对路径是否匹配段级 glob（与 `iter_files` / `Path.glob` 同口径）。"""
    segs = [s for s in str(rel).replace("\\", "/").split("/") if s]
    return _match_parts(segs, _compiled_parts(str(pattern)))



def _fast_glob_supported(pattern: str) -> bool:
    """本模块自走的枚举支持的**模式子集**：段级 `**` + 段内 `*` / `?`。

    超出子集一律**回退** `Path.glob`——宁可慢，也不许悄悄改语义（回退面：字符类 `[…]`、
    以 `**` 结尾的模式）。子集与 `Path.glob` 的**逐模式等价**由单测钉住（含点文件）。
    """
    pat = str(pattern)
    if "[" in pat or "]" in pat:
        return False
    return pat.split("/")[-1] != "**"



@functools.lru_cache(maxsize=512)
def _segment_regex(part: str) -> "re.Pattern[str]":
    """把单个路径段编译成正则：`*` → 任意（不含 `/`），`?` → 单字符（不含 `/`）。

    **Windows 上必须大小写不敏感**：`Path.glob` 依托 `os.path.normcase`，在 Windows 上
    `*.md` 能匹配 `UPPER.MD`（既有 glob 用例「后缀不分大小写 + 点文件在面内」已钉死该语义）。
    快速枚举器若按大小写敏感匹配，会在 Windows 上**静默丢件**——实测（他证）：`glob-case`
    合成树上 `Path.glob` 6 件 / 快速枚举 5 件（丢 `.../UPPER.MD`），进而使 `asset usage /
    density / thickness`、`output meter` 与 `content_fingerprint`（**落盘缓存的键**）一起少算。
    """
    out = []
    for ch in part:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out) + "$",
                      re.IGNORECASE if os.name == "nt" else 0)



@functools.lru_cache(maxsize=512)
def _compiled_parts(pattern: str):
    """把模式**一次**编译成「段 → 正则（`**` 记为 None）」的元组。

    依据（实测）：走查版与清单版过去都**每次调用**重新编译段正则——一次 evaluate 里
    `_segment_regex` 被调 **31995** 次、`re.escape` **164752** 次（自耗时合计 ~0.29 s）。
    模式的编译结果是**模式的纯函数**（与文件系统无关），故可长期记忆，不存在陈旧问题。
    """
    return tuple(None if part == "**" else _segment_regex(part)
                 for part in (p for p in str(pattern).split("/") if p != ""))



def _scandir_list(path: str):
    """列目录（绝不抛）：目录不可读/已消失时返回空——枚举面按「不存在」处理。

    常驻层命中即**零 IO**（守护带监听时安装，见 `_RESIDENT` 的说明）；**冷进程**也没必要重复走：
    本次只读调用内每个目录只列一遍（`_DIR_MEMO`，键带 `entries` 前缀，免得与 `_module_docs` 撞键）
    ——实测一次冷跑 2768 次 `scandir` 只覆盖 907 个目录（3.0 倍重复），而 2000 次 `scandir` 本机要
    ~306 ms：宽面各枚举一遍时，这笔重复是纯浪费。
    """
    key = _resident_key(path)
    if _rs._RESIDENT is not None:
        hit = _rs._RESIDENT["dirs"].get(key)
        if hit is not None:
            return hit
    dir_memo = _memo._DIR_MEMO
    memo = ("entries", key) if dir_memo is not None else None
    if memo is not None and dir_memo is not None:
        hit = dir_memo.get(memo)
        if hit is not None:
            return hit
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError:  # 目录列不到 ⇒ 空清单（IO/权限问题；该类缺口由对应门禁另行报出，见 AUD-0016）
        return []
    if memo is not None and dir_memo is not None:
        dir_memo[memo] = entries
    if _rs._RESIDENT is not None and _resident_under(key)\
            and len(_rs._RESIDENT["dirs"]) < _RESIDENT_DIR_MAX:
        packed = []
        for entry in entries:
            try:
                packed.append(_Entry(entry.name, entry.path, entry.is_dir(),
                                     entry.is_file(), entry.is_symlink()))
            except OSError:                     # 枚举与取值之间消失的条目 → 当作不存在
                continue
        _rs._RESIDENT["dirs"][key] = packed
        return packed
    return entries



#: 扫描**从不进入**的目录：工具/环境的临时产物，不是仓库内容。
#: 2026-10-19 实测：`.rivet/`（本仓 agent 的 scratch，含 1.6 GB / 3 万文件）会让
#: `**/*.py` 这类宽面枚举从 ~1 s 涨到 >25 s，进而把 conformance 的 purity 契约拖到挂死。
#: 它们本来就被 .gitignore 排除、也不该参与判据——跳过后语义更准（只看仓库内容），也更快。
NON_REPO_DIRS = frozenset({".git", ".rivet", ".venv", "node_modules", "__pycache__",
                           ".mypy_cache", ".pytest_cache", ".ruff_cache"})



def _enumerate_rel(root_abs: str, pattern: str) -> List[str]:
    """`os.scandir` **单遍**枚举（相对 root 的 posix 路径）。语义对齐 `Path.glob`：

    - `**` 消费**零或多层目录**，且不进入符号链接目录（与 pathlib 的 `_RecursiveWildcardSelector` 同）；
    - `*` / `?` 不跨 `/`；**含点文件**（pathlib 的 glob 不隐藏点文件，这里也不）；
    - 末段只收**真实文件**；符号链接一律不收——遍历器不得把本机任意文件带进仓库语料。

    为什么不用 `Path.glob`：它的 `**` 逐层重入，实测本仓 `community/*/outputs/**/*`（1156 件）
    要 236 ms，而 `os.scandir` 单遍约 90 ms——指纹每次只读调用都要按输入面枚举一遍。
    """
    parts = _compiled_parts(pattern)
    out: List[str] = []

    def match(dir_abs: str, rel: str, i: int) -> None:
        if i >= len(parts):
            return
        rx = parts[i]
        if rx is None:                                        # `**`
            match(dir_abs, rel, i + 1)                       # 零层：当前目录直接续匹配
            for entry in _scandir_list(dir_abs):
                try:
                    if entry.is_dir() and not entry.is_symlink()\
                            and entry.name not in NON_REPO_DIRS:
                        match(entry.path, rel + entry.name + "/", i)
                except OSError:
                    continue
            return
        last = (i == len(parts) - 1)
        for entry in _scandir_list(dir_abs):
            if not rx.match(entry.name):
                continue
            try:
                if last:
                    if entry.is_file() and not entry.is_symlink():
                        out.append(rel + entry.name)
                elif entry.is_dir():
                    match(entry.path, rel + entry.name + "/", i + 1)
            except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
                continue

    match(root_abs, "", 0)
    return sorted(out)



def iter_files(root, pattern: str) -> List[str]:
    """按模式枚举**文件**（相对 root 的 posix 路径，已排序）。作用域内按 (root, 模式) 记忆。

    作用域与读缓存同生命周期（`read_memo` 出口即清），因此**不跨调用复用**——与「新起进程
    看同一份仓库事实」的冷却语义一致，不存在陈旧目录清单。
    """
    root_abs = os.path.abspath(str(root))
    key = (os.path.normcase(root_abs), str(pattern))
    if _memo._PAT_MEMO is not None:
        hit = _memo._PAT_MEMO.get(key)
        if hit is not None:
            return list(hit)
    prefix = _fixed_prefix(str(pattern))
    tree = _tree_hit(root_abs, prefix)          # 子树清单已在作用域里 ⇒ 内存里筛，零 IO
    if tree is not None:
        parts = _compiled_parts(str(pattern))
        got = tuple(rel for rel in tree
                    if _match_parts(rel.split("/"), parts))
    elif _fast_glob_supported(pattern):
        got = tuple(_enumerate_rel(root_abs, str(pattern)))
    else:
        base = Path(root)
        got = tuple(sorted(p.relative_to(base).as_posix()
                           for p in base.glob(str(pattern))
                           if p.is_file() and not p.is_symlink()))
    if _memo._PAT_MEMO is not None:
        _memo._PAT_MEMO[key] = got
    return list(got)



def _fixed_prefix(pattern: str) -> str:
    """模式里**通配符之前**的固定目录前缀（`a/b/*.md` → `a/b`；全固定件 → 其所在目录）。

    只用于「子树清单是否已在作用域里」的定位，不参与匹配语义。
    """
    parts = [p for p in str(pattern).split("/") if p != ""]
    keep: List[str] = []
    for part in parts[:-1]:
        if any(ch in part for ch in "*?["):
            break
        keep.append(part)
    return "/".join(keep)



def _match_parts(segments, parts) -> bool:
    """把**整条相对路径**的分段与模式分段做匹配（`**` 消费零或多段）——与走查版语义同源。

    与 `_enumerate_rel` 共用 `_segment_regex`，两版的等价性由 `FastGlobTest` 同时覆盖
    （走查版与「子树清单」版各测一遍，防止两条路径漂移）。
    """
    def step(si: int, pi: int) -> bool:
        """下标版递归：不做切片（切片在 4.6 万次调用里本身就值 ~0.1 s）。"""
        if pi >= len(parts):
            return si >= len(segments)
        rx = parts[pi]
        if rx is None:                                   # `**`：零段或多段
            if step(si, pi + 1):
                return True
            return si < len(segments) and step(si + 1, pi)
        if si >= len(segments):
            return False
        if not rx.match(segments[si]):
            return False
        return step(si + 1, pi + 1)

    return step(0, 0)



def tree_files(root, rel_dir: str = "") -> List[str]:
    """`rel_dir` 子树内**全部文件**（仓库相对 posix 路径，已排序）。作用域内按目录记忆。

    给「要按多个模式反复匹配同一棵树」的调用方用（`layer_model` 的真源面展开就是这种形状）。
    作用域与读缓存同生命周期：出口即清，不跨调用复用。
    """
    root_abs = os.path.abspath(str(root))
    key = os.path.normcase(os.path.join(root_abs, str(rel_dir or "")))
    if _memo._TREE_MEMO is not None:
        hit = _memo._TREE_MEMO.get(key)
        if hit is not None:
            return list(hit)
    out: List[str] = []

    def walk(dir_abs: str, rel: str) -> None:
        for entry in _scandir_list(dir_abs):
            try:
                if entry.is_dir():
                    if not entry.is_symlink():
                        walk(entry.path, rel + entry.name + "/")
                elif entry.is_file() and not entry.is_symlink():
                    out.append(rel + entry.name)
            except OSError:  # 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁另行报出（见 AUD-0016）
                continue

    start_rel = "" if not rel_dir else str(rel_dir).strip("/") + "/"
    walk(key, start_rel)
    got = tuple(sorted(out))
    if _memo._TREE_MEMO is not None:
        _memo._TREE_MEMO[key] = got
    return list(got)



def _tree_hit(root_abs: str, rel_dir: str):
    """作用域里**已有**的子树清单（没有就返回 None——不主动去建，免得比定向走查更贵）。"""
    if _memo._TREE_MEMO is None:
        return None
    return _memo._TREE_MEMO.get(os.path.normcase(os.path.join(root_abs, str(rel_dir or ""))))



def _module_docs(root: str) -> List[str]:
    """模块文档清单（**一次只读调用内只走一遍文件系统**——见 `read_memo`）。

    实测：一次 `evaluate` 里本函数被调 **5** 次（各扫描器各自重走 `04_模块库` + `community/*/modules`），
    合计 167 ms。作用域与读缓存同生命周期，出口即清——下一次调用照常重新列目录，故不会陈旧。

    2026-09-29 再改**枚举器**：原实现是 `os.walk("04_模块库")` + 逐包 `os.listdir(mdir)` +
    `os.path.isdir(mdir)`，在守护口径下每次新内容状态都要重付——实测 **107 次 `listdir` + 113 次
    `isdir` ≈ 21 ms**（占该状态 os/stat 面的四分之一）。改走共享枚举器（目录清单已在常驻层）
    后同一张面 **~0.5 ms**；面**逐件一致**由 `test_conformance_scan.ModuleDocsEquivalenceTest`
    用旧口径原样重算比对，**跨作用域新鲜**由 `ModuleDocsMemoTest` 用合成树盯着。
    """
    key = os.path.normcase(os.path.abspath(str(root)))
    if _memo._DIR_MEMO is not None and key in _memo._DIR_MEMO:
        return list(_memo._DIR_MEMO[key])
    out: List[str] = []
    for pattern in ("04_模块库/**/*.md", "community/*/modules/*.md"):
        for rel in iter_files(root, pattern):
            out.append(os.path.join(root, *rel.split("/")))
    out = sorted(out)
    if _memo._DIR_MEMO is not None:
        _memo._DIR_MEMO[key] = out
    return list(out)
