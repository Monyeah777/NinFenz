#!/usr/bin/env python3
"""Validate OSPS, S2C2F, package-source, and supplier evidence.

This is a repository evidence gate, not a self-issued certification.  A control
must name concrete repository evidence or an explicitly external platform fact.
Missing files, unknown requirement IDs, incomplete supplier records, insecure
package sources, and prohibited licenses fail closed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "packaging" / "supply-chain"

EXPECTED_OSPS = {
    "OSPS-AC-01.01", "OSPS-AC-02.01", "OSPS-AC-03.01", "OSPS-AC-03.02",
    "OSPS-AC-04.01", "OSPS-BR-01.01", "OSPS-BR-01.03", "OSPS-BR-02.01",
    "OSPS-BR-03.01", "OSPS-BR-03.02", "OSPS-BR-04.01", "OSPS-BR-05.01",
    "OSPS-BR-06.01", "OSPS-BR-07.01", "OSPS-DO-01.01", "OSPS-DO-02.01",
    "OSPS-DO-06.01", "OSPS-DO-07.01", "OSPS-GV-01.01", "OSPS-GV-01.02",
    "OSPS-GV-02.01", "OSPS-GV-03.01", "OSPS-GV-03.02", "OSPS-LE-01.01",
    "OSPS-LE-02.01", "OSPS-LE-02.02", "OSPS-LE-03.01", "OSPS-LE-03.02",
    "OSPS-QA-01.01", "OSPS-QA-01.02", "OSPS-QA-02.01", "OSPS-QA-03.01",
    "OSPS-QA-04.01", "OSPS-QA-05.01", "OSPS-QA-05.02", "OSPS-QA-06.01",
    "OSPS-SA-01.01", "OSPS-SA-02.01", "OSPS-SA-03.01", "OSPS-VM-01.01",
    "OSPS-VM-02.01", "OSPS-VM-03.01", "OSPS-VM-04.01",
}

EXPECTED_S2C2F = {
    "ING-1", "ING-2", "SCA-1", "SCA-2", "SCA-3", "INV-1", "INV-2",
    "UPD-1", "UPD-2", "UPD-3", "AUD-2", "AUD-3", "ENF-1",
}

OSPS_STATUSES = {"enforced", "platform-managed", "external-manual", "partial", "not-applicable"}
S2C2F_STATUSES = {"enforced", "partial", "not-applicable"}
SOURCE_HOSTS = {"registry.npmjs.org", "pypi.org", "index.crates.io", "github.com"}


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"{path.relative_to(ROOT)}: 不可读 JSON：{exc}"
            "（修复指引：恢复有效 UTF-8 JSON）"
        ) from exc
    if not isinstance(doc, dict):
        raise ValueError(
            f"{path.relative_to(ROOT)}: 顶层必须是对象"
            "（修复指引：把根值改成 JSON 对象）"
        )
    return doc


def _review_date(doc: dict[str, Any], label: str) -> date:
    try:
        reviewed = date.fromisoformat(str(doc.get("standard", doc).get("reviewed_at", "")))
    except ValueError as exc:
        raise ValueError(
            f"{label}: reviewed_at 必须是 YYYY-MM-DD"
            "（修复指引：改为 ISO 日期）"
        ) from exc
    if reviewed > date.today():
        raise ValueError(
            f"{label}: reviewed_at 不能晚于当前日期"
            "（修复指引：改为真实复核日期）"
        )
    return reviewed


def _evidence_issues(entries: Any, label: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(entries, list) or not entries:
        return [f"{label}: evidence 必须是非空数组"]
    for value in entries:
        if not isinstance(value, str) or not value:
            issues.append(f"{label}: evidence 项必须是路径或 external: 引用")
            continue
        if value.startswith("external:"):
            if len(value) <= len("external:"):
                issues.append(f"{label}: external evidence 缺标识")
            continue
        if not (ROOT / value).exists():
            issues.append(f"{label}: evidence 路径不存在：{value}")
    return issues


def _matrix_issues(
    path: Path,
    schema: str,
    expected: set[str],
    statuses: set[str],
    id_key: str,
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    doc = _json(path)
    label = str(path.relative_to(ROOT))
    if doc.get("schema") != schema:
        issues.append(f"{label}: schema={doc.get('schema')!r}，应为 {schema!r}")
    standard = doc.get("standard")
    if not isinstance(standard, dict):
        return issues + [f"{label}: 缺 standard 对象"], doc
    for key in ("name", "repository", "commit", "reviewed_at", "scope"):
        if not standard.get(key):
            issues.append(f"{label}: standard 缺 {key}")
    if not isinstance(standard.get("scope"), list) or not standard.get("scope"):
        issues.append(f"{label}: standard.scope 必须是非空数组")
    try:
        _review_date(doc, label)
    except ValueError as exc:
        issues.append(str(exc))
    matrix_key = "controls" if id_key == "id" and schema.startswith("nf-osps") else "requirements"
    entries = doc.get(matrix_key)
    if not isinstance(entries, list):
        return issues + [f"{label}: 矩阵必须是非空数组"], doc
    actual = [entry.get(id_key) for entry in entries if isinstance(entry, dict)]
    if len(actual) != len(set(actual)):
        issues.append(f"{label}: 控制项 ID 重复")
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if missing:
        issues.append(f"{label}: 缺控制项 {missing}")
    if extra:
        issues.append(f"{label}: 未知控制项 {extra}")
    counts: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            issues.append(f"{label}: 控制项必须为对象")
            continue
        ident = str(entry.get(id_key, "?"))
        status = entry.get("status")
        counts[str(status)] = counts.get(str(status), 0) + 1
        if status not in statuses:
            issues.append(f"{label}/{ident}: 非法状态 {status!r}")
        if not entry.get("verification"):
            issues.append(f"{label}/{ident}: 缺 verification")
        if status in {"partial", "not-applicable"} and not entry.get("gap"):
            issues.append(f"{label}/{ident}: {status} 必须记录 gap")
        issues.extend(_evidence_issues(entry.get("evidence"), f"{label}/{ident}"))
    return issues, {"controls": len(entries), "status_counts": dict(sorted(counts.items()))}


def _package_source_issues() -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    path = POLICY_DIR / "package-sources.json"
    doc = _json(path)
    if doc.get("schema") != "nf-package-sources/1":
        issues.append("package-sources.json: schema 不匹配")
    rules = doc.get("rules") or {}
    for key in ("https_only", "embedded_credentials", "mutable_versions", "npm_lifecycle_scripts",
                "lock_or_exact_pins_required"):
        if key not in rules:
            issues.append(f"package-sources.json: rules 缺 {key}")
    if rules.get("https_only") is not True or rules.get("embedded_credentials") is not False:
        issues.append("package-sources.json: HTTPS/凭据规则未 fail-closed")
    if (rules.get("mutable_versions") is not False
            or rules.get("lock_or_exact_pins_required") is not True):
        issues.append("package-sources.json: 可变版本或缺少锁文件规则")
    sources = doc.get("sources")
    if not isinstance(sources, list) or len(sources) < 4:
        return issues + ["package-sources.json: 来源少于 4 个"], {"sources": 0}
    seen = set()
    for source in sources:
        if not isinstance(source, dict):
            issues.append("package-sources.json: source 必须为对象")
            continue
        eco = source.get("ecosystem")
        if eco in seen:
            issues.append(f"package-sources.json: ecosystem 重复：{eco}")
        seen.add(eco)
        url = str(source.get("url", ""))
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            issues.append(f"package-sources.json/{eco}: URL 必须是 HTTPS 且不得含凭据")
        if parsed.hostname not in SOURCE_HOSTS:
            issues.append(f"package-sources.json/{eco}: 未批准主机 {parsed.hostname!r}")
        if not source.get("integrity") or not source.get("update"):
            issues.append(f"package-sources.json/{eco}: 缺 integrity/update")
    return issues, {"sources": len(sources), "ecosystems": sorted(seen)}


def _supplier_issues() -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    path = POLICY_DIR / "suppliers.json"
    doc = _json(path)
    if doc.get("schema") != "nf-supplier-register/1":
        issues.append("suppliers.json: schema 不匹配")
    try:
        reviewed = date.fromisoformat(str(doc.get("reviewed_at", "")))
        review_by = date.fromisoformat(str(doc.get("review_by", "")))
    except ValueError:
        return ["suppliers.json: reviewed_at/review_by 必须是 YYYY-MM-DD"], {"suppliers": 0}
    if review_by < reviewed:
        issues.append("suppliers.json: review_by 早于 reviewed_at")
    allowed = set(doc.get("licenses_allowed") or [])
    suppliers = doc.get("suppliers")
    if not isinstance(suppliers, list) or len(suppliers) < 7:
        return issues + ["suppliers.json: 供应商记录不足"], {"suppliers": 0}
    seen = set()
    decisions: dict[str, int] = {}
    for supplier in suppliers:
        if not isinstance(supplier, dict):
            issues.append("suppliers.json: supplier 必须为对象")
            continue
        ident = str(supplier.get("id", ""))
        if not ident or ident in seen:
            issues.append(f"suppliers.json: 供应商 id 缺失或重复：{ident!r}")
        seen.add(ident)
        decision = supplier.get("decision")
        decisions[str(decision)] = decisions.get(str(decision), 0) + 1
        if decision not in {"approved", "restricted", "prohibited"}:
            issues.append(f"suppliers.json/{ident}: 非法 decision {decision!r}")
        if decision != "approved":
            issues.append(f"suppliers.json/{ident}: 未批准供应商仍在登记表：{decision}")
        for key in ("name", "role", "version", "license", "source", "reason"):
            if not supplier.get(key) and not supplier.get("exception"):
                issues.append(f"suppliers.json/{ident}: 缺 {key}")
        source = urlparse(str(supplier.get("source", "")))
        if source.scheme != "https" or source.username or source.password:
            issues.append(f"suppliers.json/{ident}: source 必须是安全的 HTTPS URL")
        license_id = supplier.get("license")
        if license_id != "service" and license_id not in allowed:
            issues.append(f"suppliers.json/{ident}: 许可证未在 allowlist：{license_id!r}")
    return issues, {
        "suppliers": len(suppliers),
        "decisions": dict(sorted(decisions.items())),
        "review_by": review_by.isoformat(),
    }


def scan(root: Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    global ROOT
    old_root = ROOT
    ROOT = root.resolve()
    try:
        osps_issues, osps_stats = _matrix_issues(
            ROOT / "packaging" / "supply-chain" / "osps-l1-l2.json",
            "nf-osps-evidence/1",
            EXPECTED_OSPS,
            OSPS_STATUSES,
            "id",
        )
        s2_issues, s2_stats = _matrix_issues(
            ROOT / "packaging" / "supply-chain" / "s2c2f-l1-l2.json",
            "nf-s2c2f-evidence/1",
            EXPECTED_S2C2F,
            S2C2F_STATUSES,
            "id",
        )
        source_issues, source_stats = _package_source_issues()
        supplier_issues, supplier_stats = _supplier_issues()
    finally:
        ROOT = old_root
    issues = osps_issues + s2_issues + source_issues + supplier_issues
    return issues, {
        "osps": osps_stats,
        "s2c2f": s2_stats,
        "package_sources": source_stats,
        "suppliers": supplier_stats,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 NinFenz 供应链标准与供应商证据")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        issues, stats = scan(Path(args.root))
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(
            {"issues": issues, "stats": stats},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ))
    else:
        print("== 供应链标准证据 ==")
        print(
            f"  OSPS L1/L2 {stats['osps']['controls']} 条 · "
            f"S2C2F L1/L2 {stats['s2c2f']['controls']} 条 · "
            f"包源 {stats['package_sources']['sources']} 个 · "
            f"供应商 {stats['suppliers']['suppliers']} 个"
        )
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ 证据、状态、来源与许可证策略全部自洽")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
