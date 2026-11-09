#!/usr/bin/env python3
"""Fail closed when a workflow claims SLSA Build L3 without readiness evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
READINESS_REL = "packaging/supply-chain/slsa-l3-readiness.json"
POLICY_REL = "packaging/supply-chain/verification-policy.json"
WORKFLOW_REL = ".github/workflows/npm-publish.yml"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def scan(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    readiness = _json(root / READINESS_REL)
    policy = _json(root / POLICY_REL)
    workflow = (root / WORKFLOW_REL).read_text(encoding="utf-8")
    if readiness.get("claimed_level") == "SLSA_BUILD_LEVEL_3":
        issues.append("readiness 未完成却声明 SLSA_BUILD_LEVEL_3")
    if "SLSA_BUILD_LEVEL_3" in (policy.get("verified_levels") or []):
        issues.append("verification policy 不得把自制共享 runner 标成 Build L3")
    requirements = readiness.get("requirements")
    if not isinstance(requirements, list) or len(requirements) < 4:
        issues.append("L3 readiness 缺完整要求矩阵")
        requirements = []
    statuses: dict[str, int] = {}
    for req in requirements:
        status = str(req.get("status") if isinstance(req, dict) else "")
        statuses[status] = statuses.get(status, 0) + 1
        if status not in {"satisfied", "partial", "blocked"}:
            issues.append(f"L3 readiness 非法状态：{status!r}")
    if not any(isinstance(r, dict) and r.get("id") == "trusted-builder"
               and r.get("status") == "blocked" for r in requirements):
        issues.append("当前不得把共享 GitHub runner 宣称为 trusted L3 builder")
    for needle in (
        "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
        "https://slsa.dev/verification_summary/v1",
        "scripts/build_vsa.py",
    ):
        if needle not in workflow:
            issues.append(f"发布工作流缺 VSA 接线：{needle}")
    if "slsa-github-generator" in workflow:
        issues.append("不得重新引入停维且要求浮动 tag 的 Node.js SLSA builder")
    return issues, {
        "claimed_level": readiness.get("claimed_level"),
        "statuses": dict(sorted(statuses.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SLSA L3 readiness / non-claim gate")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    try:
        issues, stats = scan(Path(args.root))
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    print(f"== SLSA L3 readiness ==\n  当前声明 {stats['claimed_level']} · {stats['statuses']}")
    for issue in issues:
        print(f"  ✗ {issue}", file=sys.stderr)
    if not issues:
        print("  ✓ 已接线 VSA；未虚标 L3，trusted builder 仍按 blocker 管理")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
