"""Focused validators for application-security inventory sections."""
from __future__ import annotations

from typing import Any

from core import crypto_policy, file_format


def file_handling_issues(files: dict[str, Any], rel: str) -> list[str]:
    issues: list[str] = []
    if not files.get("processing_types"):
        issues.append(f"{rel}: file_handling.processing_types is required")
    if not isinstance(files.get("maximum_sizes"), list):
        issues.append(f"{rel}: file_handling.maximum_sizes is required")
    if not str(files.get("malicious_file_behavior") or "").strip():
        issues.append(f"{rel}: file_handling.malicious_file_behavior is required")
    declared_types = {str(item).lower() for item in files.get("processing_types") or []}
    unsupported_types = sorted(declared_types - file_format.SUPPORTED_SUFFIXES)
    if unsupported_types:
        issues.append(f"{rel}/file_handling: no content validator for {unsupported_types}")
    content_validation = files.get("content_validation")
    if not isinstance(content_validation, dict):
        issues.append(f"{rel}: file_handling.content_validation is required")
    else:
        if content_validation.get("status") != "enforced":
            issues.append(f"{rel}: file content validation must be enforced")
        if "desktop/src/core/file_format.py" not in str(
                content_validation.get("implemented") or ""):
            issues.append(f"{rel}: file content validation is not bound to the validator")
    return issues


def crypto_issues(crypto: dict[str, Any], rel: str) -> tuple[list[str], set[str]]:
    issues: list[str] = []
    approved = set(crypto.get("approved_algorithms") or [])
    expected_algorithms = {
        "secrets.token_hex", "SHA-256", "SHA-512", "hmac.compare_digest",
    }
    if approved != expected_algorithms:
        issues.append(f"{rel}: approved algorithm set drifted")
    agility = crypto.get("agility") or {}
    if agility.get("status") != "enforced":
        issues.append(f"{rel}: cryptographic agility must be enforced")
    declared_suites = set(agility.get("suites") or [])
    if declared_suites != set(crypto_policy.SUITES):
        issues.append(f"{rel}: cryptographic suite registry drifted")
    if not str(agility.get("migration") or "").strip():
        issues.append(f"{rel}: cryptographic migration procedure is required")
    return issues, declared_suites


def logging_issues(logging: dict[str, Any], rel: str) -> list[str]:
    issues: list[str] = []
    if logging.get("posix_mode") != "0600":
        issues.append(f"{rel}: local log POSIX mode must be 0600")
    if logging.get("tamper_evident") is not True:
        issues.append(f"{rel}: logs must be tamper-evident")
    if logging.get("separate_system") is not True or not str(
            logging.get("sink") or "").strip():
        issues.append(f"{rel}: an independent host log sink is required")
    if not str(logging.get("chain_anchor") or "").strip():
        issues.append(f"{rel}: local log chain anchor is required")
    return issues


__all__ = ["crypto_issues", "file_handling_issues", "logging_issues"]
