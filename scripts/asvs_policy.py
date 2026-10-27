#!/usr/bin/env python3
"""Validate the scoped OWASP ASVS 5.0.0 Level 2 evidence matrix."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import asvs_policy  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 ASVS 5.0.0 L2 作用域证据")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        issues, stats = asvs_policy.scan(Path(args.root))
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== ASVS 5.0.0 L2 作用域证据 ==")
        print(f"  需求 {stats.get('requirements', 0)} 条 · "
              f"状态 {stats.get('statuses', {})} · "
              f"章节 {len(stats.get('chapters', []))} 个")
        controls = stats.get("controls") or {}
        print(f"  控制清单：数据类 {controls.get('data_classes', 0)} · "
              f"通信 {controls.get('communication_paths', 0)} · "
              f"密码算法 {controls.get('crypto_inventory', 0)} · "
              f"资源上限 {controls.get('resource_limits', 0)}")
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ 需求集合、作用域、证据与状态全部自洽（内部评估，非第三方认证）")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
