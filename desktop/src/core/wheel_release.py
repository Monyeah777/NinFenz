"""Deterministic metadata and verification for the PyO3/Maturin wheel."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from . import json_doc

SCHEMA = "nf-python-wheel/1"
PACKAGE = "ninfenz-pyengine"
SUM_RE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")
WHEEL_RE = re.compile(
    r"^ninfenz_pyengine-(?P<version>[^-]+)-cp311-cp311-"
    r"manylinux_2_28_(?P<arch>x86_64|aarch64)\.whl$"
)


def _version(wheel: Path) -> str:
    match = WHEEL_RE.match(wheel.name)
    if not match:
        raise ValueError(
            f"{wheel.name}: 非法 PyO3 wheel 文件名"
            "（修复指引：使用 CPython 3.11 manylinux_2_28 wheel）"
        )
    return match.group("version")


def metadata(
    wheel: Path,
    *,
    source_commit: str,
    source_date_epoch: int,
    rustc: str,
    maturin: str,
    python: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source_commit 必须是 40 位提交 SHA（修复指引：传入 GITHUB_SHA）")
    if source_date_epoch < 1:
        raise ValueError("source_date_epoch 必须是正整数（修复指引：取 git commit timestamp）")
    data = wheel.read_bytes()
    return {
        "schema": SCHEMA,
        "package": PACKAGE,
        "version": _version(wheel),
        "filename": wheel.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "source_commit": source_commit,
        "source_date_epoch": source_date_epoch,
        "toolchain": {
            "rustc": rustc,
            "maturin": maturin,
            "python": python,
        },
    }


def write_checksums(path: Path, files: list[Path]) -> None:
    rows = [
        f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}"
        for item in sorted(files, key=lambda item: item.name)
    ]
    path.write_text("\n".join(rows) + "\n", encoding="ascii")


def _sums(path: Path) -> tuple[dict[str, str], list[str]]:
    issues: list[str] = []
    values: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        match = SUM_RE.match(line)
        if not match:
            issues.append(f"非法 WHEEL-SHA256SUMS 行：{line!r}")
            continue
        digest, name = match.groups()
        if name in values:
            issues.append(f"WHEEL-SHA256SUMS 重复路径：{name}")
        values[name] = digest
    return values, issues


def _metadata_issues(wheel: Path, doc: dict[str, Any], source_commit: str) -> list[str]:
    issues: list[str] = []
    expected = {
        "schema": SCHEMA,
        "package": PACKAGE,
        "filename": wheel.name,
        "source_commit": source_commit,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "size": wheel.stat().st_size,
    }
    for key, value in expected.items():
        if doc.get(key) != value:
            issues.append(f"wheel metadata {key} 不一致")
    if not isinstance(doc.get("source_date_epoch"), int) or doc["source_date_epoch"] < 1:
        issues.append("wheel metadata source_date_epoch 非法")
    tools = doc.get("toolchain")
    if not isinstance(tools, dict):
        issues.append("wheel metadata 缺 toolchain")
    else:
        for key in ("rustc", "maturin", "python"):
            if not str(tools.get(key) or "").strip():
                issues.append(f"wheel metadata toolchain 缺 {key}")
    return issues


def verify(
    wheel: Path,
    metadata_path: Path,
    checksums_path: Path,
    source_commit: str,
) -> list[str]:
    try:
        doc = json_doc.load(metadata_path, dict, what=str(metadata_path))
        sums, issues = _sums(checksums_path)
    except (OSError, ValueError) as exc:
        return [f"wheel evidence 不可读：{exc}"]
    issues.extend(_metadata_issues(wheel, doc, source_commit))
    for name in (wheel.name, metadata_path.name):
        if name not in sums:
            issues.append(f"WHEEL-SHA256SUMS 缺件：{name}")
    for name, digest in sums.items():
        target = wheel.parent / name
        if not target.is_file():
            issues.append(f"WHEEL-SHA256SUMS 指向缺件：{name}")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            issues.append(f"wheel 工件摘要不符：{name}")
    return issues


def verify_release_dir(release: Path, source_commit: str) -> list[str]:
    wheels = sorted(release.glob("*.whl"))
    if len(wheels) != 1:
        return [f"发布目录必须恰有一个 wheel，实际 {len(wheels)}"]
    return verify(
        wheels[0],
        release / "wheel-metadata.json",
        release / "WHEEL-SHA256SUMS",
        source_commit,
    )


__all__ = [
    "PACKAGE",
    "SCHEMA",
    "metadata",
    "verify",
    "verify_release_dir",
    "write_checksums",
]
