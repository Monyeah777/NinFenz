#!/usr/bin/env python3
"""CLI for OpenVEX 0.2.0 and CycloneDX 1.6 VEX projections."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, vex  # noqa: E402

DISPOSITION_REL = vex.DISPOSITION_REL
VEX_REL = vex.OPENVEX_REL
CDX_VEX_REL = vex.CYCLONEDX_REL


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象（修复指引：恢复 JSON 对象）")
    return value


def vex_doc(root: Path = ROOT, product: str = "") -> dict[str, Any]:
    return vex.vex_doc(Path(root), product)


def cyclonedx_vex_doc(root: Path = ROOT, product: str = "") -> dict[str, Any]:
    return vex.cyclonedx_vex_doc(Path(root), product)


def validate_vex(doc: dict[str, Any]) -> list[str]:
    return vex.validate_vex(doc)


def validate_cyclonedx_vex(doc: dict[str, Any]) -> list[str]:
    return vex.validate_cyclonedx_vex(doc)


def validate_vex_pair(
    openvex: dict[str, Any],
    cyclonedx: dict[str, Any],
) -> list[str]:
    return vex.validate_vex_pair(openvex, cyclonedx)


def scan_files(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    return vex.scan_files(Path(root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成/校验 OpenVEX 与 CycloneDX VEX")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--json", action="store_true")
    group.add_argument("--cyclonedx-json", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc = vex_doc(ROOT)
        cdx = cyclonedx_vex_doc(ROOT)
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    issues = validate_vex_pair(doc, cdx)
    if issues:
        for issue in issues:
            print(f"✗ {issue}", file=sys.stderr)
        return 1
    if args.write:
        for rel, value in ((VEX_REL, doc), (CDX_VEX_REL, cdx)):
            atomic_write.write_text(
                ROOT / rel,
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        print(
            f"✓ OpenVEX 已写入：{VEX_REL}（{len(doc['statements'])} 条）；"
            f"CycloneDX VEX 已写入：{CDX_VEX_REL}（{len(cdx['vulnerabilities'])} 条）"
        )
    elif args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.cyclonedx_json:
        print(json.dumps(cdx, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for rel, value in ((VEX_REL, doc), (CDX_VEX_REL, cdx)):
            try:
                actual = _read(ROOT / rel)
            except (OSError, ValueError) as exc:
                print(f"✗ {exc}", file=sys.stderr)
                return 1
            if actual != value:
                print(
                    f"✗ {rel} 过期（修复指引：python scripts/generate_vex.py --write）",
                    file=sys.stderr,
                )
                return 1
        print(
            f"✓ OpenVEX/CycloneDX VEX 与处置台账一致"
            f"（{len(doc['statements'])} 条）"
        )
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
