"""Enforced evidence for the final ASVS controls closed by their own implementations."""
from __future__ import annotations

from typing import Any


def enforcement_map() -> dict[str, tuple[str, list[str]]]:
    return {
        "V5.2.2": (
            "Every accepted local file extension has a fail-closed content validator. The "
            "repository read boundary rejects malformed JSON/JSONL/TOML/YAML/GraphML/XML/CSV/"
            "text and verifies WASM magic/version before processing.",
            [
                "desktop/src/core/file_format.py",
                "desktop/src/core/repo_index.py",
                "desktop/tests/test_file_format.py",
                "packaging/security/application-security-controls.json",
            ],
        ),
        "V11.2.2": (
            "Randomness, digest and constant-time comparison are selected through a versioned "
            "CryptoPolicy suite registry; reviewed suites can be rotated with a documented "
            "migration path while old suite identifiers remain verifiable.",
            [
                "desktop/src/core/crypto_policy.py",
                "desktop/src/core/daemon.py",
                "desktop/tests/test_crypto_policy.py",
                "packaging/security/application-security-controls.json",
            ],
        ),
        "V16.4.2": (
            "Security events are chained in a local tamper-evident audit log and independently "
            "forwarded to the Windows Event Log or POSIX syslog for retention, detection and "
            "escalation outside the NF process.",
            [
                "desktop/src/core/security_audit.py",
                "desktop/tests/test_security_audit.py",
                "packaging/security/application-security-controls.json",
            ],
        ),
        "V16.4.3": (
            "Security events are chained in a local tamper-evident audit log and independently "
            "forwarded to the Windows Event Log or POSIX syslog for retention, detection and "
            "escalation outside the NF process.",
            [
                "desktop/src/core/security_audit.py",
                "desktop/tests/test_security_audit.py",
                "packaging/security/application-security-controls.json",
            ],
        ),
    }


def baseline_issues(
    entries: list[dict[str, Any]],
    statuses: dict[str, int],
    matrix_rel: str,
    critical_enforced: set[str],
) -> list[str]:
    issues: list[str] = []
    missing_critical = sorted(critical_enforced - {
        str(entry.get("id")) for entry in entries
        if isinstance(entry, dict) and entry.get("status") == "enforced"
    })
    if missing_critical:
        issues.append(f"{matrix_rel}: 关键控制未 enforced：{missing_critical}")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") not in critical_enforced:
            continue
        evidence = entry.get("evidence") or []
        if not any(str(item).startswith("desktop/tests/") for item in evidence):
            issues.append(
                f"{matrix_rel}/{entry.get('id')}: enforced 的关键控制必须有测试证据"
            )
    partial_count = statuses.get("partial", 0)
    if partial_count:
        issues.append(
            f"{matrix_rel}: ASVS partial baseline regressed ({partial_count} controls)"
        )
    return issues


__all__ = ["baseline_issues", "enforcement_map"]
