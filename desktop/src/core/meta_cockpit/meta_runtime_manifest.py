"""Deterministic release manifest for the local cognitive runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import (
    atomic_io,
    calibration_store,
    context_pack,
    live_selector,
    method_memory,
    runtime_executor,
    session_journal,
    task_profile,
)
from .repo_context import implementation_files

BASE = Path(__file__).parent
FILES = implementation_files()


def _digest(value) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build() -> dict:
    manifest = {
        "schema": "nf-meta-runtime-manifest/1",
        "version": "1.0",
        "machine_digest": runtime_executor.machine_digest(),
        "runtime_digest": session_journal.runtime_digest(),
        "task_profile_digest": task_profile.PROFILE_DIGEST,
        "atom_contracts_digest": hashlib.sha256(
            (BASE / "atom_contracts.json").read_bytes()
        ).hexdigest(),
        "file_digests": {
            name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in FILES
        },
        "limits": {
            "context_units": context_pack.UNIT_LIMIT,
            "references_partition": context_pack.PARTITION_LIMITS["references"],
            "method_history": method_memory.MAX_HISTORY,
            "search_expansions": live_selector.MAX_SEARCH_EXPANSIONS,
            "search_generated": live_selector.MAX_SEARCH_GENERATED,
            "calibration_store_bytes": calibration_store.MAX_STORE_BYTES,
            "journal_bytes": session_journal.MAX_JOURNAL_BYTES,
        },
        "capabilities": {
            "offline": True,
            "deterministic_replay": True,
            "fail_closed": True,
            "task_native_handoff": True,
            "role_aware_retrieval": True,
            "offline_blind_ab": True,
            "secret_guard": True,
        },
        "human_review": runtime_executor.review_status()[0],
        "no_scoring": True,
    }
    manifest["digest"] = _digest(manifest)
    return manifest


def verify(manifest: dict) -> list[str]:
    expected = build()
    issues = []
    if manifest.get("schema") != expected["schema"]:
        issues.append("schema")
    if manifest.get("digest") != expected["digest"]:
        issues.append("digest")
    for key in (
        "machine_digest",
        "runtime_digest",
        "task_profile_digest",
        "atom_contracts_digest",
        "file_digests",
        "limits",
        "capabilities",
        "human_review",
        "no_scoring",
    ):
        if manifest.get(key) != expected[key]:
            issues.append(key)
    return issues


def save(path: str | Path) -> Path:
    target = Path(path)
    manifest = build()
    atomic_io.write_text(target, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return target
