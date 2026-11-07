"""Validation for audit subject bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core import paths


def resolve(root: str, rel: str) -> Path:
    """Resolve a repository-relative subject path with containment enforced."""
    return Path(paths.validate_path(root, rel.replace("\\", "/")))


def digest(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: str, subjects: Any) -> tuple[list[str], int]:
    """Check format, containment, existence and current digest for every subject."""
    issues: list[str] = []
    if subjects is None:
        rows = []
    elif isinstance(subjects, str):
        rows = [subjects]
    elif isinstance(subjects, (list, tuple)):
        rows = list(subjects)
    else:
        return ["subjects 须为字符串或列表"], 0
    ok = 0
    for subject in rows:
        text = str(subject).strip()
        if ":" not in text:
            issues.append(f"subjects 条目格式须为 路径:sha256：{text[:40]}")
            continue
        rel, want = text.rsplit(":", 1)
        try:
            path = resolve(root, rel)
        except paths.PathEscapeError as exc:
            issues.append(f"被审对象路径不合法：{rel}（{exc}）")
            continue
        if not path.is_file():
            issues.append(f"被审对象不存在：{rel}")
            continue
        if digest(path) != want.strip():
            issues.append(f"被审对象已变，旧审计失效：{rel}（修复指引：重审并更新 digest）")
            continue
        ok += 1
    return issues, ok
