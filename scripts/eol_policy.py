#!/usr/bin/env python3
"""Validate support windows for declared Python, Node, and container runtimes.

This closes the repository-controlled portion of S2C2F SCA-3. The policy is a
pinned snapshot, while every declared runtime occurrence is discovered from the
same manifests and workflows that drive builds. Unknown or expired versions fail
closed; an approaching EOL is reported as a warning.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
POLICY_REL = "packaging/supply-chain/eol-support.json"
SCHEMA = "nf-eol-support/1"

PY_WORKFLOW = re.compile(r"(?m)^\s*python-version:\s*['\"]?([0-9]+\.[0-9]+)")
NODE_WORKFLOW = re.compile(r"(?m)^\s*node-version:\s*['\"]?([0-9]+(?:\.[0-9]+)?)")
PY_DOCKER = re.compile(r"\bpython:([0-9]+\.[0-9]+)")
NODE_DOCKER = re.compile(r"\bnode:([0-9]+)")
PY_REQUIRES = re.compile(
    r"(?m)^requires-python\s*=\s*['\"]>=\s*([0-9]+\.[0-9]+)(?:,\s*<([0-9]+\.[0-9]+))?['\"]"
)
NODE_RANGE = re.compile(r"(?<![\d.])(\d+)(?:\.\d+){0,2}")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: 不可读 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def _parse_day(value: Any, label: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{label}: 必须是 YYYY-MM-DD") from exc


def _runtime_matrix(
    doc: dict[str, Any], today: dt.date
) -> tuple[list[str], dict[str, Any], set[str], set[str]]:
    issues: list[str] = []
    runtimes = doc.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        return ["eol-support.json: runtimes 必须是非空数组"], {}, set(), set()
    warn_days = int(doc.get("warn_before_eol_days", 90))
    seen: set[str] = set()
    pythons: set[str] = set()
    nodes: set[str] = set()
    soon: list[str] = []
    for row in runtimes:
        if not isinstance(row, dict):
            issues.append("eol-support.json: runtime 必须是对象")
            continue
        ident = str(row.get("id") or "")
        ecosystem = str(row.get("ecosystem") or "")
        version = str(row.get("version") or "")
        if not ident or ident in seen:
            issues.append(f"eol-support.json: runtime id 缺失或重复：{ident!r}")
        seen.add(ident)
        if ecosystem not in {"python", "node"}:
            issues.append(f"eol-support.json/{ident}: 未知 ecosystem {ecosystem!r}")
            continue
        if not version:
            issues.append(f"eol-support.json/{ident}: 缺 version")
            continue
        if ecosystem == "python":
            pythons.add(version)
        else:
            nodes.add(version)
        try:
            eol = _parse_day(row.get("eol"), f"eol-support.json/{ident}.eol")
        except ValueError as exc:
            issues.append(str(exc))
            continue
        source = urlparse(str(row.get("source") or ""))
        if source.scheme != "https" or not source.hostname:
            issues.append(f"eol-support.json/{ident}: source 必须是 HTTPS URL")
        if eol < today:
            issues.append(f"eol-support.json/{ident}: EOL {eol.isoformat()} 已过期")
        elif (eol - today).days <= warn_days:
            soon.append(f"{ident}@{version}（剩余 {(eol - today).days} 天）")
    stats = {"runtimes": len(runtimes), "expiring_soon": soon}
    return issues, stats, pythons, nodes


def _py_requires_issues(root: Path, declarations: list[str], pythons: set[str]) -> list[str]:
    issues: list[str] = []
    for rel in declarations:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            issues.append(f"{rel}: 无法读取 requires-python")
            continue
        match = PY_REQUIRES.search(text)
        if not match:
            issues.append(f"{rel}: 缺 >=X.Y 形式的 requires-python")
        elif match.group(1) not in pythons:
            issues.append(f"{rel}: requires-python 下限 {match.group(1)} 不在支持矩阵")
    return issues


def _node_engines_issues(root: Path, rel: str, nodes: set[str]) -> list[str]:
    try:
        doc = _json(root / rel)
    except ValueError as exc:
        return [str(exc)]
    expression = str((doc.get("engines") or {}).get("node") or "")
    if not expression:
        return [f"{rel}: 缺 engines.node"]
    majors = set(NODE_RANGE.findall(expression))
    if not majors:
        return [f"{rel}: engines.node 无法解析：{expression!r}"]
    return [
        f"{rel}: engines.node 引用不受支持的 Node {major}（{expression}）"
        for major in sorted(majors - nodes)
    ]


def _docker_issues(
    root: Path, declarations: list[str], pythons: set[str], nodes: set[str]
) -> list[str]:
    issues: list[str] = []
    for rel in declarations:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            issues.append(f"{rel}: Dockerfile 不存在或不可读")
            continue
        if "@sha256:" not in text:
            issues.append(f"{rel}: 运行镜像未固定 digest")
        for version in sorted(set(PY_DOCKER.findall(text)) - pythons):
            issues.append(f"{rel}: 使用不受支持的 Python {version}")
        for version in sorted(set(NODE_DOCKER.findall(text)) - nodes):
            issues.append(f"{rel}: 使用不受支持的 Node {version}")
    return issues


def _workflow_issues(
    root: Path, pattern: str, pythons: set[str], nodes: set[str]
) -> tuple[list[str], int]:
    issues: list[str] = []
    checked = 0
    for path in sorted(root.glob(pattern)):
        checked += 1
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        for version in sorted(set(PY_WORKFLOW.findall(text)) - pythons):
            issues.append(f"{rel}: 使用不受支持的 Python {version}")
        observed_nodes = {version.split(".", 1)[0]
                          for version in NODE_WORKFLOW.findall(text)}
        for version in sorted(observed_nodes - nodes):
            issues.append(f"{rel}: 使用不受支持的 Node {version}")
    if not checked:
        issues.append(f"{pattern}: 未发现工作流")
    return issues, checked


def scan(
    root: str | Path = ROOT, today: dt.date | None = None
) -> tuple[list[str], list[str], dict[str, Any]]:
    root = Path(root).resolve()
    today = today or dt.date.today()
    try:
        doc = _json(root / POLICY_REL)
    except ValueError as exc:
        return [str(exc)], [], {"runtimes": 0}
    issues: list[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append(f"{POLICY_REL}: schema 必须是 {SCHEMA}")
    try:
        reviewed = _parse_day(doc.get("reviewed_at"), f"{POLICY_REL}.reviewed_at")
    except ValueError as exc:
        return issues + [str(exc)], [], {"runtimes": 0}
    max_age = int(doc.get("max_review_age_days", 90))
    if reviewed > today:
        issues.append(f"{POLICY_REL}: reviewed_at 不能晚于今天")
    if (today - reviewed).days > max_age:
        issues.append(f"{POLICY_REL}: 支持矩阵已过期（{(today - reviewed).days} 天 > {max_age}）")
    matrix_issues, stats, pythons, nodes = _runtime_matrix(doc, today)
    issues.extend(matrix_issues)
    declares = doc.get("declarations") or {}
    issues.extend(_py_requires_issues(root, list(declares.get("python_requires") or []), pythons))
    if node_rel := declares.get("node_engines"):
        issues.extend(_node_engines_issues(root, str(node_rel), nodes))
    else:
        issues.append(f"{POLICY_REL}: declarations 缺 node_engines")
    issues.extend(_docker_issues(root, list(declares.get("dockerfiles") or []), pythons, nodes))
    workflow_issues, workflow_count = _workflow_issues(
        root, str(declares.get("workflows") or ""), pythons, nodes
    )
    issues.extend(workflow_issues)
    stats.update({
        "python_versions": sorted(pythons),
        "node_majors": sorted(nodes, key=int),
        "workflows": workflow_count,
    })
    warns = [f"临近 EOL：{item}" for item in stats.get("expiring_soon", [])]
    return issues, warns, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 Python/Node/容器运行时 EOL 支持窗口")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    issues, warns, stats = scan(args.root)
    if args.json:
        print(json.dumps(
            {"issues": issues, "warns": warns, "stats": stats},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ))
    else:
        print(
            f"== 运行时 EOL 支持矩阵 ==\n"
            f"  组件 {stats['runtimes']} 个 · 工作流 {stats['workflows']} 个"
        )
        for warning in warns:
            print(f"  ! {warning}")
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ 声明运行时均在支持窗口内")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
