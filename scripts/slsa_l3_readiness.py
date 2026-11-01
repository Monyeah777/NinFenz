#!/usr/bin/env python3
"""CLI wrapper for the SLSA v1.2 Build L3 policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import slsa_policy  # noqa: E402

READINESS_REL = slsa_policy.READINESS_REL
POLICY_REL = slsa_policy.POLICY_REL
WORKFLOW_REL = slsa_policy.WORKFLOW_REL
BUILDER_REL = slsa_policy.BUILDER_REL
RELEASE_WORKFLOW_REL = slsa_policy.RELEASE_WORKFLOW_REL
EVIDENCE_BUILDER_REL = slsa_policy.EVIDENCE_BUILDER_REL
RUN_EVIDENCE_REL = slsa_policy.RUN_EVIDENCE_REL
EXPECTED_REQUIREMENTS = slsa_policy.EXPECTED_REQUIREMENTS
scan = slsa_policy.scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 SLSA v1.2 Build L3 声明")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        issues, stats = scan(Path(args.root))
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats}, ensure_ascii=False,
                         indent=2, sort_keys=True))
    else:
        print(f"== SLSA v1.2 Build L3 readiness ==\n"
              f"  当前声明 {stats['claimed_level']} · {stats['statuses']}")
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ reusable builder、隔离、无缓存、provenance、VSA 与消费者验签全部自洽")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
