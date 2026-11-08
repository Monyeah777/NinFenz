"""Fail-closed readiness checks for the SLSA v1.2 Source Track."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import json_doc

READINESS_REL = "packaging/supply-chain/slsa-source-readiness.json"
CONTROLS_REL = "results/supply-chain/github-source-controls.json"
REPOSITORY_URL = "https://github.com/Monyeah777/NinFenz"
REPOSITORY_API = "repos/Monyeah777/NinFenz"
EXPECTED_REQUIREMENTS = {
    "source-control-system",
    "identity-management",
    "immutable-revisions",
    "human-readable-changes",
    "history-continuity",
    "safe-expunging",
    "protected-named-references",
    "continuous-controls",
    "source-vsa",
    "source-provenance",
    "two-party-review",
}
REQUIRED_RULES = {"deletion", "non_fast_forward", "required_status_checks", "pull_request"}
REQUIRED_TAG_RULES = {"deletion", "non_fast_forward", "update"}
REQUIRED_STATUS_CHECKS = {"gate", "static-checks-42"}
VALID_STATUS = {"satisfied", "partial", "blocked", "not-applicable"}


def _json(path: Path) -> dict[str, Any]:
    return json_doc.load(path, dict, what=str(path))


def _repository_issues(snapshot: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if snapshot.get("schema") != "nf-github-source-controls/1":
        issues.append(f"{CONTROLS_REL}: schema must be nf-github-source-controls/1")
    repo = snapshot.get("repository")
    if not isinstance(repo, dict):
        return issues + [f"{CONTROLS_REL}: repository must be an object"]
    if repo.get("url") != REPOSITORY_URL:
        issues.append(f"{CONTROLS_REL}: repository URL is not canonical")
    if not isinstance(repo.get("id"), int) or repo["id"] < 1:
        issues.append(f"{CONTROLS_REL}: repository id must be a positive integer")
    if repo.get("default_branch") != "main":
        issues.append(f"{CONTROLS_REL}: default branch must be main")
    try:
        datetime.fromisoformat(str(snapshot.get("collected_at") or "").replace("Z", "+00:00"))
    except ValueError:
        issues.append(f"{CONTROLS_REL}: collected_at must be ISO-8601")
    return issues


def _branch_issues(snapshot: dict[str, Any]) -> list[str]:
    branch = snapshot.get("branch_protection")
    if not isinstance(branch, dict):
        return [f"{CONTROLS_REL}: branch_protection must be an object"]
    issues: list[str] = []
    if branch.get("allow_force_pushes") is not False:
        issues.append(f"{CONTROLS_REL}: main must forbid force push")
    if branch.get("allow_deletions") is not False:
        issues.append(f"{CONTROLS_REL}: main must forbid deletion")
    for key in (
        "enforce_admins",
        "required_linear_history",
        "required_conversation_resolution",
    ):
        if branch.get(key) is not True:
            issues.append(f"{CONTROLS_REL}: branch_protection.{key} must be true")
    checks = branch.get("required_status_checks")
    if not isinstance(checks, list) or not checks:
        issues.append(f"{CONTROLS_REL}: required status checks must be non-empty")
    elif not REQUIRED_STATUS_CHECKS.issubset(set(checks)):
        issues.append(
            f"{CONTROLS_REL}: required status checks must include gate and static-checks-42"
        )
    if branch.get("strict_status_checks") is not True:
        issues.append(f"{CONTROLS_REL}: status checks must require an up-to-date branch")
    return issues


def _rule_types(ruleset: dict[str, Any]) -> set[str]:
    return {str(rule.get("type")) for rule in ruleset.get("rules") or [] if isinstance(rule, dict)}


def _ruleset_common_issues(label: str, ruleset: Any) -> list[str]:
    if not isinstance(ruleset, dict):
        return [f"{CONTROLS_REL}: {label} ruleset is missing"]
    issues: list[str] = []
    if ruleset.get("enforcement") != "active":
        issues.append(f"{CONTROLS_REL}: {label} ruleset must be active")
    if ruleset.get("bypass_actors"):
        issues.append(f"{CONTROLS_REL}: {label} ruleset must not allow bypass actors")
    return issues


def _branch_ruleset_issues(snapshot: dict[str, Any]) -> list[str]:
    ruleset = snapshot.get("branch_ruleset")
    issues = _ruleset_common_issues("branch", ruleset)
    if not isinstance(ruleset, dict):
        return issues
    if ruleset.get("target") != "branch":
        issues.append(f"{CONTROLS_REL}: branch ruleset target must be branch")
    include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    if "~DEFAULT_BRANCH" not in include:
        issues.append(f"{CONTROLS_REL}: branch ruleset must protect the default branch")
    missing = sorted(REQUIRED_RULES - _rule_types(ruleset))
    if missing:
        issues.append(f"{CONTROLS_REL}: branch ruleset missing rules {missing}")
    return issues


def _tag_ruleset_issues(snapshot: dict[str, Any]) -> list[str]:
    ruleset = snapshot.get("tag_ruleset")
    issues = _ruleset_common_issues("tag", ruleset)
    if not isinstance(ruleset, dict):
        return issues
    if ruleset.get("target") != "tag":
        issues.append(f"{CONTROLS_REL}: tag ruleset target must be tag")
    include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
    if "refs/tags/v*" not in include:
        issues.append(f"{CONTROLS_REL}: tag ruleset must protect refs/tags/v*")
    missing = sorted(REQUIRED_TAG_RULES - _rule_types(ruleset))
    if missing:
        issues.append(f"{CONTROLS_REL}: tag ruleset missing rules {missing}")
    return issues


def _requirements_issues(readiness: dict[str, Any]) -> list[str]:
    rows = readiness.get("requirements")
    if not isinstance(rows, list):
        return [f"{READINESS_REL}: requirements must be a list"]
    issues: list[str] = []
    ids = [str(row.get("id")) for row in rows if isinstance(row, dict)]
    if set(ids) != EXPECTED_REQUIREMENTS:
        issues.append(f"{READINESS_REL}: requirement ids do not match the Source Track matrix")
    for row in rows:
        if not isinstance(row, dict):
            issues.append(f"{READINESS_REL}: each requirement must be an object")
            continue
        ident = str(row.get("id") or "?")
        if row.get("status") not in VALID_STATUS:
            issues.append(f"{READINESS_REL}/{ident}: invalid status")
        if not str(row.get("reason") or "").strip():
            issues.append(f"{READINESS_REL}/{ident}: reason is required")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append(f"{READINESS_REL}/{ident}: evidence must be non-empty")
    return issues


def _claim_issues(readiness: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    claimed = readiness.get("claimed_level")
    target = readiness.get("target_level")
    if not isinstance(claimed, int) or not 0 <= claimed <= 4:
        issues.append(f"{READINESS_REL}: claimed_level must be 0..4")
        claimed = 0
    if not isinstance(target, int) or not 1 <= target <= 4:
        issues.append(f"{READINESS_REL}: target_level must be 1..4")
    attestations = readiness.get("platform_attestations")
    if not isinstance(attestations, dict):
        return issues + [f"{READINESS_REL}: platform_attestations must be an object"]
    labels = {
        "source_vsa": "Source VSA",
        "source_provenance": "Source Provenance",
    }
    for key, label in labels.items():
        if attestations.get(key) not in (True, False):
            issues.append(f"{READINESS_REL}: platform_attestations.{key} must be boolean")
        if attestations.get(key) is True and not str(
            attestations.get(key + "_url") or ""
        ).startswith("https://"):
            issues.append(f"{READINESS_REL}: {label} evidence URL is required")
    if claimed > 0:
        for key, label in labels.items():
            if attestations.get(key) is not True:
                issues.append(f"{READINESS_REL}: level >0 requires {label}")
    return issues


def scan_documents(
    readiness: dict[str, Any], controls: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    if readiness.get("schema") != "nf-slsa-source-readiness/1":
        issues.append(f"{READINESS_REL}: invalid schema")
    if readiness.get("standard") != "SLSA v1.2 Source Track":
        issues.append(f"{READINESS_REL}: standard must be SLSA v1.2 Source Track")
    issues.extend(_requirements_issues(readiness))
    issues.extend(_claim_issues(readiness))
    issues.extend(_repository_issues(controls))
    issues.extend(_branch_issues(controls))
    issues.extend(_branch_ruleset_issues(controls))
    issues.extend(_tag_ruleset_issues(controls))
    statuses: dict[str, int] = {}
    for row in readiness.get("requirements") or []:
        if isinstance(row, dict):
            status = str(row.get("status"))
            statuses[status] = statuses.get(status, 0) + 1
    attestations = readiness.get("platform_attestations") or {}
    return issues, {
        "claimed_level": readiness.get("claimed_level"),
        "target_level": readiness.get("target_level"),
        "requirement_statuses": dict(sorted(statuses.items())),
        "source_vsa_available": attestations.get("source_vsa") is True,
        "source_provenance_available": attestations.get("source_provenance") is True,
        "technical_controls": "enforced",
    }


def scan(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root)
    try:
        readiness = _json(root / READINESS_REL)
        controls = _json(root / CONTROLS_REL)
    except (OSError, ValueError) as exc:
        return [f"SLSA Source readiness unreadable: {exc}"], {}
    return scan_documents(readiness, controls)


def _protection(raw: dict[str, Any]) -> dict[str, Any]:
    reviews = raw.get("required_pull_request_reviews") or {}
    checks = raw.get("required_status_checks") or {}
    return {
        "allow_force_pushes": bool((raw.get("allow_force_pushes") or {}).get("enabled")),
        "allow_deletions": bool((raw.get("allow_deletions") or {}).get("enabled")),
        "enforce_admins": bool((raw.get("enforce_admins") or {}).get("enabled")),
        "required_linear_history": bool((raw.get("required_linear_history") or {}).get("enabled")),
        "required_conversation_resolution": bool(
            (raw.get("required_conversation_resolution") or {}).get("enabled")
        ),
        "required_status_checks": sorted(checks.get("contexts") or []),
        "strict_status_checks": checks.get("strict") is True,
        "dismiss_stale_reviews": reviews.get("dismiss_stale_reviews") is True,
        "required_approving_review_count": int(reviews.get("required_approving_review_count") or 0),
    }


def _ruleset(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "target": raw.get("target"),
        "enforcement": raw.get("enforcement"),
        "conditions": raw.get("conditions") or {"ref_name": {"include": []}},
        "rules": [item for item in raw.get("rules") or [] if isinstance(item, dict)],
        "bypass_actors": list(raw.get("bypass_actors") or []),
    }


def collect(api: Callable[[str], Any], collected_at: str) -> dict[str, Any]:
    repo = api(REPOSITORY_API)
    protection = api(f"{REPOSITORY_API}/branches/main/protection")
    summaries = api(f"{REPOSITORY_API}/rulesets")
    details = [
        _ruleset(api(f"{REPOSITORY_API}/rulesets/{item['id']}"))
        for item in summaries
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    branch = next((item for item in details if item.get("target") == "branch"), None)
    tag = next((item for item in details if item.get("target") == "tag"), None)
    return {
        "schema": "nf-github-source-controls/1",
        "collected_at": collected_at,
        "repository": {
            "id": repo.get("id"),
            "url": repo.get("html_url"),
            "default_branch": repo.get("default_branch"),
            "visibility": repo.get("visibility"),
        },
        "branch_protection": _protection(protection),
        "branch_ruleset": branch,
        "tag_ruleset": tag,
    }


__all__ = [
    "CONTROLS_REL",
    "EXPECTED_REQUIREMENTS",
    "READINESS_REL",
    "REPOSITORY_API",
    "REPOSITORY_URL",
    "collect",
    "scan",
    "scan_documents",
]
