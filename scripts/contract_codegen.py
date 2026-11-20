#!/usr/bin/env python3
"""Generate Kotlin/TypeScript types from NF App view contracts."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop" / "src"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="contract_codegen")
    ap.add_argument("--lang", choices=("kotlin", "ts"), default="kotlin")
    ap.add_argument("--out", default="", help="write file; default stdout")
    args = ap.parse_args(argv)
    from core.research import contract_codegen
    text = (contract_codegen.all_kotlin() if args.lang == "kotlin"
            else contract_codegen.all_typescript())
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote " + args.out)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
