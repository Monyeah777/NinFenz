"""源码原子：解析 Python / 找调用点。只回数据（AST 或 (名字, 行号) 清单）。

复用面：本仓 ast_missing 已在做「函数体里必须出现某类调用」的语法级判据，但它把
「解析 + 找调用」和「缺失清单」焊在一起。这里只留前一半，后一半归能力层。
"""
from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from core.atoms import fs

from . import _wake


def parse_py(path: Path) -> ast.AST | None:
    """解析为 AST；不在场 / 语法错误 → None（语法错误本身由调用方决定算不算失败）。"""
    _wake("code.parse_py")
    text = fs.read_text(path)
    if text is None:
        return None
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def find_calls(tree: ast.AST | None, names: Iterable[str] | None = None) -> list[tuple[str, int]]:
    """→ [(被调名, 行号)]，按 (行号, 名字) 排序；names 给定时只留这些名字。

    ast.walk 是广度优先，**顺序不稳定**于判据无益；排序后同一份源码永远给出同一份清单。
    """
    _wake("code.find_calls")
    if tree is None:
        return []
    wanted = None if names is None else {str(name) for name in names}
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        else:
            continue
        if wanted is None or name in wanted:
            out.append((name, node.lineno))
    return sorted(out, key=lambda item: (item[1], item[0]))
