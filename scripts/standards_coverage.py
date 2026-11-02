#!/usr/bin/env python3
"""Build or verify the standards four-state coverage ledger."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import standards_coverage as sc  # noqa: E402


def _print_issues(issues: list[str]) -> None:
    for issue in issues:
        print(f"  ✗ {issue}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="标准四态覆盖账本")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--write", action="store_true", help=f"写入 {sc.REPORT_REL}")
    parser.add_argument("--check", action="store_true", help="已提交报告 == 实时重算")
    parser.add_argument("--json", action="store_true", help="输出完整报告")
    args = parser.parse_args(argv)
    if args.write and args.check:
        parser.error("--write 与 --check 不能同时使用")
    if args.write:
        issues, report = sc.write(args.root)
        header = "write"
    elif args.check:
        issues, report = sc.check(args.root)
        header = "check"
    else:
        issues, report = sc.build(args.root)
        header = "scan"
    if args.json:
        print(sc.render(report), end="")
    else:
        summary = report.get("summary", {})
        print(f"== 标准四态账本（{header}）==")
        print(
            "  编目 {catalogued} · 绑定 {bound} · 断言 {asserted} · 可消费 {consumable}"
            " · 非域包绑定 {not_domain_bound}".format(**summary)
        )
        _print_issues(issues)
        if not issues:
            print("  ✓ catalog / binding / assertions / consumers 四方一致")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
