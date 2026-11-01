#!/usr/bin/env python3
"""Validate or collect SLSA v1.2 Source Track readiness evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, slsa_source_policy as policy  # noqa: E402


def _gh_api(path: str) -> Any:
    proc = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            path,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"GitHub API read failed for {path}: {proc.stderr.strip()[:200]}"
            "（修复指引：检查 gh 认证、网络与仓库只读权限）"
        )
    return json.loads(proc.stdout)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_snapshot(snapshot: dict[str, Any], root: Path) -> None:
    text = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write.write_text(root / policy.CONTROLS_REL, text)


def _render(issues: list[str], stats: dict[str, Any]) -> None:
    print(
        f"== SLSA Source readiness ==\n"
        f"  claimed={stats.get('claimed_level')} target={stats.get('target_level')} "
        f"source_vsa={stats.get('source_vsa_available')} "
        f"source_provenance={stats.get('source_provenance_available')}"
    )
    for issue in issues:
        print(f"  ✗ {issue}", file=sys.stderr)
    if not issues:
        print("  ✓ 技术控制快照自洽；未把 Build provenance 冒充 Source provenance")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SLSA v1.2 Source Track readiness")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--collect", action="store_true", help="refresh GitHub control snapshot")
    parser.add_argument("--live", action="store_true", help="validate current GitHub controls")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.collect or args.live:
            snapshot = policy.collect(_gh_api, _now())
            if args.collect:
                _write_snapshot(snapshot, root)
            controls = snapshot
        else:
            controls = json.loads((root / policy.CONTROLS_REL).read_text(encoding="utf-8"))
        readiness = json.loads((root / policy.READINESS_REL).read_text(encoding="utf-8"))
        issues, stats = policy.scan_documents(readiness, controls)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {"issues": issues, "stats": stats}, ensure_ascii=False, indent=2, sort_keys=True
            )
        )
    else:
        _render(issues, stats)
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
