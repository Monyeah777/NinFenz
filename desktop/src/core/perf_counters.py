#!/usr/bin/env python3
"""结构性计数器：把「重复 I/O / 重复解析 / 重复 spawn」变成**可判据的数字**（而非毫秒）。

为什么需要（2026-10-26 教训）：本机同一命令当日出现 **13.1 s ↔ 24.3 s** 的墙钟漂移
（热降频 / 杀毒 / 并行 CI），任何跨时段"优化收益"都会被噪声吞掉或伪造。结构性计数
（本进程打开文件次数、stat 次数、正则 search 次数、子进程数、AST 解析数）**跨机器稳定**，
且直接刻画"做了多少重复劳动"——这才是性能回归该守的东西。

用法（显式开关，零常驻开销）：
    from core import perf_counters
    with perf_counters.count() as c:
        do_work()
    c["open"], c["stat"], c["regex"], c["spawn"], c["ast_parse"]

纪律：只在 `count()` 上下文内打补丁，退出即原样还原（含 partial 函数与包装链）；
不改变被计数函数的行为与返回值；不参与任何判定逻辑。
"""
from __future__ import annotations

import ast
import builtins
import contextlib
import io
import os
import re
import subprocess
from typing import Any, Iterator

#: 计数项（顺序稳定，便于逐字节比对）
KEYS = ("open", "stat", "scandir", "regex", "spawn", "ast_parse", "read_text")

#: 说明（写进证据文件，读者不必翻代码）
KEY_NOTES = {
    "open": "文件打开次数（builtins.open / io.open）",
    "stat": "stat/lstat 次数（os.stat / os.lstat）",
    "scandir": "目录枚举次数（os.scandir / os.listdir）",
    "regex": "正则模块级 search/match/findall/finditer 调用次数（编译后的 pattern 调用不在此列）",
    "spawn": "子进程创建次数（subprocess.Popen）",
    "ast_parse": "AST 解析次数（ast.parse）",
    "read_text": "pathlib.Path.read_text 次数",
}

_PATCHED: dict[str, Any] = {}


class _Counter(dict):
    """带属性访问的计数容器（`c["open"]` 与 `c.open` 等价，便于测试书写）。"""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - 只是更友好的报错
            raise AttributeError(item) from exc


@contextlib.contextmanager
def count() -> Iterator[_Counter]:
    """在工作区内计数；退出时还原所有被补丁的入口。"""
    c = _Counter({k: 0 for k in KEYS})

    def _wrap(obj: Any, name: str, key: str) -> Any:
        """把 `obj.name` 换成计数包装（保留原函数属性，便于 `functools.wraps`）。"""
        orig = getattr(obj, name)

        def wrapper(*a: Any, **kw: Any) -> Any:
            c[key] += 1
            return orig(*a, **kw)

        wrapper.__wrapped__ = orig                    # type: ignore[attr-defined]
        wrapper.__name__ = getattr(orig, "__name__", name)
        _PATCHED["%s@%s@%d" % (getattr(obj, "__name__", "?"), name, id(obj))] = (obj, name, orig)
        setattr(obj, name, wrapper)
        return wrapper

    try:
        _wrap(builtins, "open", "open")
        _wrap(io, "open", "open")
        _wrap(os, "stat", "stat")
        _wrap(os, "lstat", "stat")
        _wrap(os, "scandir", "scandir")
        _wrap(os, "listdir", "scandir")
        _wrap(subprocess, "Popen", "spawn")
        _wrap(ast, "parse", "ast_parse")
        import pathlib
        _wrap(pathlib.Path, "read_text", "read_text")
        # `re.Pattern` 是不可变类型（不能 setattr），故只统计模块级入口；
        # 编译后的 pattern 调用量由扫描侧的结构改造（见 perf_counters 的 note）另行追踪。
        _wrap(re, "search", "regex")
        _wrap(re, "match", "regex")
        _wrap(re, "findall", "regex")
        _wrap(re, "finditer", "regex")
        yield c
    finally:
        for _key, (obj, name, orig) in list(_PATCHED.items()):
            try:
                setattr(obj, name, orig)
            except Exception:                          # noqa: BLE001 - 还原尽力而为
                pass
        _PATCHED.clear()


def snapshot() -> dict[str, int]:
    """在**当前进程**跑一次"空转"并返回计数基线（用于判断补丁是否生效）。"""
    with count() as c:
        pass
    return dict(c)
