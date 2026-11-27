#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NF 离线审计执行器（纯 stdlib）。

读取 audit/rules.json 与 audit/scoring.json，对 --root 指定的源码树执行 script 型规则，
把证据写到 --out 目录（issues.json / meta.json / report.md），并打印总分与各维度分。

口径（与方案件一致）：
- script 规则离线执行；tool / manual 规则记 not-run：不计分、不写成 pass、报告单列。
- 维度分 = 100 - Σ min(命中数, 规则 penalty)，下限 0；总分 = Σ(维度分 × 权重)。
- 规则无目标文件记 no_targets；规则抛异常记 error。二者都不计分、不算通过，门禁视为失败。
- 同一输入重跑结果逐字节一致：文件遍历排序、命中排序、输出无墙钟时间。

用法：
    python audit/runner.py --root D:/d/tmp/nf-036 --commit aeae36b11 --out audit/evidence/aeae36b11
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

AUDIT_VERSION = "nf-audit-runner/1.0"
DEFAULT_RULES = "audit/rules.json"
DEFAULT_SCORING = "audit/scoring.json"

# 遍历时跳过的目录（构建产物 / 缓存 / VCS 元数据）。审计对象里这些不是源码。
SKIP_DIRS = {
    ".git", "build", ".gradle", "target", "node_modules", "results", "dist",
    ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    ".nf-cache", ".nf-logs", ".worktrees", "site", ".dart_tool", ".idea", ".cache",
    "htmlcov", ".tox", ".eggs", ".next", ".turbo", ".parcel-cache",
}

# 二进制扩展名不做文本解析（其余按 UTF-8 文本读；Dockerfile/.props/.gitignore 等无扩展名文件也要能读）。
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tif", ".tiff",
    ".so", ".dll", ".dylib", ".a", ".lib", ".o", ".obj", ".class", ".jar",
    ".ttf", ".otf", ".woff", ".woff2", ".zip", ".gz", ".tar", ".pdf", ".docx",
    ".xlsx", ".pptx", ".exe", ".bin", ".pyc", ".pyd", ".wasm", ".mp4", ".webm",
    ".mp3", ".wav", ".sqlite", ".db",
}
MAX_TEXT_BYTES = 4 * 1024 * 1024


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def to_posix(value) -> str:
    return str(value).replace("\\", "/")


def relpath(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def line_no(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def line_at(text: str, number: int) -> str:
    lines = text.splitlines()
    if 1 <= number <= len(lines):
        return lines[number - 1].strip()[:240]
    return ""


_GLOB_CACHE: dict[str, re.Pattern] = {}


def compile_glob(pattern: str) -> re.Pattern:
    """把仓库内使用的 POSIX glob 翻译成正则。

    支持 **（跨目录）、*（单段）、?、{a,b}；并让 **/ 能匹配零层目录
    （即 app/**/*.kt 也能命中 app/A.kt）。
    """
    if pattern in _GLOB_CACHE:
        return _GLOB_CACHE[pattern]
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        elif pattern[i] == "{":
            j = pattern.find("}", i)
            if j < 0:
                out.append(re.escape(pattern[i]))
                i += 1
            else:
                alts = pattern[i + 1:j].split(",")
                out.append("(?:" + "|".join(re.escape(a) for a in alts) + ")")
                i = j + 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    regex = re.compile("".join(out))
    _GLOB_CACHE[pattern] = regex
    return regex


def matches_any(regs, value: str) -> bool:
    return any(r.match(value) for r in regs)


def safe_compile(pattern: str):
    """规则作者可能写正则也可能写普通文本；非法正则回退为字面量匹配，避免规则整条 error。"""
    try:
        return re.compile(pattern)
    except re.error:
        return re.compile(re.escape(pattern))


class CheckError(RuntimeError):
    """规则自身无法执行（缺输入、schema 不可解析等），由引擎记为 error。"""


# ---------------------------------------------------------------------------
# 文本预处理（去注释 / 去字符串，保持行号不变）
# ---------------------------------------------------------------------------

def strip_comments(text: str, style: str) -> str:
    """把注释替换成空格，保留换行以便行号不变。style: c | py | auto。"""
    s = style
    if s == "auto":
        s = "py" if text.lstrip().startswith(("#!", "from ", "import ", "def ", '"""', "'''")) else "c"
    out = list(text)
    n = len(text)
    i = 0
    if s == "py":
        quote = None
        while i < n:
            c = text[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
                i += 1
                continue
            if c in ("'", '"'):
                if text.startswith(c * 3, i):
                    triple = c * 3
                    i += 3
                    while i < n and not text.startswith(triple, i):
                        if text[i] == "\\":
                            i += 1
                        i += 1
                    i = min(n, i + 3)
                    continue
                quote = c
                i += 1
                continue
            if c == "#":
                while i < n and text[i] != "\n":
                    out[i] = " "
                    i += 1
                continue
            i += 1
    else:
        quote = None
        block = False
        while i < n:
            c = text[i]
            if block:
                if text.startswith("*/", i):
                    out[i] = " "
                    out[i + 1] = " "
                    i += 2
                    block = False
                else:
                    if c != "\n":
                        out[i] = " "
                    i += 1
                continue
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
                i += 1
                continue
            if c in ("'", '"'):
                quote = c
                i += 1
                continue
            if text.startswith("//", i):
                while i < n and text[i] != "\n":
                    out[i] = " "
                    i += 1
                continue
            if text.startswith("/*", i):
                out[i] = " "
                out[i + 1] = " "
                i += 2
                block = True
                continue
            i += 1
    return "".join(out)


def strip_strings(text: str, style: str) -> str:
    """把字符串字面量内容替换为空格，保留引号与行号。用于只看代码结构的规则。"""
    if style == "py":
        pat = re.compile(
            r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\""
        )
    else:
        pat = re.compile(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"")
    return pat.sub(lambda m: m.group(0)[0] * len(m.group(0)), text)


# ---------------------------------------------------------------------------
# 源码上下文
# ---------------------------------------------------------------------------

class Context:
    def __init__(self, root: Path):
        self.root = root
        self.files: list[str] = []
        self._text_cache: dict[str, str] = {}
        self._walk()

    def _walk(self) -> None:
        collected: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                full = Path(dirpath) / name
                try:
                    rel = relpath(self.root, full)
                except ValueError:
                    continue
                collected.append(rel)
        self.files = sorted(collected)

    def candidates(self, globs, exclude=None) -> list[str]:
        if not globs:
            return []
        include = [compile_glob(g) for g in globs]
        excl = [compile_glob(g) for g in (exclude or [])]
        out = []
        for rel in self.files:
            if not matches_any(include, rel):
                continue
            if excl and matches_any(excl, rel):
                continue
            out.append(rel)
        return out

    def exists(self, rel: str) -> bool:
        try:
            return (self.root / rel).is_file()
        except OSError:
            return False

    def size(self, rel: str) -> int:
        try:
            return (self.root / rel).stat().st_size
        except OSError:
            return 0

    def text(self, rel: str) -> str:
        if rel in self._text_cache:
            return self._text_cache[rel]
        path = self.root / rel
        suffix = path.suffix.lower()
        if suffix in BINARY_EXTS:
            self._text_cache[rel] = ""
            return ""
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                self._text_cache[rel] = ""
                return ""
            data = path.read_bytes()
        except OSError:
            self._text_cache[rel] = ""
            return ""
        if b"\x00" in data[:2048]:
            self._text_cache[rel] = ""
            return ""
        text = data.decode("utf-8-sig", errors="replace")
        self._text_cache[rel] = text
        return text

    def lines(self, rel: str) -> list[str]:
        return self.text(rel).splitlines()


# ---------------------------------------------------------------------------
# 规则检查实现
# ---------------------------------------------------------------------------

CHECKS: dict[str, object] = {}


def check(name):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


def hit(path: str, line: int = 1, message: str = "", evidence: str = "") -> dict:
    return {
        "path": to_posix(path),
        "line": int(line) if line else 1,
        "message": message,
        "evidence": (evidence or "").strip()[:240],
    }


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _globs(params):
    return _as_list(params.get("globs") or [])


def _exclude(params):
    ex = params.get("exclude") or []
    if isinstance(ex, str):
        ex = [ex]
    return ex


def _brace_body(text: str, open_index: int):
    """从 '{' 位置做括号匹配，返回 (body, end_index, end_line)。"""
    depth = 0
    i = open_index
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_index + 1:i], i, line_no(text, i)
        i += 1
    return text[open_index + 1:], n - 1, line_no(text, n - 1)


KT_FUN_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|internal|protected|open|override|suspend|inline|"
    r"operator|tailrec|infix|external|actual|expect|abstract|final|const)\s+)*"
    r"fun\s+(?:<[^>\n]*>\s*)?(?:[\w.]+\.)?(\w+)\s*\("
)
RS_FUN_RE = re.compile(
    r"(?m)^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:const\s+)?(?:unsafe\s+)?"
    r"(?:extern\s+\")?fn\s+(\w+)\s*(?:<[^>\n]*>)?\s*\("
)
CS_FUN_RE = re.compile(
    r"(?m)^[ \t]*(?:(?:public|private|protected|internal|static|async|override|virtual|"
    r"sealed|partial|unsafe|new)\s+)*[\w<>\[\],.?]+\s+(\w+)\s*\("
)


def _extract_functions(text: str, ext: str, marker: str | None = None):
    """返回 (name, start_line, end_line, body, params_text) 列表。近似解析，够审计用。"""
    funcs = []
    regex = None
    if ext in (".kt", ".kts"):
        regex = KT_FUN_RE
    elif ext == ".rs":
        regex = RS_FUN_RE
    elif ext == ".cs":
        regex = CS_FUN_RE
    if regex is None:
        return funcs
    for m in regex.finditer(text):
        start = m.start()
        if marker:
            prefix = text[max(0, start - 400):start]
            if marker not in prefix:
                continue
        brace = text.find("{", m.end())
        paren = m.end() - 1
        depth = 0
        j = paren
        params_text = ""
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    params_text = text[paren + 1:j]
                    break
            j += 1
        if brace < 0:
            continue
        body, _, end_line = _brace_body(text, brace)
        funcs.append((m.group(1), line_no(text, start), end_line, body, params_text))
    return funcs


def _count_params(params_text: str) -> int:
    if not params_text.strip():
        return 0
    depth = 0
    count = 1
    for ch in params_text:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


def _py_functions(text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise CheckError(f"Python 语法解析失败: {exc}") from exc
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            segment = "\n".join(text.splitlines()[node.lineno - 1:end])
            args = _count_py_args(node.args)
            out.append((node.name, node.lineno, end, segment, args))
    return out


def _count_py_args(args: ast.arguments) -> int:
    return len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)


def _py_cyclomatic(text: str) -> int:
    if not text.strip():
        return 1
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 1
    count = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                             ast.With, ast.AsyncWith, ast.IfExp, ast.Assert, ast.Match)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            count += 1 + len(node.ifs)
    return count


def _iter_candidates(ctx: Context, params, extra_exclude=None):
    return ctx.candidates(_globs(params), list(_exclude(params)) + list(extra_exclude or []))


# --- 规模 / 复杂度 ---------------------------------------------------------

@check("file_line_limit")
def check_file_line_limit(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 400))
    allow = set(p.get("allow_files") or [])
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        n = text.count("\n") + 1
        if n > limit and rel not in allow:
            hits.append(hit(rel, limit + 1, f"文件 {n} 行，超过上限 {limit} 行", f"{n} lines"))
    return hits, files


@check("function_line_limit")
def check_function_line_limit(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 60))
    marker = p.get("marker")
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        ext = Path(rel).suffix.lower()
        try:
            if ext == ".py":
                funcs = _py_functions(text)
            else:
                funcs = _extract_functions(text, ext, marker=marker)
        except CheckError:
            continue
        for name, start, end, _body, _params in funcs:
            n = end - start + 1
            if n > limit:
                hits.append(hit(rel, start, f"函数 {name} {n} 行，超过上限 {limit} 行", name))
    return hits, files


@check("cyclomatic_proxy")
def check_cyclomatic_proxy(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 10))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        ext = Path(rel).suffix.lower()
        try:
            if ext == ".py":
                for name, start, _end, seg, _args in _py_functions(text):
                    cc = _py_cyclomatic(seg)
                    if cc > limit:
                        hits.append(hit(rel, start, f"函数 {name} 近似圈复杂度 {cc} > {limit}", name))
            else:
                for name, start, _end, body, _params in _extract_functions(text, ext):
                    stripped = strip_comments(body, "c")
                    cc = 1 + len(re.findall(r"\b(if|for|while|when|catch|match)\b|&&|\|\|", stripped))
                    if cc > limit:
                        hits.append(hit(rel, start, f"函数 {name} 近似圈复杂度 {cc} > {limit}", name))
        except CheckError:
            continue
    return hits, files


@check("max_function_params")
def check_max_function_params(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 6))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        ext = Path(rel).suffix.lower()
        try:
            if ext == ".py":
                for name, start, _end, _seg, count in _py_functions(text):
                    if count > limit:
                        hits.append(hit(rel, start, f"函数 {name} 参数 {count} 个 > {limit}", name))
            else:
                for name, start, _end, _body, params_text in _extract_functions(text, ext):
                    count = _count_params(params_text)
                    if count > limit:
                        hits.append(hit(rel, start, f"函数 {name} 参数 {count} 个 > {limit}", name))
        except CheckError:
            continue
    return hits, files


@check("nesting_depth")
def check_nesting_depth(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 6))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        ext = Path(rel).suffix.lower()
        if ext == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            max_depth = 0

            def walk(node, depth):
                nonlocal max_depth
                control = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith,
                           ast.Try, ast.Match)
                d = depth + 1 if isinstance(node, control) else depth
                max_depth = max(max_depth, d)
                for child in ast.iter_child_nodes(node):
                    walk(child, d)

            walk(tree, 0)
            if max_depth > limit:
                hits.append(hit(rel, 1, f"最大嵌套深度 {max_depth} > {limit}", ""))
        else:
            stripped = strip_comments(strip_strings(text, "c"), "c")
            depth = max_depth = 0
            for ch in stripped:
                if ch == "{":
                    depth += 1
                    max_depth = max(max_depth, depth)
                elif ch == "}":
                    depth = max(0, depth - 1)
            if max_depth > limit:
                hits.append(hit(rel, 1, f"最大括号嵌套深度 {max_depth} > {limit}", ""))
    return hits, files


@check("max_files_per_dir")
def check_max_files_per_dir(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit", 200))
    files = _iter_candidates(ctx, p)
    counts: dict[str, int] = {}
    for rel in files:
        parent = str(Path(rel).parent.as_posix())
        counts[parent] = counts.get(parent, 0) + 1
    hits = []
    for directory in sorted(counts):
        if counts[directory] > limit:
            hits.append(hit(directory + "/", 1, f"单目录文件数 {counts[directory]} > 上限 {limit}", directory))
    return hits, files


@check("pattern_count_min")
def check_pattern_count_min(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    pattern = re.compile(p.get("pattern", r"."), re.M)
    minimum = int(p.get("min_count", 1))
    files = _iter_candidates(ctx, p)
    total = sum(len(pattern.findall(ctx.text(rel))) for rel in files)
    if total < minimum:
        return [hit(p.get("label", "pattern"), 1, f"关键模式出现 {total} 次 < 下限 {minimum}", pattern.pattern)], files
    return [], files


@check("file_naming")
def check_file_naming(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    pattern = re.compile(p.get("pattern", r"[A-Za-z_][\w.-]*\.\w+"))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        if not pattern.fullmatch(Path(rel).name):
            hits.append(hit(rel, 1, f"文件名不符合约定: {Path(rel).name}", Path(rel).name))
    return hits, files


@check("package_declaration")
def check_package_declaration(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    pattern = re.compile(p.get("pattern", r"^\s*package\s+[\w.]+"), re.M)
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        if not pattern.search(text):
            hits.append(hit(rel, 1, "缺少 package 声明", ""))
    return hits, files


@check("non_null_assertion")
def check_non_null_assertion(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    per_file_limit = int(p.get("per_file_limit", 2))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        stripped = strip_comments(strip_strings(text, "c"), "c")
        count = len(re.findall(r"!!(?!=)", stripped))
        if count > per_file_limit:
            hits.append(hit(rel, 1, f"非空断言 !! 出现 {count} 次 > {per_file_limit}", f"{count} x !!"))
    return hits, files


# --- 架构 / 边界 -----------------------------------------------------------

@check("import_boundary")
def check_import_boundary(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    path_glob = _as_list(p.get("path_glob") or p.get("globs") or [])
    must_contain = p.get("file_must_contain")
    prefixes = p.get("forbid_import_prefix") or []
    files = ctx.candidates(path_glob)
    if must_contain:
        files = [f for f in files if must_contain in f]
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        ext = Path(rel).suffix.lower()
        if ext == ".py":
            line_re = re.compile(r"^\s*(?:from|import)\s+([\w.]+)")
        else:
            line_re = re.compile(r"^\s*import\s+([\w.]+)")
        module_level_only = bool(p.get("module_level_only"))
        for idx, line in enumerate(text.splitlines(), 1):
            if module_level_only and line[:1] in (" ", "\t"):
                continue
            m = line_re.match(line)
            if not m:
                continue
            target = m.group(1)
            for prefix in prefixes:
                if target == prefix or target.startswith(prefix):
                    hits.append(hit(rel, idx, f"越界 import: {target}（禁止前缀 {prefix}）", line.strip()))
                    break
    return hits, files


@check("import_cycle")
def check_import_cycle(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    internal_root = p.get("internal_prefix", "dev.ninfenz")
    pkg_re = re.compile(r"^\s*package\s+([\w.]+)", re.M)
    imp_re = re.compile(r"^\s*import\s+([\w.]+)", re.M)
    graph: dict[str, set[str]] = {}
    rep: dict[str, str] = {}
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        pm = pkg_re.search(text)
        if not pm:
            continue
        pkg = pm.group(1)
        rep.setdefault(pkg, rel)
        graph.setdefault(pkg, set())
        for target in imp_re.findall(text):
            if not target.startswith(internal_root):
                continue
            graph[pkg].add(target.rsplit(".", 1)[0])
    known = set(graph)
    clean = {}
    for pkg, targets in graph.items():
        clean[pkg] = {t for t in targets if t in known}
    color: dict[str, int] = {}
    cycles: list[list[str]] = []

    def dfs(node, stack):
        color[node] = 1
        stack.append(node)
        for nxt in sorted(clean.get(node, ())):
            if color.get(nxt, 0) == 1:
                idx = stack.index(nxt)
                cycles.append(stack[idx:] + [nxt])
            elif color.get(nxt, 0) == 0:
                dfs(nxt, stack)
        stack.pop()
        color[node] = 2

    for pkg in sorted(clean):
        if color.get(pkg, 0) == 0:
            dfs(pkg, [])
    allow_root = set(p.get("allow_root_packages") or [])
    allow_prefixes = tuple(p.get("allow_prefixes") or [])
    seen = set()
    hits = []
    for cyc in cycles:
        key = tuple(sorted(cyc))
        if key in seen:
            continue
        pkgs = set(cyc)
        # 根包（R/BuildConfig/MainActivity）与 UI 子包内部的相互引用是单模块 Android/Compose
        # 的固有结构；规则只追究跨层成环。
        if pkgs & allow_root:
            continue
        if allow_prefixes and all(
            any(pkg == pre or pkg.startswith(pre + ".") for pre in allow_prefixes) for pkg in pkgs
        ):
            continue
        seen.add(key)
        chain = " -> ".join(cyc)
        hits.append(hit(rep.get(cyc[0], files[0]), 1, f"包间依赖成环: {chain}", chain))
    return hits, files


@check("unused_gradle_dependency")
def check_unused_gradle_dependency(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    gradle_file = p.get("file") or "app/android/app/build.gradle.kts"
    if not ctx.exists(gradle_file):
        raise CheckError(f"Gradle 文件不存在: {gradle_file}")
    text = ctx.text(gradle_file)
    mapping = p.get("dependency_package_map") or {}
    source_globs = p.get("source_globs") or ["app/android/**/src/main/**/*.kt", "app/android/**/src/test/**/*.kt"]
    source_files = ctx.candidates(source_globs)
    imports = "\n".join(ctx.text(f) for f in source_files)
    deps = re.findall(r"(?:implementation|testImplementation|debugImplementation|androidTestImplementation)\s*\(\s*\"([^\"]+)\"", text)
    hits = []
    for dep in deps:
        prefixes = [prefix for key, prefix in mapping.items() if key in dep]
        if not prefixes:
            continue
        if not any(prefix in imports for prefix in prefixes):
            hits.append(hit(gradle_file, 1, f"Gradle 依赖可能未被使用: {dep}", dep))
    return hits, [gradle_file]


# --- 文本禁用 / 必需 -------------------------------------------------------

@check("forbid_text")
def check_forbid_text(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    patterns = [safe_compile(x) for x in _as_list(p.get("patterns"))]
    files = _iter_candidates(ctx, p)
    do_strip = bool(p.get("strip_comments"))
    strip_strings_flag = bool(p.get("strip_strings"))
    allowed = [g for g in (p.get("allowed_paths") or [])]
    hits = []
    for rel in files:
        if any(fnmatch.fnmatch(rel, g) for g in allowed):
            continue
        raw = ctx.text(rel)
        if not raw:
            continue
        text = raw
        suffix = Path(rel).suffix.lower()
        if do_strip or strip_strings_flag:
            style = "py" if suffix == ".py" else "c"
            if do_strip:
                text = strip_comments(text, style)
            if strip_strings_flag:
                text = strip_strings(text, style)
        for idx, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                m = pat.search(line)
                if m:
                    evidence = line_at(raw, idx) or m.group(0)
                    hits.append(hit(rel, idx, f"命中禁用模式 /{pat.pattern}/", evidence))
                    break
    return hits, files


@check("forbid_regex_multiline")
def check_forbid_regex_multiline(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    patterns = [re.compile(x, re.M) for x in (p.get("patterns") or [])]
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for pat in patterns:
            for m in pat.finditer(text):
                hits.append(hit(rel, line_no(text, m.start()), f"命中禁用模式 /{pat.pattern}/", m.group(0)[:200]))
    return hits, files


@check("require_text")
def check_require_text(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target:
        raise CheckError("require_text 需要 params.file")
    if not ctx.exists(target):
        return [hit(target, 1, "必需文件不存在", target)], [target]
    text = ctx.text(target)
    hits = []
    for pat in (p.get("patterns") or []):
        if not re.search(pat, text, re.M):
            hits.append(hit(target, 1, f"缺少必需配置模式: {pat}", pat))
    return hits, [target]


@check("require_json_keys")
def check_require_json_keys(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target:
        raise CheckError("require_json_keys 需要 params.file")
    if not ctx.exists(target):
        return [hit(target, 1, "必需文件不存在", target)], [target]
    try:
        data = json.loads(ctx.text(target))
    except json.JSONDecodeError as exc:
        raise CheckError(f"JSON 解析失败: {target}: {exc}") from exc
    hits = []
    for key in (p.get("keys") or []):
        if key not in data:
            hits.append(hit(target, 1, f"缺少必需字段: {key}", key))
    return hits, [target]


@check("required_file_presence")
def check_required_file_presence(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = p.get("files") or []
    hits = []
    for rel in files:
        if not ctx.exists(rel) or ctx.size(rel) == 0:
            hits.append(hit(rel, 1, "必需文件缺失或为空", rel))
    return hits, list(files)


@check("required_any_file")
def check_required_any_file(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = p.get("files") or []
    present = [rel for rel in files if ctx.exists(rel) and ctx.size(rel) > 0]
    if present:
        return [], list(files)
    return [hit(files[0] if files else "", 1, "候选文件全部缺失: " + ", ".join(files), "")], list(files)


@check("file_absent")
def check_file_absent(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = [hit(rel, 1, "禁止出现的文件存在", rel) for rel in files]
    return hits, files


@check("conditional_required_file")
def check_conditional_required_file(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    condition_file = p.get("file")
    require_files = p.get("require_files") or []
    if not condition_file or not ctx.exists(condition_file):
        return [], [condition_file] if condition_file else []
    text = ctx.text(condition_file)
    pattern = p.get("condition_pattern")
    if pattern and not re.search(pattern, text, re.M):
        return [], [condition_file]
    hits = []
    for rel in require_files:
        if not ctx.exists(rel) or ctx.size(rel) == 0:
            hits.append(hit(rel, 1, f"条件成立但文件缺失: {rel}", pattern or ""))
    return hits, [condition_file] + list(require_files)


@check("min_file_count")
def check_min_file_count(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    minimum = int(p.get("min_count", 1))
    if len(files) < minimum:
        return [hit(_globs(p)[0] if _globs(p) else "", 1, f"命中文件 {len(files)} 个 < 下限 {minimum}", "")], files
    return [], files


# --- 错误处理 / 并发 / 安全 ------------------------------------------------

@check("empty_catch")
def check_empty_catch(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    marker = (p.get("allow_marker") or "").strip()
    for rel in files:
        raw = ctx.text(rel)
        if not raw:
            continue
        ext = Path(rel).suffix.lower()
        if ext == ".py":
            try:
                tree = ast.parse(raw)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                handled = node.type
                generic = handled is None
                if isinstance(handled, ast.Name) and handled.id in ("Exception", "BaseException"):
                    generic = True
                if isinstance(handled, ast.Tuple) and any(
                        isinstance(x, ast.Name) and x.id in ("Exception", "BaseException") for x in handled.elts):
                    generic = True
                if generic and all(isinstance(stmt, ast.Pass) for stmt in node.body):
                    if marker and re.search(marker, "\n".join(raw.splitlines()[node.lineno - 1:node.end_lineno])):
                        continue
                    hits.append(hit(rel, node.lineno, "空 except（仅 pass，兜底异常被吞）", line_at(raw, node.lineno)))
            continue
        for m in re.finditer(r"catch\s*(?:\([^)]*\))?\s*\{", raw):
            brace = raw.find("{", m.start())
            body, _end, _line = _brace_body(raw, brace)
            stripped = strip_comments(body, "c").strip()
            if stripped:
                continue
            if marker and re.search(marker, body):
                continue
            hits.append(hit(rel, line_no(raw, m.start()), "空 catch（无恢复/上报或无 best-effort 说明）", line_at(raw, line_no(raw, m.start()))))
    return hits, files


@check("python_bare_except")
def check_python_bare_except(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    pat = re.compile(r"^\s*except\s*:")
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if pat.match(line):
                hits.append(hit(rel, idx, "裸 except:", line.strip()))
    return hits, files


@check("rust_unwrap")
def check_rust_unwrap(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    aggregate_limit = p.get("aggregate_limit")
    per_file_limit = int(p.get("per_file_limit", 10))
    hits = []
    total = 0
    top = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        text = strip_rust_test_modules(text)
        stripped = strip_comments(strip_strings(text, "c"), "c")
        count = len(re.findall(r"\.(?:unwrap|expect)\s*\(", stripped))
        if not count:
            continue
        total += count
        top.append((count, rel))
        if aggregate_limit is None and count > per_file_limit:
            hits.append(hit(rel, 1, f"unwrap/expect {count} 次 > {per_file_limit}", f"{count} 次"))
    if aggregate_limit is not None and total > int(aggregate_limit):
        top.sort(reverse=True)
        sample = ", ".join(f"{f}({n})" for n, f in top[:5])
        hits.append(hit(top[0][1] if top else "", 1, f"生产路径 unwrap/expect 共 {total} 次 > 上限 {aggregate_limit}", sample))
    return hits, files



def strip_rust_test_modules(text: str) -> str:
    """把 #[cfg(test)] mod tests { ... } 整块清空（保留行号）；E-008/E-010 只看生产路径。"""
    lines = text.splitlines(keepends=True)
    out = list(lines)
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("#[cfg(test)]"):
            j = i + 1
            while j < len(lines) and "mod " not in lines[j]:
                j += 1
            if j < len(lines) and "{" in lines[j]:
                depth = 0
                k = j
                while k < len(lines):
                    depth += lines[k].count("{") - lines[k].count("}")
                    if depth <= 0:
                        break
                    k += 1
                for x in range(i, min(k + 1, len(lines))):
                    out[x] = chr(10) if lines[x].endswith(chr(10)) else ""
                i = k + 1
                continue
        i += 1
    return "".join(out)


@check("rust_panic")
def check_rust_panic(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        text = strip_rust_test_modules(text)
        marker = p.get("allow_marker")
        count = 0
        raw_lines = text.splitlines()
        for idx, line in enumerate(raw_lines):
            if not re.search(r"\b(?:panic!|todo!|unimplemented!)\s*\(", line):
                continue
            window = "\n".join(raw_lines[max(0, idx - 3):idx + 1])
            if marker and re.search(marker, window):
                continue
            count += 1
        if count:
            hits.append(hit(rel, 1, f"panic!/todo!/unimplemented! {count} 次", f"{count} 次"))
    return hits, files


@check("rust_unsafe")
def check_rust_unsafe(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("per_file_limit", 3))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        stripped = strip_comments(strip_strings(text, "c"), "c")
        count = len(re.findall(r"\bunsafe\b", stripped))
        if count > limit:
            hits.append(hit(rel, 1, f"unsafe 出现 {count} 次 > {limit}", f"{count} 次"))
    return hits, files


SINKS = {
    "shell": ("run", "call", "check_call", "check_output", "Popen", "system", "popen"),
}


@check("python_security_sink")
def check_python_security_sink(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    wanted = set(p.get("sinks") or ["shell", "yaml_load", "pickle", "marshal", "eval", "exec"])
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
            base = ""
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                base = fn.value.id
            lineno = getattr(node, "lineno", 1)
            marker = p.get("allow_marker")
            if marker:
                window = "\n".join(text.splitlines()[max(0, lineno - 5):lineno + 3])
                if re.search(marker, window):
                    continue
            if "shell" in wanted and name in SINKS["shell"]:
                if base == "subprocess" and name in ("run", "call", "check_call", "check_output", "Popen"):
                    kw = {k.arg: k.value for k in node.keywords if k.arg}
                    shell = kw.get("shell")
                    if isinstance(shell, ast.Constant) and shell.value is True:
                        hits.append(hit(rel, lineno, "subprocess 使用 shell=True", line_at(text, lineno)))
                elif base == "os" and name in ("system", "popen"):
                    hits.append(hit(rel, lineno, f"os.{name} 执行外部命令", line_at(text, lineno)))
            if "yaml_load" in wanted and name == "load" and base == "yaml":
                hits.append(hit(rel, lineno, "yaml.load 未指定 SafeLoader", line_at(text, lineno)))
            if "pickle" in wanted and name in ("load", "loads") and base == "pickle":
                hits.append(hit(rel, lineno, "pickle 反序列化不可信数据", line_at(text, lineno)))
            if "marshal" in wanted and name in ("load", "loads") and base == "marshal":
                hits.append(hit(rel, lineno, "marshal 反序列化不可信数据", line_at(text, lineno)))
            if "eval" in wanted and name == "eval" and base == "":
                hits.append(hit(rel, lineno, "eval 执行动态代码", line_at(text, lineno)))
            if "exec" in wanted and name == "exec" and base == "":
                hits.append(hit(rel, lineno, "exec 执行动态代码", line_at(text, lineno)))
    return hits, files


@check("python_open_encoding")
def check_python_open_encoding(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"):
                continue
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            else:
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = kw.value.value
            if not isinstance(mode, str) or "b" in mode:
                continue
            if any(kw.arg == "encoding" for kw in node.keywords):
                continue
            lineno = getattr(node, "lineno", 1)
            hits.append(hit(rel, lineno, f"open(mode={mode!r}) 未显式 encoding", line_at(text, lineno)))
    return hits, files


@check("python_open_context")
def check_python_open_context(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        with_ids = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    with_ids.add(id(item.context_expr))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"):
                continue
            if id(node) in with_ids:
                continue
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            if isinstance(mode, str) and "b" not in mode and any(c in mode for c in "wa+"):
                lineno = getattr(node, "lineno", 1)
                hits.append(hit(rel, lineno, "文本写文件未使用上下文管理器", line_at(text, lineno)))
    return hits, files


@check("python_subprocess_timeout")
def check_python_subprocess_timeout(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess"):
                continue
            if fn.attr not in ("run", "call", "check_call", "check_output", "Popen"):
                continue
            if fn.attr in (p.get("exclude_calls") or []):
                continue
            if any(kw.arg == "timeout" for kw in node.keywords):
                continue
            lineno = getattr(node, "lineno", 1)
            hits.append(hit(rel, lineno, f"subprocess.{fn.attr} 未设置 timeout", line_at(text, lineno)))
    return hits, files


@check("python_swallow_exception")
def check_python_swallow_exception(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # 只审计兜底型 handler：裸 except 或 Exception/BaseException
            handled = node.type
            generic = False
            if handled is None:
                generic = True
            elif isinstance(handled, ast.Name) and handled.id in ("Exception", "BaseException"):
                generic = True
            elif isinstance(handled, ast.Tuple) and any(
                    isinstance(x, ast.Name) and x.id in ("Exception", "BaseException") for x in handled.elts):
                generic = True
            if not generic:
                continue
            body = node.body
            if not body:
                continue

            def swallows(stmt):
                if isinstance(stmt, (ast.Pass, ast.Continue)):
                    return True
                if isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)):
                    return True
                return False

            if all(swallows(stmt) for stmt in body):
                marker = p.get("allow_marker")
                if marker:
                    window = "\n".join(text.splitlines()[node.lineno - 1:getattr(node, "end_lineno", node.lineno)])
                    if re.search(marker, window):
                        continue
                hits.append(hit(rel, node.lineno, "异常被静默吞掉（仅 pass/continue/return None）", line_at(text, node.lineno)))
    return hits, files


@check("python_unbounded_cache")
def check_python_unbounded_cache(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if re.search(r"lru_cache\s*\(\s*\)", line) or re.search(r"lru_cache\s*\(\s*maxsize\s*=\s*None", line):
                hits.append(hit(rel, idx, "无界缓存 lru_cache（maxsize=None）", line.strip()))
    return hits, files


# --- 错误码 / 安全扫描 ------------------------------------------------------

@check("error_code_registry")
def check_error_code_registry(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    schema_rel = p.get("schema") or "app/schema/error_codes.json"
    if not ctx.exists(schema_rel):
        raise CheckError(f"错误码 schema 不存在: {schema_rel}")
    try:
        data = json.loads(ctx.text(schema_rel))
    except json.JSONDecodeError as exc:
        raise CheckError(f"错误码 schema 解析失败: {exc}") from exc
    codes = {str(item.get("code")) for item in data.get("codes", []) if item.get("code")}
    pattern = re.compile(p.get("pattern", r"NF-[A-Z0-9]+-\d{3}"))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            for m in pattern.finditer(line):
                token = m.group(0)
                if token not in codes:
                    hits.append(hit(rel, idx, f"错误码未在册: {token}", line.strip()))
    return hits, files


@check("error_codes_shape")
def check_error_codes_shape(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    schema_rel = p.get("schema") or "app/schema/error_codes.json"
    if not ctx.exists(schema_rel):
        raise CheckError(f"错误码 schema 不存在: {schema_rel}")
    try:
        data = json.loads(ctx.text(schema_rel))
    except json.JSONDecodeError as exc:
        raise CheckError(f"错误码 schema 解析失败: {exc}") from exc
    codes = data.get("codes") or []
    hits = []
    seen = set()
    required = p.get("required_fields") or ["code", "severity", "exit", "message", "fix"]
    for item in codes:
        code = item.get("code", "")
        for field in required:
            if not item.get(field) and item.get(field) != 0:
                hits.append(hit(schema_rel, 1, f"错误码 {code} 缺字段 {field}", code))
        if code in seen:
            hits.append(hit(schema_rel, 1, f"错误码重复: {code}", code))
        seen.add(code)
        exit_code = item.get("exit")
        allowed = p.get("allowed_exit")
        if isinstance(exit_code, int) and allowed and exit_code not in allowed:
            hits.append(hit(schema_rel, 1, f"错误码 {code} exit={exit_code} 不在 {allowed}", code))
        if item.get("severity") and p.get("allowed_severity"):
            if item.get("severity") not in p["allowed_severity"]:
                hits.append(hit(schema_rel, 1, f"错误码 {code} severity 非法: {item.get('severity')}", code))
    return hits, [schema_rel]


@check("secret_scan")
def check_secret_scan(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    patterns = [re.compile(x) for x in (p.get("patterns") or [])]
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    hits.append(hit(rel, idx, f"疑似密钥/口令: /{pat.pattern}/", line.strip()))
                    break
    return hits, files


@check("no_internet_permission")
def check_no_internet_permission(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    forbidden = p.get("permissions") or ["android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE"]
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if "uses-permission" not in line:
                continue
            if 'tools:node="remove"' in line or "tools:node='remove'" in line:
                continue
            for perm in forbidden:
                if perm in line:
                    hits.append(hit(rel, idx, f"Manifest 声明网络权限且未移除: {perm}", line.strip()))
                    break
    return hits, files


@check("manifest_attrs")
def check_manifest_attrs(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"Manifest 不存在: {target}")
    text = ctx.text(target)
    hits = []
    for item in (p.get("required") or []):
        name = item.get("name")
        value = item.get("value")
        if not name:
            continue
        if not re.search(rf'{re.escape(name)}\s*=\s*["\']{re.escape(str(value))}["\']', text):
            hits.append(hit(target, 1, f"Manifest 缺少 {name}={value}", item.get("why", "")))
    return hits, [target]


@check("manifest_exported_allowlist")
def check_manifest_exported_allowlist(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"Manifest 不存在: {target}")
    text = ctx.text(target)
    allow = set(p.get("allowlist") or [])
    hits = []
    for m in re.finditer(r"<activity\b[^>]*>", text, re.S):
        block = m.group(0)
        if 'android:exported="true"' not in block and "android:exported='true'" not in block:
            continue
        name_m = re.search(r'android:name="([^"]+)"', block)
        name = name_m.group(1) if name_m else "?"
        if name not in allow and name.lstrip(".") not in allow:
            hits.append(hit(target, line_no(text, m.start()), f"exported Activity 未在允许清单: {name}", name))
    return hits, [target]


@check("file_provider_paths")
def check_file_provider_paths(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"FileProvider 配置不存在: {target}")
    text = ctx.text(target)
    hits = []
    for tag in (p.get("required_tags") or []):
        if f"<{tag}" not in text:
            hits.append(hit(target, 1, f"FileProvider 缺少受限路径标签 <{tag}>", tag))
    if p.get("forbid_root_path") and re.search(r"<root-path\b", text):
        hits.append(hit(target, 1, "FileProvider 暴露 root-path（范围过大）", "root-path"))
    return hits, [target]


# --- 构建 / 供应链 ---------------------------------------------------------

@check("gradle_flag")
def check_gradle_flag(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"Gradle 文件不存在: {target}")
    text = ctx.text(target)
    hits = []
    for pat in (p.get("patterns") or []):
        if not re.search(pat, text, re.M):
            hits.append(hit(target, 1, f"缺少必需构建开关: {pat}", pat))
    return hits, [target]


@check("dynamic_versions")
def check_dynamic_versions(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    patterns = [re.compile(x) for x in (p.get("patterns") or [])]
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            for pat in patterns:
                if pat.search(line):
                    hits.append(hit(rel, idx, f"动态/浮动版本: /{pat.pattern}/", line.strip()))
                    break
    return hits, files


@check("lockfile_presence")
def check_lockfile_presence(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = p.get("files") or []
    hits = []
    for rel in files:
        if not ctx.exists(rel) or ctx.size(rel) == 0:
            hits.append(hit(rel, 1, "依赖锁文件缺失或为空", rel))
    return hits, list(files)


@check("workflow_action_pinning")
def check_workflow_action_pinning(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    sha_re = re.compile(r"^[0-9a-f]{40}$")
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            m = re.search(r"\buses:\s*([^\s#]+)", line)
            if not m:
                continue
            ref = m.group(1).strip("\"'")
            if ref.startswith("./") or ref.startswith("docker://"):
                continue
            if "@" not in ref:
                hits.append(hit(rel, idx, f"action 未钉版本: {ref}", line.strip()))
                continue
            version = ref.rsplit("@", 1)[1]
            if not sha_re.match(version):
                hits.append(hit(rel, idx, f"action 未钉 commit SHA: {ref}", line.strip()))
    return hits, files


@check("dependency_pins")
def check_dependency_pins(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    pinned = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[^\]]+\])?\s*(?:==|===)\s*[^\s;]+")
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if raw.startswith((" ", "\t")) or line.startswith("--"):
                continue
            if line.startswith(("-r ", "-c ")):
                continue
            if not pinned.match(line):
                hits.append(hit(rel, idx, "依赖未精确 pin: " + line[:80], line))
    return hits, files


@check("third_party_notice_coverage")
def check_third_party_notice_coverage(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    notices_rel = p.get("file") or "THIRD-PARTY-NOTICES.md"
    if not ctx.exists(notices_rel):
        return [hit(notices_rel, 1, "第三方声明文件缺失", notices_rel)], [notices_rel]
    notices = ctx.text(notices_rel).lower().replace("_", "-").replace(".", "-")
    req_files = ctx.candidates(p.get("requirement_globs") or [".github/requirements-*.txt"])
    names = set()
    for rel in req_files:
        for line in ctx.text(rel).splitlines():
            m = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*==", line.strip())
            if m:
                names.add(m.group(1).lower().replace("_", "-").replace(".", "-"))
    hits = []
    for name in sorted(names):
        if name not in notices:
            hits.append(hit(notices_rel, 1, f"第三方声明缺少依赖: {name}", name))
    return hits, [notices_rel] + req_files


@check("absolute_path_literal")
def check_absolute_path_literal(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    patterns = [re.compile(x) for x in (p.get("patterns") or [])]
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pat in patterns:
                if pat.search(line):
                    hits.append(hit(rel, idx, "源码硬编码本机绝对路径", line.strip()))
                    break
    return hits, files


@check("large_file")
def check_large_file(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    limit = int(p.get("limit_bytes", 3 * 1024 * 1024))
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        size = ctx.size(rel)
        if size > limit:
            hits.append(hit(rel, 1, f"文件 {size} 字节 > 上限 {limit}", f"{size} bytes"))
    return hits, files


# --- 测试 / 文档 / i18n ----------------------------------------------------

@check("test_file_ratio")
def check_test_file_ratio(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    source = ctx.candidates(p.get("source_globs") or [])
    tests = ctx.candidates(p.get("test_globs") or [])
    minimum = float(p.get("min_ratio", 0.5))
    if not source:
        return [], source
    ratio = len(tests) / len(source)
    if ratio < minimum:
        return [hit(p.get("label", "tests"), 1, f"测试文件/源文件 = {len(tests)}/{len(source)} = {ratio:.2f} < {minimum}", "")], source
    return [], source


@check("skip_markers")
def check_skip_markers(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    patterns = [re.compile(x) for x in (p.get("patterns") or [r"@unittest\.skip", r"pytest\.mark\.skip", r"@Ignore\b"])]
    limit = int(p.get("limit", 20))
    total = 0
    per_file = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        count = sum(len(pat.findall(text)) for pat in patterns)
        if count:
            total += count
            per_file.append((count, rel))
    if total > limit:
        per_file.sort(reverse=True)
        sample = ", ".join(f"{f}({n})" for n, f in per_file[:5])
        return [hit(per_file[0][1] if per_file else "", 1, f"跳过测试标记共 {total} 处 > 上限 {limit}", sample)], files
    return [], files


@check("test_assertions")
def check_test_assertions(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        if not re.search(r"\b(self\.assert\w*|assert\s+|assertEqual|assertTrue|assertIs|expect\()", text):
            hits.append(hit(rel, 1, "测试文件无断言", rel))
    return hits, files


@check("test_naming")
def check_test_naming(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    pattern = re.compile(p.get("pattern", r"test_.*\.py"))
    exclude_names = set(p.get("exclude_names") or ["__init__.py"])
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        name = Path(rel).name
        if name in exclude_names:
            continue
        if not pattern.fullmatch(name):
            hits.append(hit(rel, 1, f"测试文件命名不符合约定: {name}", name))
    return hits, files


@check("rust_test_presence")
def check_rust_test_presence(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    source = ctx.candidates(p.get("source_globs") or [])
    marker = re.compile(p.get("marker_pattern", r"#\[(?:test|cfg\(test\))\]"))
    with_tests = [rel for rel in source if marker.search(ctx.text(rel))]
    ratio = len(with_tests) / len(source) if source else 0.0
    minimum = float(p.get("min_ratio", 0.3))
    if source and ratio < minimum:
        return [hit(p.get("label", "rust"), 1, f"含测试标记的 Rust 文件占比 {ratio:.2f} < {minimum}", "")], source
    return [], source


@check("go_test_presence")
def check_go_test_presence(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    source = ctx.candidates(p.get("source_globs") or p.get("globs") or [])
    excluded = [d.rstrip("/") + "/" for d in (p.get("exclude_dirs") or [])]
    dirs = sorted({str(Path(f).parent.as_posix()) for f in source})
    hits = []
    for directory in dirs:
        if any((directory + "/").startswith(d) for d in excluded):
            continue
        test_glob = (directory + "/*_test.go").lstrip("/")
        if not ctx.candidates([test_glob]):
            hits.append(hit(directory, 1, "Go 包无任何测试文件", directory))
    return hits, source


@check("dotnet_test_presence")
def check_dotnet_test_presence(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    source = ctx.candidates(p.get("source_globs") or [])
    tests = ctx.candidates(p.get("test_globs") or [])
    accepted = ctx.candidates(p.get("accept_globs") or [])
    if not tests and not accepted:
        return [hit(p.get("label", "engine/dotnet"), 1, "未发现 .NET 测试项目/测试源（含引擎内自测）", "")], source
    return [], source + accepted


@check("todo_markers")
def check_todo_markers(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    pattern = re.compile(p.get("pattern", r"\b(?:TODO|FIXME|HACK|XXX)\b"))
    limit = int(p.get("limit", 20))
    total = 0
    per_file = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        count = len(pattern.findall(text))
        if count:
            total += count
            per_file.append((count, rel))
    if total > limit:
        per_file.sort(reverse=True)
        sample = ", ".join(f"{f}({n})" for n, f in per_file[:5])
        return [hit(per_file[0][1], 1, f"TODO/FIXME/HACK 共 {total} 处 > 上限 {limit}", sample)], files
    return [], files


@check("duplicate_block")
def check_duplicate_block(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    window = int(p.get("window", 8))
    per_file_limit = int(p.get("per_file_limit", 5))
    files = _iter_candidates(ctx, p)

    def normalize(text):
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith(("//", "*", "/*", "import ", "package ")):
                continue
            if s.startswith("@"):
                continue
            s = re.sub(r"\s+", " ", s)
            if len(s) >= 3:
                out.append(s)
        return out

    index: dict[str, set[str]] = {}
    for rel in files:
        lines = normalize(ctx.text(rel))
        if len(lines) < window:
            continue
        for i in range(len(lines) - window + 1):
            key = "\n".join(lines[i:i + window])
            if len(key) < 160:
                continue
            index.setdefault(key, set()).add(rel)
    dup_count: dict[str, int] = {}
    for key, members in index.items():
        if len(members) > 1:
            for rel in members:
                dup_count[rel] = dup_count.get(rel, 0) + 1
    hits = []
    for rel in sorted(dup_count):
        count = dup_count[rel]
        if count > per_file_limit:
            hits.append(hit(rel, 1, f"重复 {window} 行块命中 {count} 处 > {per_file_limit}", f"{count} 个重复窗口"))
    return hits, files


@check("json_validity")
def check_json_validity(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            hits.append(hit(rel, exc.lineno, f"JSON 解析失败: {exc.msg}", exc.doc[exc.pos:exc.pos + 80] if exc.doc else ""))
    return hits, files


@check("xml_validity")
def check_xml_validity(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as exc:
            pos = getattr(exc, "position", (1, 0)) or (1, 0)
            hits.append(hit(rel, int(pos[0]), f"XML 解析失败: {exc}", ""))
    return hits, files


@check("toml_validity")
def check_toml_validity(ctx: Context, rule: dict):
    import tomllib
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            hits.append(hit(rel, 1, f"TOML 解析失败: {exc}", ""))
    return hits, files


@check("schema_dollar_schema")
def check_schema_dollar_schema(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            hits.append(hit(rel, 1, "JSON 解析失败，无法校验 schema 标识", ""))
            continue
        keys = p.get("any_keys") or ["$schema", "schema"]
        if not any(k in data for k in keys):
            hits.append(hit(rel, 1, "schema 文件缺少 $schema/schema 标识", ""))
    return hits, files


@check("chinese_literal")
def check_chinese_literal(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    allowlist = set(p.get("allowlist_basenames") or [])
    exclude_segments = p.get("exclude_segments") or []
    limit = int(p.get("limit", 0))
    cjk = re.compile(r"\"(?:\\.|[^\"\\\n])*[\u4e00-\u9fff](?:\\.|[^\"\\\n])*\"")
    hits = []
    for rel in files:
        name = Path(rel).name
        if name in allowlist:
            continue
        if any(seg in rel for seg in exclude_segments):
            continue
        raw = ctx.text(rel)
        if not raw:
            continue
        stripped = strip_comments(raw, "c")
        found = cjk.findall(stripped)
        if len(found) > limit:
            sample = found[0] if found else ""
            hits.append(hit(rel, 1, f"硬编码中文字面量 {len(found)} 处 > {limit}", sample))
    return hits, files


@check("compose_icon_content_description")
def check_compose_icon_content_description(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    window = int(p.get("window_lines", 6))
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if not re.search(r"\bIcon\s*\(", line):
                continue
            ctx_text = "\n".join(lines[idx:idx + window])
            if "contentDescription" not in ctx_text:
                hits.append(hit(rel, idx + 1, "Icon 缺少 contentDescription", line.strip()))
    return hits, files


@check("hardcoded_color")
def check_hardcoded_color(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    pattern = re.compile(p.get("pattern", r"Color\s*\(\s*0x[0-9A-Fa-f]{8}\s*\)"))
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                hits.append(hit(rel, idx, "硬编码颜色值（应使用设计 token）", line.strip()))
    return hits, files


@check("string_key_naming")
def check_string_key_naming(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    pattern = re.compile(p.get("pattern", r"[a-z][a-z0-9_]*"))
    hits = []
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        keys = re.findall(r"<string\s+name=\"([^\"]+)\"", text)
        for key in keys:
            if not pattern.fullmatch(key):
                hits.append(hit(rel, 1, f"字符串资源 key 命名不符合 snake_case: {key}", key))
    return hits, files


@check("i18n_parity")
def check_i18n_parity(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    base_rel = p.get("base_file")
    if not base_rel or not ctx.exists(base_rel):
        raise CheckError(f"基准 strings 文件不存在: {base_rel}")

    def keys(rel):
        return set(re.findall(r"<string\s+name=\"([^\"]+)\"", ctx.text(rel)))

    base = keys(base_rel)
    hits = []
    for locale_rel in (p.get("compare_files") or []):
        if not ctx.exists(locale_rel):
            hits.append(hit(locale_rel, 1, "locale 资源文件不存在", locale_rel))
            continue
        other = keys(locale_rel)
        missing = sorted(base - other)
        if len(missing) <= int(p.get("max_missing", 0)):
            missing = []
        if missing:
            hits.append(hit(locale_rel, 1, f"缺失 {len(missing)} 个字符串 key（示例: {', '.join(missing[:8])}）", f"missing={len(missing)}"))
        extra = sorted(other - base)
        if extra and p.get("flag_extra", True):
            hits.append(hit(locale_rel, 1, f"多出 {len(extra)} 个未在默认 locale 定义的 key（示例: {', '.join(extra[:8])}）", f"extra={len(extra)}"))
    return hits, [base_rel] + list(p.get("compare_files") or [])


@check("locale_config_consistency")
def check_locale_config_consistency(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    config = p.get("config")
    mapping = p.get("mapping") or {}
    if not config or not ctx.exists(config):
        raise CheckError(f"locales_config 不存在: {config}")
    text = ctx.text(config)
    declared = set(re.findall(r'<locale\s+android:name="([^"]+)"', text))
    hits = []
    for locale, res_dir in mapping.items():
        if locale not in declared:
            hits.append(hit(config, 1, f"locales_config 未声明 locale: {locale}", locale))
        if not ctx.exists(res_dir + "/strings.xml"):
            hits.append(hit(res_dir + "/strings.xml", 1, f"locale 目录缺 strings.xml: {res_dir}", res_dir))
    return hits, [config]


@check("doc_local_links")
def check_doc_local_links(ctx: Context, rule: dict):
    from urllib.parse import unquote
    p = rule.get("params") or {}
    files = _iter_candidates(ctx, p)
    link_re = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
    hits = []
    root_resolved = ctx.root.resolve()
    for rel in files:
        text = ctx.text(rel)
        if not text:
            continue
        for m in link_re.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#", "tel:", "data:")):
                continue
            target = target.split("#")[0].split("?")[0]
            if not target:
                continue
            target = unquote(target)
            resolved = (ctx.root / Path(rel).parent / target).resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError:
                continue
            if not resolved.exists():
                hits.append(hit(rel, line_no(text, m.start()), f"相对链接目标不存在: {target}", target))
    return hits, files


@check("doc_command_refs")
def check_doc_command_refs(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"文档不存在: {target}")
    text = ctx.text(target)
    pattern = re.compile(p.get("pattern", r"(?:bash|python|sh)\s+([\w./-]+\.(?:sh|py))"))
    hits = []
    for m in pattern.finditer(text):
        ref = m.group(1)
        if not ctx.exists(ref):
            hits.append(hit(target, line_no(text, m.start()), f"文档引用的脚本不存在: {ref}", ref))
    return hits, [target]


@check("locale_anchor_sha")
def check_locale_anchor_sha(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    registry = p.get("registry") or "protocol/locales.json"
    if not ctx.exists(registry):
        raise CheckError(f"locales 注册表不存在: {registry}")
    try:
        data = json.loads(ctx.text(registry))
    except json.JSONDecodeError as exc:
        raise CheckError(f"locales 注册表解析失败: {exc}") from exc
    hits = []
    for item in data.get("docs", []):
        src = item.get("path")
        if not src or not ctx.exists(src):
            hits.append(hit(registry, 1, f"登记源件不存在: {src}", src))
            continue
        actual = hashlib.sha256((ctx.root / src).read_bytes()).hexdigest()
        for lang, tr in (item.get("translations") or {}).items():
            expected = (tr or {}).get("source_sha256")
            if expected != actual:
                hits.append(hit(registry, 1, f"译件锚过期: {src}（{lang}）", f"expected={expected} actual={actual}"))
    return hits, [registry]


@check("a11y_evidence_paths")
def check_a11y_evidence_paths(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    registry = p.get("registry") or "protocol/accessibility.json"
    if not ctx.exists(registry):
        raise CheckError(f"a11y 注册表不存在: {registry}")
    try:
        data = json.loads(ctx.text(registry))
    except json.JSONDecodeError as exc:
        raise CheckError(f"a11y 注册表解析失败: {exc}") from exc
    evidence = set()
    for key in ("wcag", "human_factors", "usability_tests"):
        for item in data.get(key, []) or []:
            for ev in item.get("evidence", []) or []:
                evidence.add(ev)
    hits = []
    for ev in sorted(evidence):
        if not ctx.exists(ev):
            hits.append(hit(registry, 1, f"a11y 登记证据路径不存在: {ev}", ev))
    return hits, [registry]


@check("version_consistency")
def check_version_consistency(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    expected = p.get("expected")
    checks = p.get("files") or {}
    hits = []
    for rel, pattern in checks.items():
        if not ctx.exists(rel):
            hits.append(hit(rel, 1, "版本声明文件缺失", rel))
            continue
        text = ctx.text(rel)
        if expected and expected not in text:
            hits.append(hit(rel, 1, f"版本声明未包含 {expected}", expected))
        if pattern and not re.search(pattern, text, re.M):
            hits.append(hit(rel, 1, f"版本声明不符合模式 {pattern}", pattern))
    return hits, list(checks.keys())


@check("changelog_version")
def check_changelog_version(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file") or "CHANGELOG.md"
    if not ctx.exists(target):
        raise CheckError(f"CHANGELOG 不存在: {target}")
    text = ctx.text(target)
    hits = []
    fallback = [rel for rel in (p.get("fallback_files") or []) if ctx.exists(rel)]
    fallback_text = "\n".join(ctx.text(rel) for rel in fallback)
    for version in (p.get("versions") or []):
        if version in text or (fallback_text and version in fallback_text):
            continue
        hits.append(hit(target, 1, f"CHANGELOG 未覆盖版本 {version}（替代来源也未覆盖）", version))
    return hits, [target] + fallback


@check("doc_scope_claim")
def check_doc_scope_claim(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"文档不存在: {target}")
    text = ctx.text(target)
    claim = p.get("claim")
    if not claim or claim not in text:
        return [], [target]
    contradicted = ctx.candidates(p.get("contradict_globs") or [])
    if contradicted:
        sample = ", ".join(contradicted[:5])
        return [hit(target, 1, f"声明与仓内目录并存，适用面需确认: {claim}", f"{len(contradicted)} 个文件: {sample}")], [target]
    return [], [target]


@check("repo_stats_freshness")
def check_repo_stats_freshness(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file")
    if not target or not ctx.exists(target):
        raise CheckError(f"repo_stats 不存在: {target}")
    try:
        data = json.loads(ctx.text(target))
    except json.JSONDecodeError as exc:
        raise CheckError(f"repo_stats 解析失败: {exc}") from exc
    hits = []
    for item in p.get("expected_counts") or []:
        key = item.get("key")
        globs = item.get("globs") or []
        if key not in data:
            hits.append(hit(target, 1, f"repo_stats 缺计数键: {key}", key))
            continue
        actual = len(ctx.candidates(globs))
        if int(data[key]) != actual:
            hits.append(hit(target, 1, f"repo_stats.{key}={data[key]} 与实扫 {actual} 不一致", f"{data[key]} vs {actual}"))
    return hits, [target]


@check("gitignore_covers_build")
def check_gitignore_covers_build(ctx: Context, rule: dict):
    p = rule.get("params") or {}
    target = p.get("file") or ".gitignore"
    if not ctx.exists(target):
        raise CheckError(f"gitignore 不存在: {target}")
    text = ctx.text(target)
    hits = []
    for pat in p.get("patterns") or []:
        if not re.search(pat, text, re.M):
            hits.append(hit(target, 1, f".gitignore 缺少构建产物规则: {pat}", pat))
    return hits, [target]


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"[runner] 读取失败 {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[runner] JSON 解析失败 {path}: {exc}") from exc


def validate_rules(rules_doc: dict, scoring: dict) -> list[dict]:
    if not isinstance(rules_doc.get("rules"), list):
        raise SystemExit("[runner] rules.json 缺少 rules 数组")
    dims = set((scoring.get("dimensions") or {}).keys())
    if not dims:
        raise SystemExit("[runner] scoring.json 缺少 dimensions")
    seen = set()
    rules = []
    for raw in rules_doc["rules"]:
        rid = raw.get("id")
        for field in ("id", "dimension", "iso", "severity", "statement", "check", "penalty", "source", "version"):
            if field not in raw:
                raise SystemExit(f"[runner] 规则 {rid} 缺字段 {field}")
        if rid in seen:
            raise SystemExit(f"[runner] 规则 id 重复: {rid}")
        seen.add(rid)
        if raw["dimension"] not in dims:
            raise SystemExit(f"[runner] 规则 {rid} 维度非法: {raw['dimension']}")
        if raw["severity"] not in ("P0", "P1", "P2", "P3"):
            raise SystemExit(f"[runner] 规则 {rid} severity 非法: {raw['severity']}")
        if raw["check"] not in ("script", "tool", "manual"):
            raise SystemExit(f"[runner] 规则 {rid} check 非法: {raw['check']}")
        if raw["check"] == "script" and not raw.get("script"):
            raise SystemExit(f"[runner] 规则 {rid} 缺 script")
        if raw["check"] == "tool" and not raw.get("tool"):
            raise SystemExit(f"[runner] 规则 {rid} 缺 tool")
        try:
            penalty = int(raw["penalty"])
        except (TypeError, ValueError):
            raise SystemExit(f"[runner] 规则 {rid} penalty 非整数")
        if penalty < 0:
            raise SystemExit(f"[runner] 规则 {rid} penalty 为负")
        item = dict(raw)
        item["penalty"] = penalty
        rules.append(item)
    return rules


def effective_penalty(rule: dict, scoring: dict) -> int:
    cap = int(scoring.get("penalty_cap_per_rule", 5))
    return min(rule["penalty"], cap)


def sort_hits(hits: list[dict]) -> list[dict]:
    return sorted(hits, key=lambda h: (str(h.get("path", "")), int(h.get("line", 1)), str(h.get("message", "")), str(h.get("evidence", ""))))


def assign_ids(rule_id: str, hits: list[dict]) -> list[dict]:
    result = []
    used: dict[str, int] = {}
    for item in hits:
        base = f"{rule_id}::{item['path']}:{item['line']}"
        if base in used:
            used[base] += 1
            issue_id = f"{base}#{used[base]}"
        else:
            used[base] = 1
            issue_id = base
        result.append({"id": issue_id, "rule_id": rule_id, **item})
    return result


def run_rules(ctx: Context, rules: list[dict], scoring: dict, max_issues_per_rule: int):
    issues: list[dict] = []
    rule_status: dict[str, dict] = {}
    for rule in rules:
        rid = rule["id"]
        status = {
            "dimension": rule["dimension"],
            "severity": rule["severity"],
            "check": rule["check"],
            "script": rule.get("script"),
            "tool": rule.get("tool"),
            "status": "not-run",
            "candidates": 0,
            "hits": 0,
            "stored": 0,
        }
        if rule["check"] != "script":
            status["status"] = "not-run"
            status["reason"] = rule.get("note") or ("需要外部工具" if rule["check"] == "tool" else "需要人工评审")
            rule_status[rid] = status
            continue
        fn = CHECKS.get(rule["script"])
        if fn is None:
            status["status"] = "error"
            status["error"] = f"未实现的 script 检查器: {rule['script']}"
            rule_status[rid] = status
            continue
        try:
            hits, candidates = fn(ctx, rule)
        except CheckError as exc:
            status["status"] = "error"
            status["error"] = str(exc)
            rule_status[rid] = status
            continue
        except Exception as exc:  # noqa: BLE001 - 规则异常必须显式记录
            status["status"] = "error"
            status["error"] = f"{type(exc).__name__}: {exc}"
            status["traceback"] = traceback.format_exc(limit=2)
            rule_status[rid] = status
            continue
        hits = sort_hits([h for h in hits if h.get("path") is not None])
        status["candidates"] = len(candidates) if not isinstance(candidates, int) else candidates
        status["hits"] = len(hits)
        status["stored"] = min(len(hits), max_issues_per_rule)
        if not candidates:
            status["status"] = "no_targets"
        elif hits:
            status["status"] = "fail"
        else:
            status["status"] = "pass"
        rule_status[rid] = status
        for item in assign_ids(rid, hits[:max_issues_per_rule]):
            item["dimension"] = rule["dimension"]
            item["severity"] = rule["severity"]
            item["statement"] = rule["statement"]
            issues.append(item)
    return issues, rule_status


def compute_scores(rules: list[dict], rule_status: dict, scoring: dict):
    dimensions = scoring.get("dimensions") or {}
    per_dim = {d: {"score": 100, "weight": float(meta.get("weight", 0)), "deduction": 0,
                   "hits": 0, "rules": 0, "failing_rules": 0}
              for d, meta in dimensions.items()}
    for rule in rules:
        dim = rule["dimension"]
        info = rule_status[rule["id"]]
        per_dim[dim]["rules"] += 1
        if info["status"] == "fail":
            deduction = min(int(info["hits"]), effective_penalty(rule, scoring))
            per_dim[dim]["deduction"] += deduction
            per_dim[dim]["hits"] += int(info["hits"])
            per_dim[dim]["failing_rules"] += 1
    total = 0.0
    for dim, data in per_dim.items():
        data["score"] = max(0, 100 - data["deduction"])
        data["weight"] = float(dimensions[dim].get("weight", 0))
        total += data["score"] * data["weight"]
    return per_dim, round(total, 2)


def build_report(meta: dict, per_dim: dict, issues: list[dict], rules_by_id: dict) -> str:
    lines = []
    lines.append("# NF 审计报告（离线可复现）")
    lines.append("")
    lines.append("- 审计对象：" + str(meta["object"]))
    lines.append("- 源码根：" + str(meta["root"]))
    lines.append("- commit：" + str(meta["commit"]))
    lines.append("- 规则库版本：" + str(meta["rules_version"]) + "；scoring 版本：" + str(meta["scoring_version"]))
    lines.append("- Python：" + str(meta["python"]) + "；执行器：" + str(meta["audit_version"]) + "（sha256 " + str(meta["runner_sha256"])[:16] + "）")
    lines.append("- 规则总数：" + str(meta["rules"]["total"]) + "（script " + str(meta["rules"]["script"]) + " / tool " + str(meta["rules"]["tool"]) + " / manual " + str(meta["rules"]["manual"]) + "）")
    lines.append("")
    lines.append("## 评分总览")
    lines.append("")
    lines.append("| 维度 | 名称 | 权重 | 扣分 | 命中数 | 维度分 |")
    lines.append("|---|---|---|---|---|---|")
    for dim in sorted(per_dim):
        data = per_dim[dim]
        lines.append("| " + dim + " | " + meta["dimension_names"].get(dim, "") + " | "
                     + f"{data['weight']:.2f}" + " | " + str(data["deduction"]) + " | "
                     + str(data["hits"]) + " | " + str(data["score"]) + " |")
    lines.append("")
    lines.append("**总分：" + str(meta["score"]) + "**（= Σ 维度分 × 权重）")
    lines.append("")
    counts = meta["severity_counts"]
    lines.append("问题命中（按规则实际上报）：P0=" + str(counts["P0"]) + " / P1=" + str(counts["P1"]) + " / P2="
                 + str(counts["P2"]) + " / P3=" + str(counts["P3"]) + "，合计 " + str(meta["hits_total"]))
    lines.append("")
    lines.append("证据包 issues.json 按单规则最多保留 200 条（防超大文件），实际保留 "
                 + str(meta["issue_count"]) + " 条；完整命中数见 meta.json 的 rule_status.hits。截断不影响评分与门禁。")
    lines.append("")
    lines.append("## 规则执行状态")
    lines.append("")
    st = meta["status_counts"]
    lines.append("script 规则：pass=" + str(st["pass"]) + " / fail=" + str(st["fail"]) + " / error="
                 + str(st["error"]) + " / no_targets=" + str(st["no_targets"])
                 + "；tool+manual 未执行（not-run）=" + str(st["not-run"]))
    lines.append("")
    lines.append("口径：tool / manual 规则记 not-run，不计扣分、不写成 pass；no_targets（无目标文件）与 error（执行异常）同样不计扣分、不算通过。")
    lines.append("")
    if meta["errors"]:
        lines.append("### 执行异常（error）")
        lines.append("")
        for e in meta["errors"]:
            lines.append("- " + e["rule_id"] + "：" + e["message"])
        lines.append("")
    p0p1 = [i for i in issues if i["severity"] in ("P0", "P1")]
    lines.append("## P0/P1 命中清单")
    lines.append("")
    if not p0p1:
        lines.append("无 P0/P1 命中。")
    else:
        lines.append("| 规则 | 级别 | 位置 | 说明 |")
        lines.append("|---|---|---|---|")
        for item in p0p1[:200]:
            lines.append("| " + item["rule_id"] + " | " + item["severity"] + " | "
                         + item["path"] + ":" + str(item["line"]) + " | " + item["message"] + " |")
        if len(p0p1) > 200:
            lines.append("| … | | | 仅列出前 200 条，共 " + str(len(p0p1)) + " 条 |")
    lines.append("")
    lines.append("## 未执行项（tool / manual）")
    lines.append("")
    lines.append("| 规则 | 级别 | 类型 | 工具/方式 | 说明 |")
    lines.append("|---|---|---|---|---|")
    for rid in sorted(rules_by_id):
        rule = rules_by_id[rid]
        if rule["check"] == "script":
            continue
        tool = rule.get("tool") or "人工抽样"
        lines.append("| " + rid + " | " + rule["severity"] + " | " + rule["check"] + " | "
                     + str(tool) + " | " + str(rule.get("note", "")) + " |")
    lines.append("")
    lines.append("## 复现")
    lines.append("")
    lines.append("    python audit/runner.py --root " + str(meta["root"]) + " --commit "
                 + str(meta["commit"]) + " --out audit/evidence/" + str(meta["commit"]))
    lines.append("")
    lines.append("同一输入重跑：文件遍历与命中排序均为确定性，issues.json / meta.json / report.md 逐字节一致。")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="NF 离线审计执行器")
    parser.add_argument("--root", required=True, help="源码树根目录")
    parser.add_argument("--commit", default="", help="审计对象 commit")
    parser.add_argument("--out", required=True, help="证据输出目录")
    parser.add_argument("--rules", default=None, help="规则库路径（默认 audit/rules.json）")
    parser.add_argument("--scoring", default=None, help="评分配置路径（默认 audit/scoring.json）")
    parser.add_argument("--max-issues-per-rule", type=int, default=200, help="单规则最多写入证据的条数")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"[runner] 源码根不存在: {root}")

    here = Path(__file__).resolve().parent
    rules_path = Path(args.rules) if args.rules else here / "rules.json"
    scoring_path = Path(args.scoring) if args.scoring else here / "scoring.json"
    rules_doc = load_json(rules_path)
    scoring = load_json(scoring_path)
    rules = validate_rules(rules_doc, scoring)
    rules_by_id = {r["id"]: r for r in rules}

    ctx = Context(root)
    issues, rule_status = run_rules(ctx, rules, scoring, args.max_issues_per_rule)

    status_counts = {"pass": 0, "fail": 0, "error": 0, "no_targets": 0, "not-run": 0}
    for info in rule_status.values():
        status_counts[info["status"]] = status_counts.get(info["status"], 0) + 1
    # 命中数按规则实际上报条数统计（证据包可能按单规则上限截断，截断不影响评分/门禁）
    severity_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    hits_total = 0
    for rid, info in rule_status.items():
        sev = info.get("severity", "P3")
        severity_counts[sev] = severity_counts.get(sev, 0) + int(info.get("hits", 0))
        hits_total += int(info.get("hits", 0))
    stored_severity_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in issues:
        stored_severity_counts[item["severity"]] = stored_severity_counts.get(item["severity"], 0) + 1
    errors = [
        {"rule_id": rid, "message": info.get("error", "")}
        for rid, info in rule_status.items() if info["status"] == "error"
    ]
    errors.sort(key=lambda x: x["rule_id"])
    per_dim, total = compute_scores(rules, rule_status, scoring)

    runner_bytes = Path(__file__).read_bytes()
    meta = {
        "schema": "nf-audit-meta/1",
        "audit_version": AUDIT_VERSION,
        "runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
        "rules_sha256": hashlib.sha256(rules_path.read_bytes()).hexdigest(),
        "scoring_sha256": hashlib.sha256(scoring_path.read_bytes()).hexdigest(),
        "object": rules_doc.get("object", "NF 源码"),
        "commit": args.commit,
        "root": root.as_posix(),
        "python": sys.version.split()[0],
        "rules_version": rules_doc.get("version"),
        "scoring_version": scoring.get("version"),
        "dimension_names": {d: meta.get("name", "") for d, meta in (scoring.get("dimensions") or {}).items()},
        "rules": {
            "total": len(rules),
            "script": sum(1 for r in rules if r["check"] == "script"),
            "tool": sum(1 for r in rules if r["check"] == "tool"),
            "manual": sum(1 for r in rules if r["check"] == "manual"),
        },
        "files_scanned": len(ctx.files),
        "script_checkers": sorted(CHECKS),
        "score": total,
        "dimensions": {d: {"score": data["score"], "weight": data["weight"], "deduction": data["deduction"],
                           "hits": data["hits"], "rules": data["rules"], "failing_rules": data["failing_rules"]}
                       for d, data in per_dim.items()},
        "severity_counts": severity_counts,
        "stored_severity_counts": stored_severity_counts,
        "hits_total": hits_total,
        "issue_count": len(issues),
        "status_counts": status_counts,
        "errors": errors,
        "rule_status": rule_status,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    issues_doc = {
        "schema": "nf-audit-issues/1",
        "commit": args.commit,
        "rules_total": len(rules),
        "issue_count": len(issues),
        "issues": issues,
        "not_run": sorted(rid for rid, info in rule_status.items() if info["status"] == "not-run"),
        "errors": errors,
        "no_targets": sorted(rid for rid, info in rule_status.items() if info["status"] == "no_targets"),
    }
    (out_dir / "issues.json").write_text(
        json.dumps(issues_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = build_report(meta, per_dim, issues, rules_by_id)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    if not args.quiet:
        print(f"NF 审计完成：commit={args.commit or '(未提供)'} 规则 {len(rules)} 条")
        for dim in sorted(per_dim):
            data = per_dim[dim]
            print(f"  {dim} {meta['dimension_names'].get(dim, ''):<14s} 权重 {data['weight']:.2f} 扣分 {data['deduction']:>3d} 维度分 {data['score']:>3d}")
        print(f"总分：{total}")
        print(f"问题（按规则实际命中）：P0={severity_counts['P0']} P1={severity_counts['P1']} P2={severity_counts['P2']} P3={severity_counts['P3']} 合计 {hits_total}")
        print(f"证据包保留 {len(issues)} 条（单规则截断上限 200）")
        print(f"规则状态：pass={status_counts['pass']} fail={status_counts['fail']} error={status_counts['error']} no_targets={status_counts['no_targets']} not-run={status_counts['not-run']}")
        print(f"证据：{out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
