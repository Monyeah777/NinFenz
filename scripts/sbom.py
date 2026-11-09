#!/usr/bin/env python3
"""材料清单生成器（`nf-sbom/1`）：`--write` 落 `results/ccos/sbom.json`，`--check` 与重算比对。

为什么（第 113 轮）：供应链域说「材料→产物摘要」，仓库此前没有这个对象。
本件只做清单，不做签名（签名是另一件事，且需要密钥）。

用法：python scripts/sbom.py [--write|--check] [--json] [--root PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))
OUT_REL = "results/ccos/sbom.json"


def _core(name: str):
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib

    return importlib.import_module("core." + name)


def build(root: Path = ROOT) -> dict[str, Any]:
    return _core("sbom").collect(root)


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _check(root: Path) -> int:
    """与已提交清单比对 → 退出码（0 一致 / 1 不一致或缺件）。"""
    dest = ROOT / OUT_REL
    if not dest.is_file():
        print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
        return 1
    committed = _core("json_doc").load(dest, dict, what=OUT_REL)
    issues = _core("sbom").verify(committed, root)
    if issues:
        print("；".join(issues[:3]), file=sys.stderr)
        return 1
    print("OK 材料清单与现场一致")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sbom",
                                 description="材料清单：按显式范围列出输入文件与摘要")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default="", help="仓库根（缺省=本仓）")
    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else ROOT
    try:
        doc = build(root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.write:
        dest = ROOT / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        _core("atomic_write").write_text(dest, render(doc))
        print("OK 已写入 " + OUT_REL + "（材料 " + str(doc["count"]) + " · 摘要 "
              + doc["digest"][:16] + "）")
        return 0
    if args.check:
        return _check(root)
    if False:
        dest = ROOT / OUT_REL
        if not dest.is_file():
            print("缺 " + OUT_REL + "（先跑 --write）", file=sys.stderr)
            return 1
        committed = _core("json_doc").load(dest, dict, what=OUT_REL)
        issues = _core("sbom").verify(committed, root)
        if issues:
            print("；".join(issues[:3]), file=sys.stderr)
            return 1
        print("OK 材料清单与现场一致")
        return 0
    if args.json:
        print(render(doc), end="")
        return 0
    print("材料 " + str(doc["count"]) + " 件 · " + str(doc["bytes"]) + " 字节 · 摘要 "
          + doc["digest"][:16])
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
