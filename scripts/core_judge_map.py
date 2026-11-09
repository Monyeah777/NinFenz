#!/usr/bin/env python3
"""core 模块 → 测试引用面（`nf-core-judge-map/1`）：哪些核心模块没有被任何测试提到。

为什么（第 158 轮测量，第 159 轮落成对象）：355 个 core 模块里 34 个没被任何测试文件按名字提到。
这个数要小心读——「没被提到」不等于「没被测」（可能经端到端路径覆盖），但它比「0」接近真相。

口径：**粗粒度名字匹配**（模块名出现在任一 `desktop/tests/test_*.py` 的文本里就算被引用）。
边界：这是**代理指标**，不做导入图分析；真正的覆盖判定需要运行期追踪，成本高得多。

用途：冻结「未被提到的模块数」，只减不增；新增 core 模块必须被某个测试提到（或在提交时说明）。

用法：python scripts/core_judge_map.py [--write|--check] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/core_judge_map.json"
SCHEMA = "nf-core-judge-map/1"


def _tests_text(base: Path) -> str:
    chunks = []
    for path in sorted((base / "desktop" / "tests").glob("test_*.py")):
        chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    if not chunks:
        raise ValueError("没扫到测试文件（修复指引：确认 --root 指向仓库根）")
    return "".join(chunks)


def collect(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    pool = _tests_text(base)
    modules = sorted(p.stem for p in (base / "desktop" / "src" / "core").rglob("*.py")
                     if p.stem != "__init__")
    if not modules:
        raise ValueError("没扫到 core 模块（修复指引：确认 --root 指向仓库根）")
    entries = [{"module": m, "referenced": m in pool} for m in modules]
    referenced = sum(1 for e in entries if e["referenced"])
    return {"schema": SCHEMA, "modules": len(entries),
            "referenced": referenced,
            "unreferenced": len(entries) - referenced,
            "entries": entries,
            "note": "粗粒度名字匹配（代理指标），不做导入图分析"}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="core_judge_map",
                                 description="core 模块 → 测试引用面（粗粒度）")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = collect(ROOT)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        from core import atomic_write

        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        atomic_write.write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（模块 " + str(doc["modules"]) + " · 未引用 "
              + str(doc["unreferenced"]) + "）")
        return 0
    if args.check:
        from core import json_doc

        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        if render(json_doc.load(dest, dict, what=OUT_REL)) != render(doc):
            print("core 引用面已陈旧——重跑 --write", file=sys.stderr)
            return 1
        print("OK core 引用面与现场一致")
        return 0
    if args.json:
        print(render(doc), end="")
        return 0
    print("模块 " + str(doc["modules"]) + " · 已引用 " + str(doc["referenced"])
          + " · 未引用 " + str(doc["unreferenced"]))
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
