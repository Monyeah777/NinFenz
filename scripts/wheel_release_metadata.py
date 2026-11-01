#!/usr/bin/env python3
"""Write or verify metadata for the attested PyO3/Maturin wheel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, wheel_release  # noqa: E402


def _metadata(args: argparse.Namespace) -> int:
    doc = wheel_release.metadata(
        Path(args.wheel),
        source_commit=args.source_commit,
        source_date_epoch=int(args.source_date_epoch),
        rustc=args.rustc,
        maturin=args.maturin,
        python=args.python,
    )
    atomic_write.write_text(
        Path(args.out),
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(f"✓ wheel metadata: {args.out}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    release = Path(args.release_dir)
    wheels = sorted(release.glob("*.whl"))
    if len(wheels) != 1:
        print(f"✗ wheel 数量必须为 1，实际 {len(wheels)}", file=sys.stderr)
        return 1
    issues = wheel_release.verify(
        wheels[0],
        release / "wheel-metadata.json",
        release / "WHEEL-SHA256SUMS",
        args.source_commit,
    )
    for issue in issues:
        print(f"✗ {issue}", file=sys.stderr)
    return 1 if issues else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PyO3 wheel release evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser("metadata")
    meta.add_argument("--wheel", required=True)
    meta.add_argument("--out", required=True)
    meta.add_argument("--source-commit", required=True)
    meta.add_argument("--source-date-epoch", required=True)
    meta.add_argument("--rustc", required=True)
    meta.add_argument("--maturin", required=True)
    meta.add_argument("--python", required=True)
    meta.set_defaults(func=_metadata)
    verify = sub.add_parser("verify")
    verify.add_argument("--release-dir", required=True)
    verify.add_argument("--source-commit", required=True)
    verify.set_defaults(func=_verify)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
