#!/usr/bin/env python3
"""能力清单（`nf-capability-inventory/1`）：静态扫描脚本，列出每个脚本能做什么。

为什么（第 139 轮）：第 136/138 轮我两次断言「某工具没有某能力」都判错——
两次都是**只看显式命名/帮助文本**，没看实际行为。与其继续靠记忆，不如把能力面机械列出来。

口径：**纯静态 AST 扫描**，不执行脚本（`--help` 也可能有副作用）。
抽取：模块 docstring 首行 / `ap.add_argument("--x")` 旗标 / `add_parser("x")` 子命令。
边界：静态扫描看不到「缺省模式就是校验」这类行为——它列的是**接口面**，不是语义。

用法：python scripts/capability_inventory.py [--write|--check] [--json]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/capability_inventory.json"
SCHEMA = "nf-capability-inventory/1"


def _docstring_head(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    for line in doc.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _scan_source(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    flags: list[str] = []
    subs: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", "")
        if name == "add_argument" and node.args:
            first = node.args[0]
            if (isinstance(first, ast.Constant) and isinstance(first.value, str)
                    and first.value.startswith("--")):
                flags.append(first.value)
        elif name == "add_parser" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                subs.append(first.value)
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:  # 非仓库内路径（判据会用临时目录做变异测试）
        rel = path.name
    return {"path": rel,
            "doc": _docstring_head(tree),
            "flags": sorted(set(flags)), "subcommands": sorted(set(subs))}


def _digest(rows: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for row in sorted(rows, key=lambda r: str(r["path"])):
        h.update(str(row["path"]).encode("utf-8"))
        h.update(b"\x00")
        h.update(",".join(row["flags"]).encode("utf-8"))
        h.update(b"\x00")
        h.update(",".join(row["subcommands"]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def collect(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    scripts = sorted(p for p in (base / "scripts").glob("*.py") if p.is_file())
    if not scripts:
        raise ValueError("没扫到 scripts/*.py（修复指引：确认 --root 是否指向仓库根）")
    rows = [_scan_source(p) for p in scripts]
    return {"schema": SCHEMA, "scripts": len(rows),
            "flags": sum(len(r["flags"]) for r in rows),
            "digest": _digest(rows), "entries": rows,
            "note": "静态接口面（docs/flags/subcommands），不含缺省行为语义"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="capability_inventory",
                                 description="能力清单：静态扫描 scripts/*.py 的接口面")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = collect(ROOT)
    except (ValueError, SyntaxError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        from core import atomic_write

        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（脚本 " + str(doc["scripts"]) + " · 旗标 "
              + str(doc["flags"]) + "）")
        return 0
    if args.check:
        from core import json_doc

        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        if render(json_doc.load(dest, dict, what=OUT_REL)) != render(doc):
            print("能力清单已陈旧（脚本接口面变了）——重跑 --write", file=sys.stderr)
            return 1
        print("OK 能力清单与现场一致")
        return 0
    print(render(doc), end="")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
