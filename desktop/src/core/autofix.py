"""机械修复引擎（内部差距实证：doc_hygiene / purity_scan / schema_lint 都「只报告」，
仓库全域无 autofix/auto-fix/fix_file 命中——每次治理都要人手改）。

只做**机械且可判定安全**的修复，不做语义改写：

1. `last_updated`   —— 关键文档缺「> 最后更新：YYYY-MM-DD」位 → 标题行后补位
2. `instruction_mark` —— 指令档缺「⛔ 操作指令」标识 → 标题行后补标识行
3. `trailing_ws`    —— 行尾空白（含 tab）→ 去尾
4. `final_newline`  —— 文件末缺换行 → 补一个换行

纪律：修复只改机械面；语义/契约问题（纯度私货、schema 漂移、conformance 虚标）
一律不自动改——留给人判断（auto-fix 不替人做决定）。`dry_run` 只报将改什么。
"""
from __future__ import annotations

import os

from core import atomic_write
from datetime import date as _date
from typing import Dict, List

LAST_UPDATED_PREFIX = "> 最后更新："
INSTRUCTION_MARK = "⛔ 操作指令"
INSTRUCTION_LINE = ("> ⛔ 操作指令：阅读即执行——本文含可直接执行的命令/步骤/判定，"
                    "勿当资料阅读。")

#: 全部机械修复规则（顺序即应用顺序）
RULES = ("final_newline", "trailing_ws", "last_updated", "instruction_mark")


def _head_lines(text: str, n: int = 8) -> List[str]:
    return text.splitlines()[:n]


def _doc_flags(rel: str) -> tuple:
    """该文件是否在「必带最后更新」/「必带指令标识」清单里。"""
    try:
        from core import doc_hygiene as dh
        return rel in dh.REQUIRED_DOCS, rel in dh.INSTRUCTION_DOCS
    except Exception:
        return False, False


def _marker_rule_issues(required: bool, instruction: bool, head: list) -> List[Dict[str, str]]:
    """last_updated / instruction_mark 两条可修规则。"""
    out: List[Dict[str, str]] = []
    if required and not any(ln.startswith(LAST_UPDATED_PREFIX) for ln in head):
        out.append({"rule": "last_updated", "message": "缺「最后更新」位（头部 8 行内）"})
    if instruction and not any(INSTRUCTION_MARK in ln for ln in head):
        out.append({"rule": "instruction_mark", "message": "指令档缺「⛔ 操作指令」标识"})
    return out


def _text_shape_issues(text: str) -> List[Dict[str, str]]:
    """行尾空白 / 末尾换行两条可修规则。"""
    out: List[Dict[str, str]] = []
    if any(ln != ln.rstrip() for ln in text.splitlines()):
        out.append({"rule": "trailing_ws", "message": "存在行尾空白"})
    if text and not text.endswith("\n"):
        out.append({"rule": "final_newline", "message": "文件末尾缺换行"})
    return out


def lint_rules(path: str, text: str, root: str = ".") -> List[Dict[str, str]]:
    """给出该文件**可自动修**的问题（与 doc_hygiene 判据同源，不另造标准）。"""
    out: List[Dict[str, str]] = []
    rel = os.path.relpath(os.path.abspath(path),
                          os.path.abspath(root)).replace("\\", "/")
    required, instruction = _doc_flags(rel)
    head = _head_lines(text)
    return (_marker_rule_issues(required, instruction, head)
            + _text_shape_issues(text))


def _normalize_whitespace(text: str, applied: set) -> str:
    """行尾空白 / 末尾换行两条机械修（先统一换行符）。"""
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    if "trailing_ws" in applied:
        out = "\n".join(ln.rstrip() for ln in out.split("\n"))
    if "final_newline" in applied and out and not out.endswith("\n"):
        out += "\n"
    return out


def _head_insertions(applied: set, head: list, today: str) -> list:
    """需要插到头部的标识行（指令标识 / 最后更新）。"""
    needs = []
    if "instruction_mark" in applied and not any(INSTRUCTION_MARK in ln for ln in head):
        needs.append(INSTRUCTION_LINE)
    if "last_updated" in applied and not any(ln.startswith(LAST_UPDATED_PREFIX)
                                             for ln in head):
        needs.append(LAST_UPDATED_PREFIX + (today or _date.today().isoformat()))  # noqa: DTZ011 - 本地日历日期是有意语义（UTC 会在跨零点给出错误「今天」）
    return needs


def apply_rules(text: str, rules, today: str = "") -> str:
    """按规则顺序机械改写文本（纯函数，便于单测）。"""
    applied = set(rules)
    out = _normalize_whitespace(text, applied)
    lines = out.split("\n")
    needs = _head_insertions(applied, lines[:8], today)
    if needs:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines[insert_at:insert_at] = needs
        out = "\n".join(lines)
    return out


def fix_file(path: str, root: str = ".", today: str = "",
             dry_run: bool = False) -> Dict[str, object]:
    """对单文件执行机械修复 → {path, rules[], changed, applied}。"""
    with open(path, encoding="utf-8") as fh:
        before = fh.read()
    found = lint_rules(path, before, root)
    rules = [f["rule"] for f in found]
    if not rules:
        return {"path": path, "rules": [], "changed": False, "applied": []}
    after = apply_rules(before, rules, today)
    changed = after != before
    if changed and not dry_run:
        atomic_write.write_text(path, after)      # 机械修复也原子落盘（崩在中途不留截断件）
    return {"path": path, "rules": rules, "changed": changed,
            "applied": rules, "dry_run": dry_run}
