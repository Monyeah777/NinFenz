#!/usr/bin/env python3
"""Check the canonical NinFenz product metadata and all derived public surfaces."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import product_metadata  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验产品版本/许可证/发布束唯一真源")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="校验真源与全部投影（默认行为，显式开关便于门禁调用）")
    parser.add_argument("--write", action="store_true",
                        help="从 product_metadata.json 重生成机器面投影")
    args = parser.parse_args(argv)
    if args.write:
        changed = product_metadata.write(args.root)
        print("== product metadata write ==")
        if changed:
            for rel in changed:
                print(f"  ✓ {rel}")
        else:
            print("  ✓ 所有机器面已与真源一致")
        return 0
    issues = product_metadata.check(args.root)
    doc = product_metadata.load(args.root)
    if args.json:
        print(json.dumps({"ok": not issues, "product": doc, "issues": issues},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== product metadata ==\n  {product_metadata.summary(args.root)}")
        for issue in issues:
            print(f"  [FAIL] {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ Python/npm/citation/CLI/MCP/法律面一致")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
