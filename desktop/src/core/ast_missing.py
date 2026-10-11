"""AST 判据 + 缺失清单（机制借鉴 ha_agent tests/test_websocket_security_ast.py）。

R5/R6 是直接 import/sink 面；本模块补**语法级「必须成对」判据**：某类函数体里必须
出现指定守卫调用，否则输出**一次列全的缺失清单**（而非逐条首错）。
"""
from __future__ import annotations

import ast
from typing import Iterable, List, Tuple


def _calls(tree: ast.AST) -> set:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def missing_guards(source: str, func_prefix: str, required: Iterable[str]) -> List[Tuple[str, List[str]]]:
    """→ [(函数名, 缺失守卫列表)]；函数名以 func_prefix 开头者才检查。"""
    need = set(required)
    out: List[Tuple[str, List[str]]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [("<syntax>", ["源码不可解析：%s（修复指引：先修语法）" % exc])]
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith(func_prefix):
            have = _calls(n)
            miss = sorted(need - have)
            if miss:
                out.append((n.name, miss))
    return out
