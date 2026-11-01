#!/usr/bin/env python3
"""Validate same-environment, bit-for-bit reproducibility evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_REL = "packaging/supply-chain/reproducibility.json"
SLSA_REL = "results/supply-chain/slsa-l3-attestation-run.json"
BUILDER_REL = ".github/workflows/slsa-build-l3.yml"
RELEASE_REL = "packaging/npm/tools/build_release.py"
SCHEMA = "nf-reproducibility-evidence/1"
STANDARD = "https://reproducible-builds.org/docs/definition/"
SCOPE = "same-controlled-build-environment"
SLSA_SCHEMA = "nf-slsa-l3-attestation-run/1"
SLSA_LEVEL = "SLSA_BUILD_LEVEL_3"
KINDS = {"npm", "github-packages", "python-wheel"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: 不可读 JSON：{exc}（修复指引：恢复有效 UTF-8 JSON）") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def _workflow_issues(root: Path) -> list[str]:
    builder = (root / BUILDER_REL).read_text(encoding="utf-8")
    release = (root / RELEASE_REL).read_text(encoding="utf-8")
    issues: list[str] = []
    for text, label, needles in (
        (builder, BUILDER_REL, ("cmp \"$WHEEL_A\" \"$WHEEL_B\"", "--verify .artifacts/release")),
        (release, RELEASE_REL, ("tar_one = build_tarball(files)", "tar_two = build_tarball(files)",
                                "if tar_one != tar_two")),
    ):
        for needle in needles:
            if needle not in text:
                issues.append(f"{label} 缺可复现判据：{needle}")
    return issues


def _slsa_subjects(slsa: dict[str, Any], issues: list[str]) -> dict[str, Any]:
    value = slsa.get("subjects")
    if not isinstance(value, dict):
        issues.append("SLSA subjects 必须是对象")
        return {}
    return value


def _artifact_kinds(slsa: dict[str, Any], artifacts: list[Any], issues: list[str]) -> set[str]:
    seen: set[str] = set()
    seen_filenames: set[str] = set()
    subjects = _slsa_subjects(slsa, issues)
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            issues.append(f"artifacts[{index}] 必须是对象")
            continue
        kind = str(artifact.get("kind") or "")
        filename = str(artifact.get("filename") or "")
        digest = str(artifact.get("sha256") or "")
        builds = artifact.get("builds")
        if kind in seen:
            issues.append(f"artifact kind 重复：{kind}")
        seen.add(kind)
        if kind not in KINDS:
            issues.append(f"artifacts[{index}] 未知 kind：{kind!r}")
        if not filename or filename in seen_filenames:
            issues.append(f"artifacts[{index}] filename 为空或重复：{filename!r}")
        seen_filenames.add(filename)
        if isinstance(builds, bool) or not isinstance(builds, int) or builds < 2:
            issues.append(f"artifacts[{index}] 至少需要 2 次构建")
        if artifact.get("comparison") != "byte-identical":
            issues.append(f"artifacts[{index}] comparison 必须是 byte-identical")
        if not SHA256.fullmatch(digest):
            issues.append(f"artifacts[{index}] sha256 非法")
        if subjects.get(filename) != digest:
            issues.append(f"artifacts[{index}] 摘要未绑定到 SLSA subject {filename}")
    return seen


def _slsa_verification_issues(slsa: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if slsa.get("schema") != SLSA_SCHEMA:
        issues.append(f"SLSA evidence schema 必须是 {SLSA_SCHEMA}")
    levels = slsa.get("verified_levels")
    if not isinstance(levels, list) or SLSA_LEVEL not in levels:
        issues.append(f"SLSA evidence 必须包含已验证的 {SLSA_LEVEL}")
    for field in (
        "provenance_verified",
        "vsa_verified",
        "release_evidence_verified",
    ):
        if slsa.get(field) is not True:
            issues.append(f"SLSA evidence {field} 必须为 true")
    return issues


def _binding_issues(doc: dict[str, Any], slsa: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if doc.get("run_id") != slsa.get("run_id"):
        issues.append("run_id 必须与 SLSA L3 验证运行一致")
    if doc.get("source_commit") != slsa.get("tested_commit"):
        issues.append("source_commit 必须与 SLSA L3 tested_commit 一致")
    return issues


def validate_doc(
    root: Path, doc: dict[str, Any], slsa: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append(f"reproducibility schema 必须是 {SCHEMA}")
    if doc.get("standard") != STANDARD:
        issues.append(f"standard 必须是 {STANDARD}")
    if doc.get("scope") != SCOPE:
        issues.append(
            "scope 必须严格声明为同一受控构建环境；"
            "当前证据不足以宣称跨机器或跨发行版可复现"
        )
    issues.extend(_binding_issues(doc, slsa))
    issues.extend(_slsa_verification_issues(slsa))
    env = doc.get("environment")
    if not isinstance(env, dict):
        issues.append("environment 必须是对象")
        env = {}
    if env.get("persistent_caches") is not False:
        issues.append("environment.persistent_caches 必须为 false")
    for key in ("runner", "source_date_epoch", "rust", "maturin", "python", "node",
                "wheel_container"):
        if not str(env.get(key) or "").strip():
            issues.append(f"environment 缺 {key}")
    if "@sha256:" not in str(env.get("wheel_container") or ""):
        issues.append("wheel_container 必须固定 digest")
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return issues + ["artifacts 必须是非空数组"], {"artifacts": 0}
    seen = _artifact_kinds(slsa, artifacts, issues)
    missing = sorted(KINDS - seen)
    if missing:
        issues.append(f"缺少产物类型：{missing}")
    issues.extend(_workflow_issues(root))
    return issues, {"artifacts": len(artifacts), "kinds": sorted(seen)}


def scan(root: str | Path = ROOT) -> tuple[list[str], dict[str, Any]]:
    root = Path(root).resolve()
    try:
        doc = _json(root / EVIDENCE_REL)
        slsa = _json(root / SLSA_REL)
    except ValueError as exc:
        return [str(exc)], {}
    issues, stats = validate_doc(root, doc, slsa)
    stats["evidence_sha256"] = hashlib.sha256((root / EVIDENCE_REL).read_bytes()).hexdigest()
    return issues, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验受控环境下的逐字节可复现证据")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    issues, stats = scan(args.root)
    if args.json:
        print(json.dumps({"issues": issues, "stats": stats}, ensure_ascii=False,
                         indent=2, sort_keys=True))
    else:
        print(f"== Reproducible Builds ==\n  工件 {stats.get('artifacts', 0)} 类")
        for issue in issues:
            print(f"  ✗ {issue}", file=sys.stderr)
        if not issues:
            print("  ✓ npm、GitHub Packages 与 Python wheel 均为两次逐字节一致构建")
    return 1 if issues else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
