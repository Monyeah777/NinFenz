"""验证器三性质探针（机制借鉴 vivera lib/chunk-schema.mjs:28-49）。

一条判据函数应当：① 坏数据**不抛异常**（软失败）；② **一次报全部**违规（穷尽）；
③ **纯净**（无 fs/时钟/随机）。本模块给出可跑的探针。
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, List

_IMPURE = {"open", "time", "random", "os", "datetime", "subprocess", "socket"}


def no_throw(fn: Callable[[Any], Any], bad_inputs: Iterable[Any]) -> List[str]:
    """对每条坏数据调用，异常即记。"""
    out = []
    for bad in bad_inputs:
        try:
            fn(bad)
        except Exception as exc:
            out.append("坏数据 %r 触发异常：%s（修复指引：改为软失败返回 issue）" % (bad, exc))
    return out


def exhaustive(fn: Callable[[Any], Any], sample: Any, expect_min: int) -> List[str]:
    """单次调用应报出 ≥ expect_min 条（而不是首错即返）。"""
    got = fn(sample)
    n = len(got) if hasattr(got, "__len__") else 0
    if n < expect_min:
        return ["一次只报出 %d 条 < %d（修复指引：穷尽报错，不首错即返）" % (n, expect_min)]
    return []


def purity(fn: Callable[..., Any]) -> List[str]:
    """按 code 常量名粗判非纯净能力。"""
    names = set(getattr(fn.__code__, "co_names", ()))
    hit = sorted(names & _IMPURE)
    return ["引用了非纯净能力：%s（修复指引：把 I/O 与时钟注入）" % ", ".join(hit)] if hit else []
