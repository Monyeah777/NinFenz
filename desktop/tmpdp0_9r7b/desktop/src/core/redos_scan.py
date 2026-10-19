#!/usr/bin/env python3
"""正则失控回溯（ReDoS）扫描：把「工具链零 ReDoS 规则」补成一条会红的判据。

为什么需要（2026-10-10 全仓审计 Y3，P1）：仓内 173 处字面量 `re.compile`，而 ruff/bandit
没有 ReDoS 规则。实测两处引文正则 `[0-9A-Za-z_]+:` 在「长串字母数字但没有冒号」的输入上
O(n²)：64 KB 要 2.8 s（同一形态在 `round_drill` 与 `assemble_plan` 各一份）。

两条判据（互补）：
- **形态**（静态）：`(原子+量化)+` 这种「量词套量词、中间没有强制分隔符」的形态可指数回溯
  （如 `(a+)+`）。刻意比 `json_schema._NESTED_QUANT` 更严：那个粗粒度正则会把
  `(?:[.-]\\d+)*` / `(?:_[A-Z0-9]+)+` 这类**每次迭代都有强制分隔符**的线性形态一起误报。
- **增长律**（动态）：用一族对抗输入实测耗时——超线性即报。只对**形态检查未命中**的表达式跑，
  且指数形态在静态阶段就被拦下，故动态探针的规模是有界的（不会真把门禁挂死）。

纯标准库；只读（不执行被扫模块，只编译它的字面量 pattern）。
"""
from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

#: 扫描面（与 sast_check 的 SCAN_TARGETS 同口径；额外含 tui）。
SCAN_DIRS = ("desktop/src", "scripts", "tui", ".github/scripts")

#: 「量词套量词」精确形态：组内**只有一个原子**且带无界量词，组外再套无界量词。
#: 组内有第二原子（`(?:[.-]\\d+)*`）时每次迭代必须消费一个分隔符 ⇒ 不可能指数回溯。
_NESTED = re.compile(
    r"\((?:\?:)?"
    r"(?:\[[^\]]*\]|\\[wsdWSD]|\\[^wsdWSD]|[^()\\])"   # 单个原子
    r"[+*]\)"                                                  # 原子 + 无界量词
    r"\s*[+*{]"                                                # 组外再套无界量词
)

#: 动态对抗输入：纯字符长串（触发「贪婪类 + 必需字面量」的回溯）与「长串 + 终结符」
#: （触发指数形态的失败路径）。
_SAMPLE_CHARS = ("a", "1", " ", ".", "-", "_", "§", ":")
_STOPPERS = ("!", "\n")


def suspicious_nesting(pattern: str) -> str:
    """→ 命中的「量词套量词」片段（空串 = 未命中）。纯函数，变异自证直接喂它。"""
    m = _NESTED.search(pattern)
    return m.group(0) if m else ""


def probe_inputs(n: int) -> List[Tuple[str, str]]:
    """→ [(说明, 输入)]：一族对抗输入（纯长串 + 长串带终结符）。"""
    out: List[Tuple[str, str]] = []
    for ch in _SAMPLE_CHARS:
        out.append(("run:%r" % ch, ch * n))
    mixed = ("a1. -_§:" * ((n // 8) + 1))[:n]
    out.append(("mixed", mixed))
    for stop in _STOPPERS:
        out.append(("run:a+%r" % stop, "a" * (n - 1) + stop))
        out.append(("mixed+%r" % stop, mixed[:-1] + stop))
    return out


def probe(pattern: str, n: int = 65536, budget_ms: float = 1500.0) -> Tuple[float, str]:
    """→ (最坏耗时 ms, 最坏输入的说明)；编译失败 → (0.0, "")（语法坏不归本面管）。

    只用 `search`：仓内正则绝大多数是「在长文本里找一处」的用法。
    """
    try:
        obj = re.compile(pattern)
    except re.error:
        return 0.0, ""
    worst_ms, worst_desc = 0.0, ""
    for desc, text in probe_inputs(n):
        t0 = time.perf_counter()
        try:
            obj.search(text)
        except (re.error, ValueError):     # 个别 pattern 对畸形输入抛错：不算回溯问题
            continue
        ms = (time.perf_counter() - t0) * 1000.0
        if ms > worst_ms:
            worst_ms, worst_desc = ms, desc
        if worst_ms > budget_ms:           # 超预算即定性，不再把后续输入跑完（门禁不挂死）
            break
    return worst_ms, worst_desc


def literal_patterns(root: str = ".", dirs: Tuple[str, ...] = SCAN_DIRS
                     ) -> List[Tuple[str, int, str]]:
    """AST 提取字面量 `re.compile("…")` → [(仓库相对路径, 行号, pattern)]。"""
    r = Path(root)
    out: List[Tuple[str, int, str]] = []
    for d in dirs:
        base = r / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.py")):
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except (OSError, SyntaxError):
                # 不可读/不可解析的件不构成正则命中面（其语法问题由 ruff / py_compile 判据报出）。
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "compile" and node.args):
                    continue
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append((p.relative_to(r).as_posix(), node.lineno, a.value))
    return out


def scan(root: str = ".", n: int = 65536, budget_ms: float = 1500.0
         ) -> Tuple[List[str], Dict[str, Any]]:
    """→ (issues, stats)：形态命中 + 动态超线性各成一条 issue（带修复指引）。"""
    issues: List[str] = []
    patterns = literal_patterns(root)
    checked = 0
    for rel, line, pat in patterns:
        shape = suspicious_nesting(pat)
        if shape:
            issues.append(
                "%s:%d 正则含量词套量词 %r（可能指数回溯）（修复指引：给内层量词一个强制分隔符，"
                "或改写为不重叠的字符类）" % (rel, line, shape))
            continue
        ms, desc = probe(pat, n=n, budget_ms=budget_ms)
        checked += 1
        if ms > budget_ms:
            issues.append(
                "%s:%d 正则超线性回溯：%d 字符的 %s 输入耗时 %.0f ms > 预算 %.0f ms"
                "（修复指引：给贪婪量词加前缀边界，或先按分隔符切分再匹配）"
                % (rel, line, n, desc, ms, budget_ms))
    stats = {"patterns": len(patterns), "probed": checked,
             "n": n, "budget_ms": budget_ms}
    return issues, stats


scan_repo = scan
