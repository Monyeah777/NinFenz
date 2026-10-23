#!/usr/bin/env python3
"""Synchronize the repository-root llms-full.txt with its site source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402


SOURCE = ROOT / "site" / "llms-full.txt"
TARGET = ROOT / "llms-full.txt"


def synchronized() -> bool:
    return TARGET.is_file() and TARGET.read_bytes() == SOURCE.read_bytes()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Keep the root llms-full.txt byte-identical to site/llms-full.txt"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the root projection")
    mode.add_argument("--check", action="store_true", help="fail when the projection drifts")
    args = parser.parse_args(argv)

    if not SOURCE.is_file():
        print(f"missing source: {SOURCE.relative_to(ROOT)}", file=sys.stderr)
        return 1

    if args.write:
        atomic_write.write_bytes(TARGET, SOURCE.read_bytes())
        print("llms-full.txt written from site/llms-full.txt")
        return 0

    if synchronized():
        print("llms-full.txt is synchronized")
        return 0

    target_state = "missing" if not TARGET.exists() else "different"
    print(
        "llms-full.txt drift: "
        f"{target_state}; run `python scripts/sync_llms.py --write`",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())

