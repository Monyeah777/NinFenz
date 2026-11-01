#!/usr/bin/env python3
"""Validate the repository's OpenSSF Security Insights v2.2.0 profile."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROFILE_REL = "security-insights.yml"
EVIDENCE_REL = "results/standards/security-insights-validation.json"
SCHEMA_VERSION = "2.2.0"
MAX_AGE_DAYS = 120
REPO = "https://github.com/Monyeah777/NinFenz"
RAW = "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/security-insights.yml"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _mapping(value: Any, label: str, issues: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        issues.append(f"{label} 必须是对象")
        return {}
    return value


def _url(value: Any, label: str, issues: list[str], https: bool = True) -> str:
    text = str(value or "")
    parsed = urlparse(text)
    if not parsed.scheme or (https and parsed.scheme != "https"):
        issues.append(f"{label} 必须是 HTTPS URL（修复指引：填写稳定公开地址）")
    return text


def _date(value: Any, label: str, issues: list[str]) -> dt.date | None:
    text = str(value or "")
    if not DATE.fullmatch(text):
        issues.append(f"{label} 必须是 YYYY-MM-DD")
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        issues.append(f"{label} 不是有效日期")
        return None


def _repo_path(value: str) -> str | None:
    prefixes = (
        REPO + "/blob/main/",
        "https://raw.githubusercontent.com/Monyeah777/NinFenz/main/",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix):]
    return None


def _document_urls(doc: dict[str, Any], issues: list[str]) -> list[str]:
    urls: list[str] = []
    project = _mapping(doc.get("project"), "project", issues)
    repository = _mapping(doc.get("repository"), "repository", issues)
    for source, keys, label in (
        (project.get("documentation") or {}, (
            "quickstart-guide", "detailed-guide", "code-of-conduct",
            "release-process", "support-policy", "signature-verification",
        ), "project.documentation"),
        ((project.get("vulnerability-reporting") or {}).get("policy"), (), "vulnerability policy"),
        (repository.get("documentation") or {}, (
            "contributing-guide", "dependency-management-policy",
            "governance", "review-policy", "security-policy",
        ), "repository.documentation"),
        ((repository.get("security") or {}).get("assessments") or {}, (), "security assessment"),
    ):
        if isinstance(source, str):
            urls.append(_url(source, label, issues))
            continue
        docs = _mapping(source, label, issues)
        for key in keys:
            if docs.get(key):
                urls.append(_url(docs[key], f"{label}.{key}", issues))
        if "self" in docs:
            self_doc = _mapping(docs["self"], f"{label}.self", issues)
            if self_doc.get("evidence"):
                urls.append(_url(self_doc["evidence"], f"{label}.self.evidence", issues))
    return urls


def _contact_issues(rows: Any, label: str, issues: list[str]) -> None:
    if not isinstance(rows, list) or not rows:
        issues.append(f"{label} 必须是非空数组")
        return
    primary = 0
    for index, item in enumerate(rows):
        row = _mapping(item, f"{label}[{index}]", issues)
        if not str(row.get("name") or "").strip():
            issues.append(f"{label}[{index}] 缺 name")
        if row.get("primary") is True:
            primary += 1
        if row.get("social"):
            _url(row["social"], f"{label}[{index}].social", issues)
    if primary != 1:
        issues.append(f"{label} 必须恰有一个 primary=true（实际 {primary}）")


def _header_issues(header: dict[str, Any], today: dt.date, issues: list[str]) -> None:
    if header.get("schema-version") != SCHEMA_VERSION:
        issues.append(f"header.schema-version 必须是 {SCHEMA_VERSION}")
    if _url(header.get("url"), "header.url", issues) != RAW:
        issues.append(f"header.url 必须指向 canonical main 分支：{RAW}")
    updated = _date(header.get("last-updated"), "header.last-updated", issues)
    reviewed = _date(header.get("last-reviewed"), "header.last-reviewed", issues)
    if updated and reviewed and updated > reviewed:
        issues.append("header.last-updated 不得晚于 last-reviewed")
    if reviewed and (today - reviewed).days > MAX_AGE_DAYS:
        issues.append(f"Security Insights 已过期（{(today - reviewed).days} 天 > {MAX_AGE_DAYS}）")


def _project_issues(project: dict[str, Any], issues: list[str]) -> None:
    if not str(project.get("name") or "").strip():
        issues.append("project.name 不得为空")
    if _url(project.get("homepage"), "project.homepage", issues) != "https://ninfenz.dev/":
        issues.append("project.homepage 必须指向 https://ninfenz.dev/")
    _contact_issues(project.get("administrators"), "project.administrators", issues)
    repos = project.get("repositories")
    if not isinstance(repos, list) or not repos:
        issues.append("project.repositories 必须非空")
    elif not any(row.get("url") == REPO for row in repos if isinstance(row, dict)):
        issues.append("project.repositories 必须包含 canonical repository")
    vuln = _mapping(
        project.get("vulnerability-reporting"),
        "project.vulnerability-reporting",
        issues,
    )
    if vuln.get("reports-accepted") is not True:
        issues.append("vulnerability-reporting.reports-accepted 必须为 true")
    if vuln.get("bug-bounty-available") is not False:
        issues.append("bug-bounty-available 必须与实际能力一致，当前为 false")


def _repository_issues(repository: dict[str, Any], issues: list[str]) -> None:
    if _url(repository.get("url"), "repository.url", issues) != REPO:
        issues.append("repository.url 必须是 canonical repository")
    if repository.get("status") != "active":
        issues.append("repository.status 必须是 active")
    for key in ("accepts-change-request", "accepts-automated-change-request"):
        if repository.get(key) is not True:
            issues.append(f"repository.{key} 必须为 true")
    _contact_issues(repository.get("core-team"), "repository.core-team", issues)
    license_doc = _mapping(repository.get("license"), "repository.license", issues)
    if "AGPL-3.0-only" not in str(license_doc.get("expression") or ""):
        issues.append("repository.license.expression 缺 AGPL-3.0-only")


def _release_issues(release: dict[str, Any], issues: list[str]) -> None:
    if release.get("automated-pipeline") is not True:
        issues.append("release.automated-pipeline 必须为 true")
    distributions = release.get("distribution-points")
    if not isinstance(distributions, list) or not any(
        row.get("uri") == "pkg:npm/ninfenz" for row in distributions if isinstance(row, dict)
    ):
        issues.append("release.distribution-points 必须包含 pkg:npm/ninfenz")
    attestations = release.get("attestations")
    predicates = {
        row.get("predicate-uri") for row in attestations or [] if isinstance(row, dict)
    }
    for predicate in (
        "https://slsa.dev/provenance/v1",
        "https://slsa.dev/verification_summary/v1",
        "https://openvex.dev/ns/v0.2.0",
    ):
        if predicate not in predicates:
            issues.append(f"release.attestations 缺 {predicate}")


def _tool_issues(security: dict[str, Any], issues: list[str]) -> None:
    tools = security.get("tools")
    if not isinstance(tools, list) or len(tools) < 5:
        issues.append("repository.security.tools 少于 5 条")
    else:
        types = {row.get("type") for row in tools if isinstance(row, dict)}
        for tool_type in ("SAST", "SCA", "fuzzing"):
            if tool_type not in types:
                issues.append(f"repository.security.tools 缺 {tool_type}")
        for index, row in enumerate(tools):
            integration = _mapping(row.get("integration"), f"tools[{index}].integration", issues)
            if not any(integration.get(key) is True for key in ("adhoc", "ci", "release")):
                issues.append(f"tools[{index}] 至少一个集成面必须为 true")


def validate_doc(
    root: Path, doc: dict[str, Any], today: dt.date | None = None
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    today = today or dt.date.today()
    header = _mapping(doc.get("header"), "header", issues)
    project = _mapping(doc.get("project"), "project", issues)
    repository = _mapping(doc.get("repository"), "repository", issues)
    _header_issues(header, today, issues)
    _project_issues(project, issues)
    _repository_issues(repository, issues)
    _release_issues(_mapping(repository.get("release"), "repository.release", issues), issues)
    _tool_issues(_mapping(repository.get("security"), "repository.security", issues), issues)
    release = repository.get("release") or {}
    security = repository.get("security") or {}
    attestations = release.get("attestations") or []
    tools = security.get("tools") or []
    repos = project.get("repositories") or []
    for url in _document_urls(doc, issues):
        rel = _repo_path(url)
        if rel and not (root / rel).is_file():
            issues.append(f"引用的仓内证据不存在：{rel}")
    stats = {
        "schema_version": SCHEMA_VERSION,
        "tools": len(tools or []),
        "attestations": len(attestations or []),
        "repositories": len(repos or []),
    }
    return issues, stats


def scan(
    root: str | Path = ROOT, today: dt.date | None = None
) -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    path = root / PROFILE_REL
    try:
        import yaml
    except ImportError:
        return ["缺 PyYAML（修复指引：pip install -r .github/requirements-ci.txt）"], {}
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return [f"{PROFILE_REL} 不可读：{exc}（修复指引：恢复有效 UTF-8 YAML）"], {}
    if not isinstance(doc, dict):
        return [f"{PROFILE_REL} 顶层必须是对象"], {}
    issues, stats = validate_doc(root, doc, today)
    stats["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    evidence_path = root / EVIDENCE_REL
    if not evidence_path.is_file():
        issues.append(
            f"缺 {EVIDENCE_REL}（修复指引：用 CUE 2.2.0 官方 schema 完成 cue vet 后留证）"
        )
    else:
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append(f"{EVIDENCE_REL} 不可读：{exc}")
        else:
            if evidence.get("subject_sha256") != stats["sha256"]:
                issues.append(f"{EVIDENCE_REL} 与当前 Security Insights 摘要不一致")
            if evidence.get("cue_vet") != "PASS":
                issues.append(f"{EVIDENCE_REL} 缺官方 cue vet PASS 证据")
    return issues, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 OpenSSF Security Insights v2.2.0")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    issues, stats = scan(args.root)
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats}, ensure_ascii=False,
                         indent=2, sort_keys=True))
    else:
        print(f"== OpenSSF Security Insights {SCHEMA_VERSION} ==\n"
              f"  工具 {stats.get('tools', 0)} · 声明来源证明 {stats.get('attestations', 0)}")
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ 标准字段、仓内证据与官方 cue vet 留证一致")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
