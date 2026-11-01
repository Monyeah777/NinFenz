"""Fail-closed validation for SLSA v1.2 Build L3 release evidence."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

READINESS_REL = "packaging/supply-chain/slsa-l3-readiness.json"
POLICY_REL = "packaging/supply-chain/verification-policy.json"
WORKFLOW_REL = ".github/workflows/npm-publish.yml"
BUILDER_REL = ".github/workflows/slsa-build-l3.yml"
RELEASE_WORKFLOW_REL = ".github/workflows/release.yml"
EVIDENCE_BUILDER_REL = ".github/workflows/release-evidence-l3.yml"
RUN_EVIDENCE_REL = "results/supply-chain/slsa-l3-attestation-run.json"
PENDING_RUN_ENV = "NF_SLSA_PENDING_RUN"
EXPECTED_REQUIREMENTS = {
    "reusable-trusted-builder",
    "unforgeable-provenance",
    "build-isolation",
    "cache-poisoning",
    "provenance-distribution",
    "consumer-verification",
}
STATUSES = {"satisfied", "partial", "blocked"}
LEVEL_L3 = "SLSA_BUILD_LEVEL_3"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def _evidence_issues(root: Path, label: str, values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return [f"{label}: evidence 必须是非空列表"]
    missing = [
        str(rel)
        for rel in values
        if not (root / str(rel)).is_file() and not str(rel).startswith("external:")
    ]
    return [f"{label}: evidence 缺件：{missing}"] if missing else []


def _readiness_issues(root: Path, readiness: dict[str, Any]) -> tuple[list[str], dict[str, int]]:
    issues: list[str] = []
    if readiness.get("schema") != "nf-slsa-l3-readiness/2":
        issues.append("readiness schema 必须是 nf-slsa-l3-readiness/2")
    if readiness.get("standard") != "SLSA v1.2 Build L3":
        issues.append("readiness 必须对齐 SLSA v1.2 Build L3")
    claimed = readiness.get("claimed_level")
    if claimed not in {"SLSA_BUILD_LEVEL_2", LEVEL_L3}:
        issues.append(f"非法 claimed_level：{claimed!r}")
    rows = readiness.get("requirements")
    if not isinstance(rows, list):
        return issues + ["readiness requirements 必须是列表"], {}
    ids = [str(row.get("id")) for row in rows if isinstance(row, dict)]
    if set(ids) != EXPECTED_REQUIREMENTS:
        issues.append(
            "readiness requirements 集合不匹配："
            f"missing={sorted(EXPECTED_REQUIREMENTS - set(ids))} "
            f"extra={sorted(set(ids) - EXPECTED_REQUIREMENTS)}"
        )
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            issues.append("readiness requirement 必须是对象")
            continue
        ident = str(row.get("id") or "?")
        status = str(row.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
        if status not in STATUSES:
            issues.append(f"{ident}: 非法 readiness 状态 {status!r}")
        if not str(row.get("reason") or "").strip():
            issues.append(f"{ident}: 缺 reason")
        issues.extend(_evidence_issues(root, ident, row.get("evidence")))
    return issues, counts


def _policy_issues(policy: dict[str, Any], claimed: Any) -> list[str]:
    issues: list[str] = []
    levels = policy.get("verified_levels")
    if not isinstance(levels, list):
        return ["verification policy verified_levels 必须是列表"]
    if claimed == LEVEL_L3:
        if levels != [LEVEL_L3]:
            issues.append("Build L3 声明时 verified_levels 必须且只能是 SLSA_BUILD_LEVEL_3")
        if LEVEL_L3 in (policy.get("not_claimed_levels") or []):
            issues.append("Build L3 不得同时列入 not_claimed_levels")
    elif LEVEL_L3 in levels:
        issues.append("readiness 未声明 L3 时 verification policy 不得声明 Build L3")
    expected = {
        "build_workflow": BUILDER_REL,
        "provenance_signer_workflow": BUILDER_REL,
        "vsa_signer_workflow": WORKFLOW_REL,
        "release_evidence_workflow": EVIDENCE_BUILDER_REL,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            issues.append(f"verification policy {key} 必须是 {value}")
    if policy.get("build_workflow_ref") != "refs/heads/main":
        issues.append("verification policy build_workflow_ref 必须是 refs/heads/main")
    if (policy.get("verifier") or {}).get("id") != (
        "https://github.com/Monyeah777/NinFenz/.github/workflows/npm-publish.yml"
    ):
        issues.append("verification policy verifier.id 必须指向调用方验证工作流")
    return issues


def _builder_issues(label: str, text: str) -> list[str]:
    issues: list[str] = []
    if "workflow_call:" not in text:
        issues.append(f"{label} 必须暴露 workflow_call")
    if "actions/attest-build-provenance@" not in text:
        issues.append(f"{label} 必须在内部生成 artifact provenance")
    for forbidden in ("cache: pip", "cache: npm", "cache: yarn"):
        if forbidden in text:
            issues.append(f"{label} 不得启用持久缓存：{forbidden}")
    return issues


def _run_evidence_issues(root: Path, pending_run: bool = False) -> list[str]:
    path = root / RUN_EVIDENCE_REL
    if not path.is_file():
        return [f"{RUN_EVIDENCE_REL}: 缺真实 L3 attestation 运行证据"]
    try:
        doc = _json(path)
    except (OSError, ValueError) as exc:
        return [f"{RUN_EVIDENCE_REL}: 不可读：{exc}"]
    issues: list[str] = []
    expected = {
        "schema": "nf-slsa-l3-attestation-run/1",
        "repository": "https://github.com/Monyeah777/NinFenz",
        "build_signer_workflow": BUILDER_REL,
        "vsa_signer_workflow": WORKFLOW_REL,
        "provenance_predicate": "https://slsa.dev/provenance/v1",
        "vsa_predicate": "https://slsa.dev/verification_summary/v1",
    }
    for key, value in expected.items():
        if doc.get(key) != value:
            issues.append(f"{RUN_EVIDENCE_REL}: {key} 必须是 {value}")
    if not isinstance(doc.get("run_id"), int) or doc["run_id"] < 1:
        issues.append(f"{RUN_EVIDENCE_REL}: run_id 必须是正整数")
    if not re.fullmatch(r"[0-9a-f]{40}", str(doc.get("tested_commit") or "")):
        issues.append(f"{RUN_EVIDENCE_REL}: tested_commit 必须是 40 位提交 SHA")
    if doc.get("verified_levels") != [LEVEL_L3]:
        issues.append(f"{RUN_EVIDENCE_REL}: verified_levels 必须且只能是 Build L3")
    for key in ("provenance_verified", "vsa_verified"):
        if doc.get(key) is not True:
            issues.append(f"{RUN_EVIDENCE_REL}: {key} 必须为 true")
    workflows = doc.get("workflow_sha256")
    expected_workflows = {
        BUILDER_REL,
        WORKFLOW_REL,
        EVIDENCE_BUILDER_REL,
        RELEASE_WORKFLOW_REL,
    }
    if not isinstance(workflows, dict) or set(workflows) != expected_workflows:
        issues.append(f"{RUN_EVIDENCE_REL}: workflow_sha256 集合不完整")
    else:
        for rel, expected_hash in workflows.items():
            actual = hashlib.sha256((root / rel).read_bytes()).hexdigest()
            if actual != expected_hash and not pending_run:
                issues.append(f"{RUN_EVIDENCE_REL}: {rel} 已在验收运行后变更")
    try:
        datetime.fromisoformat(str(doc.get("verified_at") or "").replace("Z", "+00:00"))
    except ValueError:
        issues.append(f"{RUN_EVIDENCE_REL}: verified_at 必须是 ISO-8601")
    subjects = doc.get("subjects")
    if not isinstance(subjects, dict) or not subjects:
        issues.append(f"{RUN_EVIDENCE_REL}: subjects 必须非空")
    elif any(not re.fullmatch(r"[0-9a-f]{64}", str(digest)) for digest in subjects.values()):
        issues.append(f"{RUN_EVIDENCE_REL}: subject digest 必须是 SHA-256")
    return issues


def _workflow_issues(root: Path) -> list[str]:
    caller = (root / WORKFLOW_REL).read_text(encoding="utf-8")
    builder = (root / BUILDER_REL).read_text(encoding="utf-8")
    release = (root / RELEASE_WORKFLOW_REL).read_text(encoding="utf-8")
    evidence_builder = (root / EVIDENCE_BUILDER_REL).read_text(encoding="utf-8")
    issues: list[str] = []
    if "uses: ./.github/workflows/slsa-build-l3.yml" not in caller:
        issues.append("调用方必须使用同仓 slsa-build-l3.yml reusable workflow")
    if "uses: ./.github/workflows/release-evidence-l3.yml" not in release:
        issues.append("release.yml 必须使用同仓 release-evidence-l3.yml reusable workflow")
    issues.extend(_builder_issues(BUILDER_REL, builder))
    issues.extend(_builder_issues(EVIDENCE_BUILDER_REL, evidence_builder))
    for label, text in ((WORKFLOW_REL, caller), (RELEASE_WORKFLOW_REL, release)):
        if "actions/attest-build-provenance@" in text:
            issues.append(f"{label} 不得在 reusable builder 之外生成构建 provenance")
    for needle in (
        "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
        "https://slsa.dev/verification_summary/v1",
        "scripts/build_vsa.py",
        "--signer-workflow \"$GITHUB_REPOSITORY/.github/workflows/slsa-build-l3.yml\"",
        "--signer-workflow \"$GITHUB_REPOSITORY/.github/workflows/npm-publish.yml\"",
        "--deny-self-hosted-runners",
    ):
        if needle not in caller:
            issues.append(f"调用方缺 L3 验证接线：{needle}")
    release_signer = (
        "--signer-workflow "
        "\"$GITHUB_REPOSITORY/.github/workflows/release-evidence-l3.yml\""
    )
    if release_signer not in release:
        issues.append("release.yml 缺 release-evidence-l3.yml 验签")
    if "--deny-self-hosted-runners" not in release:
        issues.append("release.yml 缺 hosted-runner 约束")
    if any("slsa-github-generator" in text for text in (
        caller, builder, release, evidence_builder
    )):
        issues.append("不得依赖停维护的 slsa-github-generator")
    return issues


def claimed_level_issues(policy: dict[str, Any], root: Path) -> list[str]:
    """VSA helper: reject claims unless the checked-in readiness is consistent."""
    if LEVEL_L3 not in (policy.get("verified_levels") or []):
        return []
    issues, stats = scan(root)
    if issues:
        return ["Build L3 readiness 未通过：" + issue for issue in issues]
    if stats.get("claimed_level") != LEVEL_L3:
        return ["Build L3 readiness 未声明目标等级"]
    return []


def scan(root: str | Path) -> tuple[list[str], dict[str, Any]]:
    root = Path(root)
    try:
        readiness = _json(root / READINESS_REL)
        policy = _json(root / POLICY_REL)
    except (OSError, ValueError) as exc:
        return [f"SLSA L3 evidence unreadable: {exc}"], {}
    claimed = readiness.get("claimed_level")
    readiness_issues, statuses = _readiness_issues(root, readiness)
    issues = readiness_issues + _policy_issues(policy, claimed) + _workflow_issues(root)
    if claimed == LEVEL_L3 and statuses != {"satisfied": len(EXPECTED_REQUIREMENTS)}:
        issues.append("声明 Build L3 时所有 readiness 要求必须为 satisfied")
    if claimed == LEVEL_L3:
        issues.extend(_run_evidence_issues(
            root, pending_run=bool(os.environ.get(PENDING_RUN_ENV))
        ))
    last_run_id = None
    if (root / RUN_EVIDENCE_REL).is_file():
        try:
            last_run_id = _json(root / RUN_EVIDENCE_REL).get("run_id")
        except (OSError, ValueError):
            last_run_id = None
    return issues, {
        "claimed_level": claimed,
        "statuses": dict(sorted(statuses.items())),
        "last_run_id": last_run_id,
    }


__all__ = [
    "BUILDER_REL",
    "EVIDENCE_BUILDER_REL",
    "EXPECTED_REQUIREMENTS",
    "LEVEL_L3",
    "POLICY_REL",
    "PENDING_RUN_ENV",
    "READINESS_REL",
    "RELEASE_WORKFLOW_REL",
    "RUN_EVIDENCE_REL",
    "WORKFLOW_REL",
    "claimed_level_issues",
    "scan",
]
