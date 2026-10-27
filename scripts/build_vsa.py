#!/usr/bin/env python3
"""Build a SLSA Verification Summary predicate after local release verification."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write  # noqa: E402

SUM_RE = re.compile(r"^([0-9a-f]{64})  ([^\r\n]+)$")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象")
    return value


def _vex_tools():
    path = ROOT / "scripts" / "generate_vex.py"
    spec = importlib.util.spec_from_file_location("nf_vsa_generate_vex", path)
    if spec is None or spec.loader is None:
        raise ValueError("无法加载 scripts/generate_vex.py（修复指引：恢复 VEX 生成器）")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_release(
    release: Path,
    policy: dict[str, Any],
    commit: str,
    source_root: Path = ROOT,
) -> list[str]:
    issues: list[str] = []
    metadata_path = release / "release-metadata.json"
    sums_path = release / "SHA256SUMS"
    if not metadata_path.is_file() or not sums_path.is_file():
        return ["release bundle 缺 release-metadata.json 或 SHA256SUMS"]
    metadata = _json(metadata_path)
    if metadata.get("release_ready") is not True:
        issues.append("release_ready 不是 true")
    if metadata.get("source_commit") != commit:
        issues.append("source_commit 与 VSA commit 不一致")
    reproducible = metadata.get("reproducible_build") or {}
    if reproducible.get("verified") is not True:
        issues.append("可复现构建未验证")
    required_builds = int((policy.get("required_checks") or {}).get("reproducible_builds", 2))
    if int(reproducible.get("independent_builds", 0)) < required_builds:
        issues.append("独立构建次数不足")
    seen: dict[str, str] = {}
    for line in sums_path.read_text(encoding="ascii").splitlines():
        match = SUM_RE.match(line)
        if not match:
            issues.append(f"非法 SHA256SUMS 行：{line!r}")
            continue
        digest, name = match.groups()
        seen[name] = digest
        path = release / name
        if not path.is_file():
            issues.append(f"SHA256SUMS 指向缺件：{name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            issues.append(f"摘要不符：{name}")
    mapped: list[str] = []
    for key in ("artifact_names", "github_packages_names"):
        values = metadata.get(key)
        if not isinstance(values, dict):
            issues.append(f"release-metadata 缺 {key}")
            continue
        mapped.extend(str(value) for value in values.values())
    missing_mapped = sorted(set(mapped) - set(seen))
    if missing_mapped:
        issues.append(f"release-metadata 工件未进 SHA256SUMS：{missing_mapped}")
    for pattern in policy.get("required_artifacts") or []:
        if not any(release.glob(pattern)):
            issues.append(f"发布目录缺必需工件：{pattern}")
    vex_paths = sorted(release.glob("*.openvex.json"))
    if len(vex_paths) != 1:
        issues.append("发布目录缺 OpenVEX")
    else:
        actual_vex = _json(vex_paths[0])
        product = f"pkg:npm/{metadata.get('package')}@{metadata.get('version')}"
        generated_vex = _vex_tools().vex_doc(source_root, product)
        if actual_vex != generated_vex:
            issues.append("发布束 OpenVEX 与处置台账不一致")
    return issues


def predicate(
    policy: dict[str, Any],
    policy_digest: str,
    commit: str,
    run_id: str,
    verified_at: str,
) -> dict[str, Any]:
    repo = str(policy["repository"])
    verifier_id = str((policy.get("verifier") or {}).get("id") or "")
    levels = policy.get("verified_levels") or []
    if "SLSA_BUILD_LEVEL_3" in levels:
        raise ValueError(
            "readiness 未满足，禁止签发 Build L3 VSA"
            "（修复指引：先满足 trusted builder 与 build isolation，再改 verification policy）"
        )
    if not verifier_id or not levels:
        raise ValueError("verification policy 缺 verifier 或 verified_levels")
    policy_uri = f"{repo}/blob/{commit}/packaging/supply-chain/verification-policy.json"
    return {
        "timeVerified": verified_at,
        "verifier": {"id": verifier_id},
        "verificationResult": "PASSED",
        "verifiedLevels": levels,
        "resourceUri": f"{repo}/actions/runs/{run_id}",
        "policy": {"uri": policy_uri, "digest": {"sha256": policy_digest}},
        "inputAttestations": [
            {"uri": f"{repo}/actions/runs/{run_id}"},
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 SLSA VSA predicate")
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--policy", default="packaging/supply-chain/verification-policy.json")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--time", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    policy_path = Path(args.policy)
    policy_bytes = policy_path.read_bytes()
    policy = _json(policy_path)
    policy_digest = hashlib.sha256(policy_bytes).hexdigest()
    if policy.get("repository") != args.repository:
        print("✗ policy.repository 与 --repository 不一致", file=sys.stderr)
        return 1
    release = Path(args.release_dir)
    issues = verify_release(release, policy, args.commit, ROOT)
    if issues:
        for issue in issues:
            print(f"✗ {issue}", file=sys.stderr)
        return 1
    verified_at = args.time or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        doc = predicate(policy, policy_digest, args.commit, args.run_id, verified_at)
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    out = Path(args.out)
    atomic_write.write_text(
        out,
        json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(f"✓ VSA predicate 已写入：{out}（{', '.join(doc['verifiedLevels'])}）")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
