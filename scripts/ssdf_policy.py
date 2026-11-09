#!/usr/bin/env python3
"""Validate the scoped NIST SSDF v1.1 evidence matrix and RV response ledger."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ssdf_policy  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 NIST SSDF v1.1 作用域证据")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    issues, stats = ssdf_policy.scan(Path(args.root))
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== NIST SSDF v1.1 作用域证据 ==")
        print(
            f"  实践 {stats.get('practices', 0)} 条 · {stats.get('statuses', {})}"
            f" · 任务 {stats.get('tasks', 0)} 条 · {stats.get('task_statuses', {})}"
        )
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ 实践/任务证据、RV 台账与发布阻断规则全部自洽（非第三方认证）")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
