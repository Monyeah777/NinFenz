"""Explicit registry for audit records created before the audit protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.library import parse_frontmatter


def records(decl: dict[str, Any]) -> list[dict[str, str]]:
    """Return normalized legacy records from the protocol declaration."""
    raw = decl.get("legacy_records")
    if not isinstance(raw, dict):
        return []
    paths = raw.get("paths")
    if not isinstance(paths, list):
        return []
    rows = []
    for item in paths:
        if isinstance(item, dict) and str(item.get("path") or "").strip():
            rows.append({"path": str(item["path"]).replace("\\", "/"),
                         "reason": str(item.get("reason") or "").strip()})
        elif isinstance(item, str) and item.strip():
            rows.append({"path": item.replace("\\", "/"), "reason": ""})
    return rows


def validation_issues(root: str, decl: dict[str, Any]) -> list[str]:
    """Validate that every legacy exemption is explicit, local and still needed."""
    issues: list[str] = []
    raw = decl.get("legacy_records")
    if raw is not None and not isinstance(raw, dict):
        return ["legacy_records 须为对象"]
    if isinstance(raw, dict) and not isinstance(raw.get("paths"), list):
        return ["legacy_records.paths 须为列表"]
    rows = records(decl)
    paths = [row["path"] for row in rows]
    if len(paths) != len(set(paths)):
        issues.append("legacy_records.paths 不得重复")
    for row in rows:
        rel = row["path"]
        path = Path(rel)
        target = Path(root) / rel
        if path.is_absolute() or ".." in path.parts:
            issues.append(f"legacy_records 路径不得逃出仓库：{rel}")
        elif path.parent.as_posix() != "results/audit" or path.suffix != ".md":
            issues.append(f"legacy_records 只能登记 results/audit/*.md：{rel}")
        elif not target.is_file():
            issues.append(f"legacy_records 指向不存在的审计件：{rel}")
        elif not row["reason"]:
            issues.append(f"legacy_records 必须为每件写明保留理由：{rel}")
        else:
            fm, _ = parse_frontmatter(target.read_text(encoding="utf-8"))
            if (fm or {}).get("id"):
                issues.append(f"legacy_records 条目已具备审计 id，应从清单移除：{rel}")
    return issues


def registered_paths(decl: dict[str, Any]) -> set[str]:
    return {row["path"] for row in records(decl)}


def is_legacy(rel: str, decl: dict[str, Any], has_id: bool) -> bool:
    """A record is legacy only when explicitly registered and still lacks an id."""
    return not has_id and rel.replace("\\", "/") in registered_paths(decl)
