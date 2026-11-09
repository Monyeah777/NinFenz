#!/usr/bin/env python3
"""Validate CycloneDX 1.6 VEX with the official schema and NF fail-closed rules."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import json_doc, vex  # noqa: E402


def validate(path: Path) -> list[str]:
    try:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator
    except ImportError as exc:
        raise RuntimeError(
            "缺 CycloneDX 验证器（修复指引：安装 .github/requirements-sbom.txt）"
        ) from exc
    doc = json_doc.loads(path.read_text(encoding="utf-8"), dict, what=str(path))
    error = JsonStrictValidator(SchemaVersion.V1_6).validate_str(
        json.dumps(doc, ensure_ascii=False)
    )
    issues = [] if error is None else [f"{path.name}: CycloneDX 1.6 schema: {error}"]
    return issues + vex.validate_cyclonedx_vex(doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 CycloneDX 1.6 VEX")
    parser.add_argument("paths", nargs="+", help="一个或多个 *.cdx-vex.json")
    args = parser.parse_args(argv)
    issues: list[str] = []
    try:
        for raw in args.paths:
            issues.extend(validate(Path(raw)))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"✗ {issue}", file=sys.stderr)
    if issues:
        return 1
    print(f"✓ CycloneDX 1.6 VEX schema 与 NF 语义规则通过（{len(args.paths)} 件）")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
