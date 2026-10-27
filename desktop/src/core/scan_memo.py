#!/usr/bin/env python3
"""一次扫描内的**共享读面 + 派生事实面**（`verify_report` 结构性去重的底座）。

为什么需要（cProfile 实测，2026-10-25，本机）：
`verify_report` 的 31 条判据**各自全仓扫一遍**，一次 build 里出现：
`io.open` 32,921 次 ≈ 6.1 s、`pathlib.read_text` 28,113 次 ≈ 8.6 s、
`ast.walk` 197 万次 ≈ 7.0 s、`re.Pattern.search` 46,942 次 ≈ 6.5 s。
其中绝大多数是「**同一批文件、同一读法、同一 AST**」的纯重复。

设计（踩过坑后的定稿）：
- **键 = `os.path.abspath` 的字符串**，**绝不用 `Path.resolve()`**——实测它在 Windows 上每次走
  realpath 系统调用，32k 次读合计十余秒，缓存反而比不缓存更慢（第一版就栽在这）。
- **新鲜度靠作用域**：`begin()/end()` 圈定一次扫描；长驻进程（daemon）每请求前 `begin()`
  （与 `daemon.reset_process_caches` 清按路径缓存同一纪律）。作用域内文件不会半路被改——
  真被改了也应由上层的"冻结链顺序"保证，而不是靠每个读都去 stat 一次（那也是 Windows 上的贵操作）。
- 只缓存**成功**：读失败/语法错照原样让调用方处理（异常与 issue 文案语义不变）。
- `stats()` 暴露 read/parse/facts 的**命中率**——把「重复 I/O」从感觉变成可机读指标。
"""
from __future__ import annotations

import ast
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

_TEXT: dict[tuple, str] = {}
_AST: dict[tuple, Any] = {}
_FACTS: dict[tuple, Any] = {}
#: 作用域深度（可重入）：公开入口（`scan`/`_run_uncached`/`build`）各自 begin/end。
#: **语义（2026-10-27 起）**：作用域只重置**计数器**，不丢弃读面/AST/事实缓存——缓存键含
#: (abspath, mtime_ns, size)，文件一改键就变，因此跨调用保活**不会读到旧内容**；而
#: 「进程内连续跑 N 条 CLI 面」（`cli_harness.run_cli_proc` 的扫描类用例，实测每条面 ≈1 s、
#: 单文件 stat 16 万次）由此从 N×扫描 变成 1×扫描 + N×命中。
#: 需要"每入口彻底冷启"的口径（对齐新起进程）可设 `NF_SCAN_MEMO=cold`。
#: **不缓存 stat 结果**：实测缓存 stat 会让"改文件后重扫"读到旧键（`test_regex_limit_ratchet`
#: 直接踩到）。重复 stat 的正确解法是**减少调用次数**（见 judgement_coverage 的 signals 表），
#: 不是把 stat 结果记住。
_DEPTH = 0
_STATS = {"read": 0, "read_hit": 0, "parse": 0, "parse_hit": 0, "facts": 0, "facts_hit": 0}


def _key(path: Any) -> tuple | None:
    """缓存键 = (绝对路径, mtime_ns, size)。

    为什么带 stat（而不是只按路径）：只按路径的缓存**跨"改文件后重扫"会吃旧值**——实测
    `test_asset_contract.test_regex_limit_ratchet` 就踩到了（同一进程里改临时文件再扫）。
    stat 是**单次**系统调用（不像 `Path.resolve()` 的 realpath 那么贵），32k 次读 ≈ 0.1~0.3 s，
    换来的是「文件改了键就变」的正确性。
    """
    if path is None:
        return None
    try:
        ab = os.path.abspath(os.fspath(path))
    except (TypeError, ValueError):
        # 可吞：路径不可表达（None/非路径对象）→ 调用方直接计算，与"未命中缓存"同语义。
        return None
    try:
        st = os.stat(ab)
    except OSError:
        # 可吞：文件不存在 → 调用方退化为直接计算（与"未命中缓存"同语义）。
        return None
    return (ab, st.st_mtime_ns, st.st_size)


def read_text(path: Any) -> str | None:
    """容错读：等价 `p.read_text(encoding="utf-8", errors="replace")`；缺件/不可读 → None。"""
    key = _key(path)
    if key is None:
        return None
    got = _TEXT.get(key)
    if got is not None:
        _STATS["read_hit"] += 1
        return got
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    _TEXT[key] = text
    _STATS["read"] += 1
    return text


def read_text_strict(path: Any) -> str:
    """严格读：等价 `p.read_text(encoding="utf-8")`，OSError/UnicodeDecodeError 原样抛。"""
    key = _key(path)
    if key is not None:
        got = _TEXT.get(key)
        if got is not None:
            _STATS["read_hit"] += 1
            return got
    text = Path(path).read_text(encoding="utf-8")
    if key is not None:
        _TEXT[key] = text
    _STATS["read"] += 1
    return text


def parse(path: Any) -> Any | None:
    """解析 AST（同一文件只解析一次）；语法错/缺件 → None（调用方出 issue 文案）。"""
    key = _key(path)
    if key is None:
        return None
    got = _AST.get(key)
    if got is not None:
        _STATS["parse_hit"] += 1
        return got
    text = read_text(path)
    if text is None:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    _AST[key] = tree
    _STATS["parse"] += 1
    return tree


def facts(name: str, path: Any, compute: Callable[[], Any]) -> Any:
    """按「文件」缓存派生事实（如一次 AST 遍历得出的结论）。"""
    key = _key(path)
    if key is None:
        return compute()
    k = (name, key)
    if k in _FACTS:
        _STATS["facts_hit"] += 1
        return _FACTS[k]
    got = compute()
    _FACTS[k] = got
    _STATS["facts"] += 1
    return got


def pure(name: str, key: Any, compute: Callable[[], Any]) -> Any:
    """按「内容键」缓存纯函数结果（如 ReDoS 探针：同一 pattern 只探一次）。"""
    k = (name, key)
    if k in _FACTS:
        _STATS["facts_hit"] += 1
        return _FACTS[k]
    got = compute()
    _FACTS[k] = got
    _STATS["facts"] += 1
    return got



# ---------------------------------------------------------------- 消费信号（单遍字符扫描）
_IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_BODY = _IDENT_START | frozenset("0123456789")
_BLANKS = " 	"


def _ident_at(text: str, i: int) -> tuple[str, int]:
    j = i
    n = len(text)
    while j < n and text[j] in _IDENT_BODY:
        j += 1
    return text[i:j], j


def token_signals(path: Any) -> dict:
    """抽「消费信号」：`NAME.xxx(...)` 的 NAME 集合 / 带引号的名字集合。

    为什么不用正则：第一版用了带 `[A-Za-z0-9_]*` 的 pattern，`redos_scan` 当场判定它在
    `'a'*65536` 上二次回溯（27 s）——**判据是对的**：这类"长标识符后必须紧跟某字符"的
    pattern 在失败路径上必然 O(n²)。改成单遍字符扫描：线性、无回溯、也无 ReDoS 面。
    """
    text = read_text(path) or ""
    calls, quoted = set(), set()
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == ".":
            k = i - 1
            while k >= 0 and text[k] in _BLANKS:
                k -= 1
            end = k + 1
            while k >= 0 and text[k] in _IDENT_BODY:
                k -= 1
            name = text[k + 1:end]
            if name and name[0] in _IDENT_START:
                j = i + 1
                while j < n and text[j] in _BLANKS:
                    j += 1
                if j < n and text[j] in _IDENT_START:
                    _, j2 = _ident_at(text, j)
                    while j2 < n and text[j2] in _BLANKS:
                        j2 += 1
                    if j2 < n and text[j2] == "(":
                        calls.add(name)
            i += 1
            continue
        if ch in "'\"":
            if i > 0 and text[i - 1] in _IDENT_BODY:
                i += 1
                continue
            j = i + 1
            if j < n and text[j] in _IDENT_START:
                name, j2 = _ident_at(text, j)
                if j2 < n and text[j2] == ch:
                    quoted.add(name)
            i += 1
            continue
        i += 1
    return {"calls": calls, "imports": from_core_names(text), "quoted": quoted}


def from_core_names(text: str) -> set:
    """`from core[.X] import a, b` 里的模块名/导入名（按行解析，不做跨行正则）。"""
    out = set()
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("from core"):
            continue
        head, sep, rest = s.partition(" import ")
        if not sep:
            continue
        if head.startswith("from core."):
            out.add(head[len("from core."):].split(".")[0])
        for tok in rest.replace(",", " ").split():
            if tok and (tok[0].isalpha() or tok[0] == "_"):
                out.add(tok)
    return out


def signals(path: Any) -> dict:
    """按文件缓存的消费信号（`token_signals` 的事实面包装）。"""
    return facts("signals", path, lambda: token_signals(path))


def begin() -> None:
    """开一次扫描作用域（可重入）：只重置计数器，数据缓存按 mtime 键跨调用保活。"""
    global _DEPTH
    if _DEPTH == 0:
        _reset_stats()
        if os.environ.get("NF_SCAN_MEMO") == "cold":
            _clear_data()
    _DEPTH += 1


def end() -> dict[str, int]:
    """结束作用域：返回统计并重置计数器（**不清数据缓存**，见模块顶部语义说明）。"""
    global _DEPTH
    _DEPTH = max(0, _DEPTH - 1)
    if _DEPTH > 0:
        return stats()
    got = stats()
    _reset_stats()
    _clear_if_huge()
    return got


def _reset_stats() -> None:
    for k in _STATS:
        _STATS[k] = 0


def _clear_data() -> None:
    _TEXT.clear()
    _AST.clear()
    _FACTS.clear()


def _clear_if_huge(limit: int = 20000) -> None:
    """兜底内存上限：条目过多就整体丢弃（缓存只是加速面，丢了下一次重建即可）。"""
    if len(_TEXT) + len(_AST) + len(_FACTS) > limit:
        _clear_data()


def reset() -> None:
    """显式清空（测试/长驻进程需要"彻底冷启"时用）。"""
    _clear_data()
    _reset_stats()


def stats() -> dict[str, int]:
    return dict(_STATS)


def scoped(fn):
    """把公开入口包成"自成作用域"（**不改名**：源码里仍是 `def scan(`，靠它做静态识别的判据不受影响）。

    为什么不做成重命名 + 薄包装：本仓有判据按源码文本识别「模块是否定义 `def scan(`」
    （judgement_coverage / 死码 / 层级面），改名会让这些判据**静默失真**——实测改名的第一版
    直接让 verify_report 的判据结论与已冻结报告对不上。
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        begin()
        try:
            return fn(*args, **kwargs)
        finally:
            end()

    return wrapper
