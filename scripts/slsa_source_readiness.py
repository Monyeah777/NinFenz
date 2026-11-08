#!/usr/bin/env python3
"""Validate or collect SLSA v1.2 Source Track readiness evidence."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
from datetime import UTC, datetime
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402
from core import slsa_source_policy as policy  # noqa: E402

_SSL_CONTEXT = ssl.create_default_context()


def _gh_api(path: str) -> Any:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "NinFenz-Source-Readiness",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    connection = HTTPSConnection("api.github.com", timeout=30, context=_SSL_CONTEXT)
    try:
        connection.request("GET", "/" + path.lstrip("/"), headers=headers)
        response = connection.getresponse()
        payload = response.read().decode("utf-8")
        if not 200 <= response.status < 300:
            raise RuntimeError(
                f"GitHub API returned HTTP {response.status} for {path}"
                "（修复指引：检查仓库只读权限与 API 限流）"
            )
    except (OSError, HTTPException) as exc:
        raise RuntimeError(
            f"GitHub API read failed for {path}: {str(exc)[:200]}"
            "（修复指引：检查 GH_TOKEN、网络与仓库只读权限）"
        ) from exc
    finally:
        connection.close()
    return json_doc.loads(payload, (dict, list), what=f"GitHub API {path}")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
            controls = json_doc.load(root / policy.CONTROLS_REL, dict, what=policy.CONTROLS_REL)
        readiness = json_doc.load(root / policy.READINESS_REL, dict, what=policy.READINESS_REL)
        issues, stats = policy.scan_documents(readiness, controls)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats}, ensure_ascii=False,
                         indent=2, sort_keys=True))
    else:
        _render(issues, stats)
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
