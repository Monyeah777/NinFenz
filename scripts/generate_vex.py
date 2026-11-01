#!/usr/bin/env python3
"""Generate and validate OpenVEX 0.2.0 from vulnerability dispositions."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402

DISPOSITION_REL = "results/supply-chain/vuln-disposition.json"
VEX_REL = "results/supply-chain/ninfenz.openvex.json"
PRODUCT = "pkg:npm/ninfenz@1.1.0"
ALLOWED_STATUS = {
    "not_affected", "affected", "fixed", "under_investigation",
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def vex_doc(root: Path = ROOT, product: str = PRODUCT) -> dict[str, Any]:
    disposition = _json(root / DISPOSITION_REL)
    findings = disposition.get("findings")
    if not isinstance(findings, list):
        raise ValueError(f"generate_vex: {DISPOSITION_REL} findings 必须是数组")
    reviewed = str(disposition.get("reviewed_at") or "")
    if len(reviewed) != 10:
        raise ValueError("generate_vex: reviewed_at 必须是 YYYY-MM-DD")
    statements: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("generate_vex: finding 必须是对象")
        vuln = str(finding.get("vulnerability") or "").strip()
        status = str(finding.get("status") or "").strip()
        finding_product = str(finding.get("product") or product).strip()
        if not vuln or status not in ALLOWED_STATUS:
            raise ValueError(
                f"generate_vex: finding 缺 vulnerability 或 status 非法：{finding!r}"
            )
        statement: dict[str, Any] = {
            "vulnerability": {"name": vuln},
            "products": [{"@id": finding_product}],
            "status": status,
        }
        if status == "not_affected":
            statement["justification"] = str(finding.get("justification") or "")
            statement["impact_statement"] = str(finding.get("impact_statement") or "")
            if not statement["justification"] or not statement["impact_statement"]:
                raise ValueError(f"generate_vex: not_affected 缺 justification/impact：{vuln}")
        elif status in {"affected", "under_investigation"}:
            statement["action_statement"] = str(finding.get("action_statement") or "")
            if not statement["action_statement"]:
                raise ValueError(f"generate_vex: {status} 缺 action_statement：{vuln}")
        statements.append(statement)
    identity = hashlib.sha256(
        json.dumps(
            disposition,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": f"https://ninfenz.dev/vex/{reviewed}/{identity}",
        "author": "NinFenz maintainers",
        "timestamp": f"{reviewed}T00:00:00Z",
        "version": 1,
        "tooling": "NinFenz generate_vex.py",
        "statements": statements,
    }


def validate_vex(doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if doc.get("@context") != "https://openvex.dev/ns/v0.2.0":
        issues.append("VEX 不是 OpenVEX 0.2.0")
    for key in ("@id", "author", "timestamp", "version", "tooling"):
        if not doc.get(key):
            issues.append(f"VEX 缺 {key}")
    statements = doc.get("statements")
    if not isinstance(statements, list):
        return issues + ["VEX statements 必须是数组"]
    for statement in statements:
        if not isinstance(statement, dict):
            issues.append("VEX statement 必须是对象")
            continue
        vuln = statement.get("vulnerability")
        if not isinstance(vuln, dict) or not vuln.get("name"):
            issues.append("VEX statement 缺 vulnerability.name")
        if statement.get("status") not in ALLOWED_STATUS:
            issues.append(f"VEX statement status 非法：{statement.get('status')!r}")
        products = statement.get("products")
        if not isinstance(products, list) or not products:
            issues.append("VEX statement 缺 products")
        else:
            for product in products:
                if (not isinstance(product, dict)
                        or not str(product.get("@id", "")).startswith("pkg:")):
                    issues.append("VEX product 必须是 purl")
        if statement.get("status") == "not_affected":
            for key in ("justification", "impact_statement"):
                if not statement.get(key):
                    issues.append(f"VEX not_affected 缺 {key}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成/校验 OpenVEX")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc = vex_doc(ROOT)
    except (OSError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    issues = validate_vex(doc)
    if issues:
        for issue in issues:
            print(f"✗ {issue}", file=sys.stderr)
        return 1
    if args.write:
        path = ROOT / VEX_REL
        atomic_write.write_text(
            path,
            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        print(f"✓ OpenVEX 已写入：{VEX_REL}（{len(doc['statements'])} 条）")
    elif args.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        actual = _json(ROOT / VEX_REL)
        if actual != doc:
            print(f"✗ {VEX_REL} 过期（修复指引：python scripts/generate_vex.py --write）",
                  file=sys.stderr)
            return 1
        print(f"✓ OpenVEX 与处置台账一致（{len(doc['statements'])} 条）")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
