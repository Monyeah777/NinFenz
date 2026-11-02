"""Content-addressed local store for verified A/B experiment bundles."""

from __future__ import annotations

import json
from pathlib import Path

from . import atomic_io, cockpit_ab_bundle, file_lock, json_asset

MAX_BUNDLE_BYTES = 16 * 1024 * 1024


def _path(directory: Path, bundle_digest: str) -> Path:
    if len(bundle_digest) != 64 or any(char not in "0123456789abcdef" for char in bundle_digest):
        raise ValueError("invalid bundle digest")
    return directory / (bundle_digest + ".json")


def save(directory: str | Path, bundle: dict) -> Path:
    issues = cockpit_ab_bundle.verify(bundle)
    if issues:
        raise ValueError("invalid bundle: " + "; ".join(issues))
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    target = _path(root, bundle["bundle_digest"])
    payload = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    with file_lock.locked(target):
        if target.is_file():
            existing = load(target)
            if existing != bundle:
                raise ValueError("content-addressed collision")
            return target
        atomic_io.write_text(target, payload)
    return target


def load(path: str | Path) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError("bundle missing")
    if target.stat().st_size > MAX_BUNDLE_BYTES:
        raise ValueError("bundle too large")
    try:
        bundle = json_asset.load(target)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("invalid bundle json") from exc
    if not isinstance(bundle, dict):
        raise ValueError("invalid bundle type")
    issues = cockpit_ab_bundle.verify(bundle)
    if issues:
        raise ValueError("invalid bundle: " + "; ".join(issues))
    if target.name != bundle["bundle_digest"] + ".json":
        raise ValueError("bundle filename digest mismatch")
    return bundle


def index(directory: str | Path) -> list[dict]:
    return audit(directory)["entries"]


def audit(directory: str | Path) -> dict:
    root = Path(directory)
    if not root.is_dir():
        return {
            "schema": "nf-cockpit-ab-store-audit/1",
            "entries": [],
            "invalid": [],
        }
    entries = []
    invalid = []
    for path in sorted(root.glob("*.json")):
        try:
            bundle = load(path)
        except ValueError as exc:
            invalid.append(
                {
                    "path": path.name,
                    "reason": str(exc)[:500],
                }
            )
            continue
        entries.append(
            {
                "bundle_digest": bundle["bundle_digest"],
                "experiment_id": bundle["manifest"]["experiment_id"],
                "analysis_plan_digest": bundle["manifest"]["analysis_plan_digest"],
                "has_analysis": bundle["analysis"] is not None,
                "path": path.name,
            }
        )
    return {
        "schema": "nf-cockpit-ab-store-audit/1",
        "entries": entries,
        "invalid": invalid,
    }
