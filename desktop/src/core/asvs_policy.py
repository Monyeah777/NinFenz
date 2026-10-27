"""Fail-closed validator for the scoped OWASP ASVS 5.0.0 L2 evidence matrix."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

MATRIX_REL = Path("packaging/security/asvs-5.0.0-l2.json")
SCHEMA = "nf-asvs-evidence/1"
VERSION = "5.0.0"
COMMIT = "5cf9b032440be53ce345ab3c130fda46ba1ce7a2"
SCOPE = {"V1", "V2", "V4", "V5", "V6", "V7", "V8",
         "V11", "V12", "V13", "V14", "V15", "V16"}
STATUSES = {"enforced", "partial", "not-applicable"}
EXPECTED_COUNT = 191
EXPECTED_ID_DIGEST = "3a9188535468fd49708af56c499362a15ef47d9e1624756b8d122f2280490362"
CRITICAL_ENFORCED = {
    "V1.2.5", "V1.5.2", "V5.3.2", "V7.2.3", "V8.3.1",
    "V11.5.1", "V13.4.1", "V15.3.3", "V16.4.1", "V16.5.1",
}
_ID = re.compile(r"^V(?:[1-9]|1[0-7])\.\d+\.\d+$")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def _natural(ident: str) -> tuple[int, ...]:
    return tuple(int(part) for part in ident.removeprefix("V").split("."))


def scan(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root)
    issues: list[str] = []
    path = root / MATRIX_REL
    try:
        doc = _json(path)
    except (OSError, ValueError):
        return [f"{MATRIX_REL}: 不可读或非法（修复指引：恢复或重生成 ASVS 矩阵）"], {}
    if doc.get("schema") != SCHEMA:
        issues.append(f"{MATRIX_REL}: schema 不匹配")
    standard = doc.get("standard")
    if not isinstance(standard, dict):
        return issues + [f"{MATRIX_REL}: 缺 standard 对象"], {}
    if standard.get("version") != VERSION or standard.get("commit") != COMMIT:
        issues.append(f"{MATRIX_REL}: ASVS 版本或提交未固定在 5.0.0/{COMMIT}")
    scope = set(standard.get("scope") or [])
    if scope != SCOPE:
        issues.append(f"{MATRIX_REL}: 作用域章节不一致：{sorted(scope)}")
    excluded = standard.get("excluded_chapters")
    if not isinstance(excluded, dict) or set(excluded) != {"V3", "V9", "V10", "V17"}:
        issues.append(f"{MATRIX_REL}: 排除章节及理由不完整")
    elif any(not str(excluded[key]).strip() for key in excluded):
        issues.append(f"{MATRIX_REL}: 排除章节缺理由")
    claim = doc.get("claim") or {}
    if not isinstance(claim, dict) or claim.get("certified") is not False:
        issues.append(f"{MATRIX_REL}: 不得声称第三方 ASVS 认证")
    entries = doc.get("requirements")
    if not isinstance(entries, list):
        return issues + [f"{MATRIX_REL}: requirements 必须是数组"], {}
    if len(entries) != EXPECTED_COUNT:
        issues.append(f"{MATRIX_REL}: 需求数量 {len(entries)} != {EXPECTED_COUNT}")
    ids: list[str] = []
    statuses: dict[str, int] = {}
    coverage: dict[str, dict[str, int]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            issues.append(f"{MATRIX_REL}: requirement 必须是对象")
            continue
        ident = str(entry.get("id") or "")
        ids.append(ident)
        if not _ID.match(ident):
            issues.append(f"{MATRIX_REL}/{ident}: 非法 ASVS ID")
        chapter = ident.split(".", 1)[0]
        if chapter not in SCOPE:
            issues.append(f"{MATRIX_REL}/{ident}: 章节不在作用域")
        status = str(entry.get("status") or "")
        statuses[status] = statuses.get(status, 0) + 1
        coverage.setdefault(chapter, {})
        coverage[chapter][status] = coverage[chapter].get(status, 0) + 1
        if status not in STATUSES:
            issues.append(f"{MATRIX_REL}/{ident}: 非法状态 {status!r}")
        if not str(entry.get("verification") or "").strip():
            issues.append(f"{MATRIX_REL}/{ident}: 缺 verification")
        if status in {"partial", "not-applicable"} and not str(entry.get("gap") or "").strip():
            issues.append(f"{MATRIX_REL}/{ident}: {status} 必须记录 gap")
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append(f"{MATRIX_REL}/{ident}: evidence 必须是非空数组")
            continue
        for item in evidence:
            if not isinstance(item, str) or not item:
                issues.append(f"{MATRIX_REL}/{ident}: evidence 项非法")
            elif not item.startswith("external:") and not (root / item).exists():
                issues.append(f"{MATRIX_REL}/{ident}: evidence 路径不存在：{item}")
    if len(ids) != len(set(ids)):
        issues.append(f"{MATRIX_REL}: 需求 ID 重复")
    ordered = sorted(ids, key=_natural)
    digest = hashlib.sha256("\n".join(ordered).encode()).hexdigest()
    if digest != EXPECTED_ID_DIGEST:
        issues.append(f"{MATRIX_REL}: 需求 ID 集合漂移（{digest}）")
    if doc.get("requirement_id_digest") != digest:
        issues.append(f"{MATRIX_REL}: 矩阵记录的需求摘要已过期")
    missing_critical = sorted(CRITICAL_ENFORCED - {
        str(entry.get("id")) for entry in entries
        if isinstance(entry, dict) and entry.get("status") == "enforced"
    })
    if missing_critical:
        issues.append(f"{MATRIX_REL}: 关键控制未 enforced：{missing_critical}")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") not in CRITICAL_ENFORCED:
            continue
        evidence = entry.get("evidence") or []
        if not any(str(item).startswith("desktop/tests/") for item in evidence):
            issues.append(
                f"{MATRIX_REL}/{entry.get('id')}: enforced 的关键控制必须有测试证据"
            )
    return issues, {
        "requirements": len(entries),
        "statuses": dict(sorted(statuses.items())),
        "chapters": sorted(coverage, key=lambda item: int(item[1:])),
        "coverage": {key: dict(sorted(value.items()))
                     for key, value in sorted(coverage.items(),
                                              key=lambda item: int(item[0][1:]))},
    }
