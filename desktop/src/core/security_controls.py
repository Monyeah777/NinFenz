"""Machine checks for the scoped application-security control inventory.

The inventory records requirements that are broader than a single test: input
rules, data classes, cryptographic algorithms, communication paths, resource
limits, production defaults, and release safeguards. This module keeps those
claims tied to code constants and rejects documentation-only promotions.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

CONTROLS_REL = Path("packaging/security/application-security-controls.json")
DOC_REL = Path("docs/security-controls.md")
SCHEMA = "nf-application-security-controls/1"

_DATA_FIELDS = {
    "id", "examples", "confidentiality", "integrity", "retention", "logging", "access",
}
_COMM_FIELDS = {
    "id", "source", "target", "transport", "external", "authentication",
    "least_privilege", "allowlist",
}
_AUTH_FIELDS = {"id", "consumer", "resource", "decision"}
_CRYPTO_FIELDS = {
    "id", "algorithm", "purpose", "key_source", "storage", "rotation",
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(
            f"{path}: top level must be an object"
            "（修复指引：恢复 JSON 顶层对象，勿改成数组或标量）"
        )
    return value


def _rows(doc: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = doc.get(key)
    if not isinstance(value, list) or not value:
        return []
    return [row for row in value if isinstance(row, dict)]


def _load_script(root: Path, rel: str, name: str):
    path = root / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(
            f"{rel}: cannot load for constant verification"
            "（修复指引：恢复脚本及 Python 语法后重跑安全控制校验）"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resource_constants(root: Path) -> dict[str, int]:
    from core import daemon as dm
    from core import mcp_runtime as mcp
    from core import repo_index

    plugin = _load_script(root, "scripts/plugin_host.py", "nf_security_controls_plugin")
    return {
        "daemon.request": int(dm.MAX_REQUEST_BYTES),
        "daemon.response": int(dm.MAX_RESPONSE_BYTES),
        "mcp.message": int(mcp.MAX_MESSAGE_BYTES),
        "mcp.snapshot": int(mcp.MAX_SNAPSHOT_BYTES),
        "mcp.resource": int(repo_index.MAX_RESOURCE_BYTES),
        "plugin.input": int(plugin.MAX_PLUGIN_INPUT_BYTES),
        "plugin.output": int(plugin.MAX_PLUGIN_OUTPUT_BYTES),
    }


def _timeout_constants(root: Path) -> dict[str, int]:
    from core import daemon as dm

    plugin = _load_script(root, "scripts/plugin_host.py", "nf_security_controls_plugin_timeout")
    return {
        "daemon.idle": int(dm.DEFAULT_IDLE_TIMEOUT),
        "daemon.lifetime": int(dm.DEFAULT_MAX_LIFETIME),
        "plugin.wall": int(plugin.DEFAULT_WALL_TIMEOUT_MS / 1000),
    }


def scan(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    root = Path(root)
    issues: list[str] = []
    try:
        doc = _json(root / CONTROLS_REL)
    except (OSError, ValueError) as exc:
        return [f"{CONTROLS_REL}: unreadable or invalid: {exc}"], {}
    if doc.get("schema") != SCHEMA:
        issues.append(f"{CONTROLS_REL}: schema must be {SCHEMA}")
    if not str(doc.get("reviewed_at") or "").strip():
        issues.append(f"{CONTROLS_REL}: reviewed_at is required")

    input_validation = doc.get("input_validation")
    if not isinstance(input_validation, dict):
        issues.append(f"{CONTROLS_REL}: input_validation must be an object")
        input_validation = {}
    for key in ("rules", "coupled_rules", "business_limits"):
        if not _rows(input_validation, key):
            issues.append(f"{CONTROLS_REL}: input_validation.{key} must be non-empty")
    for row in _rows(input_validation, "rules"):
        if not all(str(row.get(key) or "").strip()
                   for key in ("id", "surface", "validation", "limit", "evidence")):
            issues.append(f"{CONTROLS_REL}/input_validation: incomplete rule {row.get('id')!r}")
        elif not (root / str(row["evidence"])).exists():
            issues.append(f"{CONTROLS_REL}/input_validation/{row.get('id')}: evidence missing")

    files = doc.get("file_handling")
    if not isinstance(files, dict):
        issues.append(f"{CONTROLS_REL}: file_handling must be an object")
        files = {}
    if files.get("upload_surface") is not False:
        issues.append(f"{CONTROLS_REL}: upload_surface must remain false")
    if not files.get("processing_types"):
        issues.append(f"{CONTROLS_REL}: file_handling.processing_types is required")
    if not _rows(files, "maximum_sizes"):
        issues.append(f"{CONTROLS_REL}: file_handling.maximum_sizes is required")
    if not str(files.get("malicious_file_behavior") or "").strip():
        issues.append(f"{CONTROLS_REL}: file_handling.malicious_file_behavior is required")

    auth = doc.get("authorization")
    if not isinstance(auth, dict) or auth.get("default") != "deny":
        issues.append(f"{CONTROLS_REL}: authorization default must be deny")
        auth = {}
    if not _rows(auth, "rules"):
        issues.append(f"{CONTROLS_REL}: authorization.rules must be non-empty")
    for row in _rows(auth, "rules"):
        if not _AUTH_FIELDS.issubset(row) or not all(
                str(row.get(key) or "").strip() for key in _AUTH_FIELDS):
            issues.append(f"{CONTROLS_REL}/authorization: incomplete rule {row.get('id')!r}")

    crypto = doc.get("cryptography")
    if not isinstance(crypto, dict):
        issues.append(f"{CONTROLS_REL}: cryptography must be an object")
        crypto = {}
    crypto_rows = _rows(crypto, "inventory")
    if not crypto_rows:
        issues.append(f"{CONTROLS_REL}: cryptography.inventory must be non-empty")
    crypto_ids = {str(row.get("id")) for row in crypto_rows}
    if not {"daemon-session-token", "content-integrity", "token-comparison"}.issubset(crypto_ids):
        issues.append(f"{CONTROLS_REL}: cryptography inventory misses an approved primitive")
    for row in crypto_rows:
        if not _CRYPTO_FIELDS.issubset(row) or not all(
                str(row.get(key) or "").strip() for key in _CRYPTO_FIELDS):
            issues.append(f"{CONTROLS_REL}/cryptography: incomplete row {row.get('id')!r}")
    approved = set(crypto.get("approved_algorithms") or [])
    if approved != {"secrets.token_hex(32)", "SHA-256", "hmac.compare_digest"}:
        issues.append(f"{CONTROLS_REL}: approved algorithm set drifted")
    agility = crypto.get("agility") or {}
    if agility.get("status") == "partial" and not str(agility.get("gap") or "").strip():
        issues.append(f"{CONTROLS_REL}: partial crypto agility must record gap")

    comms = _rows(doc, "communications")
    if not comms:
        issues.append(f"{CONTROLS_REL}: communications must be non-empty")
    for row in comms:
        if not _COMM_FIELDS.issubset(row) or not all(
                str(row.get(key) or "").strip() for key in _COMM_FIELDS
                if key != "external"):
            issues.append(f"{CONTROLS_REL}/communications: incomplete row {row.get('id')!r}")
        if row.get("external") is not False:
            issues.append(
                f"{CONTROLS_REL}/communications/{row.get('id')}: "
                "runtime external path is not reviewed"
            )

    data = doc.get("data_protection")
    classes = _rows(data if isinstance(data, dict) else {}, "classes")
    if not classes:
        issues.append(f"{CONTROLS_REL}: data_protection.classes must be non-empty")
    for row in classes:
        if not _DATA_FIELDS.issubset(row) or not all(
                str(row.get(key) or "").strip() for key in _DATA_FIELDS):
            issues.append(f"{CONTROLS_REL}/data_protection: incomplete class {row.get('id')!r}")

    try:
        actual_limits = _resource_constants(root)
        actual_timeouts = _timeout_constants(root)
    except (OSError, ValueError, ImportError) as exc:
        issues.append(f"{CONTROLS_REL}: cannot verify runtime constants: {exc}")
        actual_limits, actual_timeouts = {}, {}
    limits = doc.get("resource_limits") if isinstance(doc.get("resource_limits"), dict) else {}
    declared_limits = {str(row.get("id")): int(row.get("bytes", -1))
                       for row in _rows(limits, "limits")}
    for key in ("daemon.request", "daemon.response", "mcp.message", "mcp.snapshot",
                "mcp.resource", "plugin.input", "plugin.output"):
        if declared_limits.get(key) != actual_limits.get(key):
            issues.append(f"{CONTROLS_REL}/resource_limits/{key}: declared limit differs from code")
    declared_timeouts = {str(row.get("id")): int(row.get("seconds", -1))
                         for row in _rows(limits, "timeouts")}
    for key in ("daemon.idle", "daemon.lifetime", "plugin.wall"):
        if declared_timeouts.get(key) != actual_timeouts.get(key):
            issues.append(
                f"{CONTROLS_REL}/resource_limits/{key}: declared timeout differs from code"
            )

    logging = doc.get("logging") if isinstance(doc.get("logging"), dict) else {}
    if logging.get("posix_mode") != "0600":
        issues.append(f"{CONTROLS_REL}: local log POSIX mode must be 0600")
    if logging.get("tamper_evident") is False and not str(logging.get("gap") or "").strip():
        issues.append(f"{CONTROLS_REL}: non-immutable logs must record the residual gap")

    production = doc.get("production") if isinstance(doc.get("production"), dict) else {}
    if production.get("debug_default") != "disabled":
        issues.append(f"{CONTROLS_REL}: production debug default must be disabled")
    if production.get("development_artifacts_excluded_from_payload") is not True:
        issues.append(f"{CONTROLS_REL}: development artifacts must be excluded from payload")

    release = doc.get("release") if isinstance(doc.get("release"), dict) else {}
    if release.get("slsa_claimed_level") != "SLSA_BUILD_LEVEL_2":
        issues.append(f"{CONTROLS_REL}: SLSA claim must remain at evidenced Build L2")
    if int(release.get("reproducible_build_count") or 0) < 2:
        issues.append(f"{CONTROLS_REL}: at least two reproducible builds are required")

    doc_path = root / DOC_REL
    try:
        human = doc_path.read_text(encoding="utf-8")
    except OSError:
        issues.append(f"{DOC_REL}: human-readable control document is missing")
    else:
        for needle in (
            "输入校验", "数据分类", "密码算法清单", "通信清单",
            "资源上限", "日志保护", "发布与依赖",
        ):
            if needle not in human:
                issues.append(f"{DOC_REL}: missing section anchor {needle!r}")

    return issues, {
        "data_classes": len(classes),
        "communication_paths": len(comms),
        "crypto_inventory": len(crypto_rows),
        "resource_limits": len(declared_limits) + len(declared_timeouts),
        "runtime_external_paths": sum(
            1 for row in comms if row.get("external") is True
        ),
    }


__all__ = ["CONTROLS_REL", "DOC_REL", "SCHEMA", "scan"]
