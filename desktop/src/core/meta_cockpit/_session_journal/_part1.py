"""core.session_journal 私有实现分片 1/2（对外只经 core.session_journal 门面导入）：BASE 等"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.meta_cockpit import atomic_io, calibration_ledger, file_lock, json_asset, method_memory
from core.meta_cockpit import live_selector as ls
from core.meta_cockpit import schema_compat as jsonschema
from core.meta_cockpit.repo_context import implementation_files, repository_root

BASE = Path(__file__).parent.parent


NF_ROOT = repository_root()


SCHEMA_NAME = "nf-cockpit-journal/1"


MAX_JOURNAL_BYTES = 8 * 1024 * 1024


SCHEMA = json_asset.load(BASE / "cockpit_journal.schema.json")


VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


FORBIDDEN_KEYS = {"score", "grade", "rating", "receipt"}


RUNTIME_FILES = implementation_files()


def _canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def contracts_digest() -> str:
    return hashlib.sha256((BASE / "atom_contracts.json").read_bytes()).hexdigest()


def runtime_digest() -> str:
    payload = {
        name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in RUNTIME_FILES
    }
    return digest(payload)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _forbidden_paths(value, path: str = "$") -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                found.append(path + "." + key)
            found += _forbidden_paths(child, path + "." + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found += _forbidden_paths(child, f"{path}[{index}]")
    return found


def _event_digest(event: dict) -> str:
    return digest({k: v for k, v in event.items() if k != "event_digest"})


def _document_digest(doc: dict) -> str:
    return digest({k: v for k, v in doc.items() if k != "digest"})


def _header_issues(doc: dict) -> list[str]:
    issues = [e.message for e in VALIDATOR.iter_errors(doc)]
    if issues:
        return issues
    if doc["atom_contracts_digest"] != contracts_digest():
        issues.append("contracts")
    if doc["runtime_digest"] != runtime_digest():
        issues.append("runtime")
    if doc["digest"] != _document_digest(doc):
        issues.append("document-digest")
    if _forbidden_paths(doc):
        issues.append("forbidden-drive-key")
    return issues


def _event_chain_issues(index: int, event: dict, chain_digest: str, state_digest: str) -> list[str]:
    issues = []
    if event["seq"] != index:
        issues.append(f"sequence:{index}")
    if event["prev_digest"] != chain_digest:
        issues.append(f"chain:{index}")
    if event["state_before_digest"] != state_digest:
        issues.append(f"state-before:{index}")
    return issues


def _event_state_issues(index: int, event: dict) -> tuple[list[str], str]:
    issues = []
    actual_state_digest = digest(event["state"])
    if event["state_after_digest"] != actual_state_digest:
        issues.append(f"state-after:{index}")
    if event["event_digest"] != _event_digest(event):
        issues.append(f"event-digest:{index}")
    if set(event["predicted"]) != set(event["resolved"]):
        issues.append(f"calibration:{index}")
    trace_ids = [item["atom_id"] for item in event["atom_trace"]]
    if trace_ids != event["cluster"]:
        issues.append(f"atom-trace:{index}")
    return issues, actual_state_digest


def _candidate_issues(index: int, decision: dict, event: dict) -> list[str]:
    issues = []
    choice = decision["choice"]
    candidates = decision["candidates"]
    if decision["candidate_count"] != len(candidates):
        issues.append(f"candidate-count:{index}")
    if digest(candidates) != decision["candidate_set_digest"]:
        issues.append(f"candidate-digest:{index}")
    if not 0 <= choice < len(candidates):
        issues.append(f"candidate-choice:{index}")
        return issues
    chosen = candidates[choice]
    if chosen["cluster"] != event["cluster"]:
        issues.append(f"candidate-cluster:{index}")
    if digest(chosen) != decision["chosen_candidate_digest"]:
        issues.append(f"chosen-digest:{index}")
    return issues


def _patch_digest_issues(index: int, decision: dict) -> list[str]:
    issues = []
    if digest(decision["source_snapshot"]) != decision["source_snapshot_digest"]:
        issues.append(f"source-snapshot-digest:{index}")
    patch = decision.get("thought_patch")
    if patch is not None and (
        "thought_patch_digest" not in decision
        or digest(patch) != decision["thought_patch_digest"]
    ):
        issues.append(f"thought-patch-digest:{index}")
    return issues


def _validate(doc: dict) -> list[str]:
    issues = _header_issues(doc)
    if issues:
        return issues
    state_digest = digest(doc["initial_state"])
    calibration_digest = doc["initial_calibration_digest"]
    chain_digest = digest(
        {
            "type": "session-start",
            "session_id": doc["session_id"],
            "state_digest": state_digest,
        }
    )
    for index, event in enumerate(doc["events"], 1):
        issues.extend(_event_chain_issues(index, event, chain_digest, state_digest))
        state_issues, actual_state_digest = _event_state_issues(index, event)
        issues.extend(state_issues)
        decision = event["decision"]
        issues.extend(_candidate_issues(index, decision, event))
        issues.extend(_patch_digest_issues(index, decision))
        if event["calibration_before_digest"] != calibration_digest:
            issues.append(f"calibration-chain:{index}")
        calibration_digest = event["calibration_after_digest"]
        state_digest = actual_state_digest
        chain_digest = event["event_digest"]
    return issues


def current_state(doc: dict) -> dict:
    return copy.deepcopy(doc["events"][-1]["state"] if doc["events"] else doc["initial_state"])


def _file_revision(path: Path) -> str | None:
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_JOURNAL_BYTES:
        return "oversized"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, doc: dict, expected_revision: str | None = None) -> None:
    with file_lock.locked(path):
        if expected_revision is not None and _file_revision(path) != expected_revision:
            raise RuntimeError("concurrent-write")
        doc["digest"] = _document_digest(doc)
        issues = [error.message for error in VALIDATOR.iter_errors(doc)]
        if issues:
            raise ValueError("schema:" + ",".join(issues))
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if len(text.encode("utf-8")) > MAX_JOURNAL_BYTES:
            raise ValueError("journal too large")
        atomic_io.write_text(path, text)


@dataclass(frozen=True)
class TurnOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    before_state: dict
    after_state: dict
    cluster: list[str]
    kind: str
    predicted: list[str]
    resolved: list[str]
    changed_keys: list[str]
    atom_trace: list[dict]
    decision: dict
    calibration_before_digest: str | None = None
    calibration_after_digest: str | None = None
    observations: list[str] | None = None


def _source_drift(doc: dict) -> list[str]:
    issues = set()
    verified = {}
    for event in doc["events"]:
        for item in event["decision"]["source_snapshot"]:
            path_text = item["path"]
            if path_text.startswith("mcp://"):
                continue
            path = (NF_ROOT / path_text).resolve()
            try:
                path.relative_to(NF_ROOT.resolve())
            except ValueError:
                issues.add("escape:" + path_text)
                continue
            if path_text not in verified:
                verified[path_text] = _file_revision(path)
            if verified[path_text] != item["file_digest"]:
                issues.add("changed:" + path_text)
    return sorted(issues)


def reconcile_calibration(doc: dict, ledger: dict) -> tuple[dict, str]:
    current = copy.deepcopy(ledger)
    if not doc["events"]:
        return current, "ok"
    current_digest = digest(current)
    if current_digest == doc["events"][-1]["calibration_after_digest"]:
        return current, "ok"
    start = None
    for index, event in enumerate(doc["events"]):
        if event["calibration_before_digest"] == current_digest:
            start = index
            break
    if start is None:
        return current, "calibration-drift"
    for event in doc["events"][start:]:
        calibration_ledger.observe(current, event["cluster"], ls.available_keys(event["state"]))
        if digest(current) != event["calibration_after_digest"]:
            return ledger, "calibration-replay-mismatch"
    return current, "ok"


def _replay_context_issues(event: dict, state: dict) -> list[str]:
    from .. import context_pack
    from ..constrained_choice import build_prompt_payload

    if event["decision"]["external_context"]:
        return []
    try:
        payload = build_prompt_payload(state, event["decision"]["candidates"])
        if context_pack.digest(payload) != event["decision"]["context_digest"]:
            return [f"context:{event['seq']}"]
    except Exception:
        return [f"context-build:{event['seq']}"]
    return []


def _replayed_state(event: dict, state: dict, result: dict) -> dict:
    replayed = copy.deepcopy(result["state"])
    replayed["turn"] = event["state"].get("turn", replayed.get("turn", 0))
    replayed["context_units_spent"] = int(state.get("context_units_spent", 0)) + int(
        event["decision"]["context_units"]
    )
    method_memory.record_turn(
        replayed,
        int(event["seq"]),
        event["cluster"],
        event["resolved"],
        event["changed_keys"],
        event["kind"],
    )
    return replayed


def _replay_event_issues(event: dict, result: dict, replayed: dict) -> list[str]:
    issues = []
    if digest(replayed) != event["state_after_digest"]:
        issues.append(f"state:{event['seq']}")
    if set(result["resolved"]) != set(event["resolved"]):
        issues.append(f"resolved:{event['seq']}")
    if set(result["changed_keys"]) != set(event["changed_keys"]):
        issues.append(f"changed:{event['seq']}")
    if result["atom_trace"] != event["atom_trace"]:
        issues.append(f"trace:{event['seq']}")
    return issues


def replay(doc: dict) -> dict:
    """从 initial_state 确定性重放每个已提交原子簇。"""
    from ..cognitive_cockpit import execute_cluster

    issues = []
    state = copy.deepcopy(doc["initial_state"])
    for event in doc["events"]:
        for question in event["observations"]:
            state.setdefault("open_questions", []).append(question)
        issues.extend(_replay_context_issues(event, state))
        result = execute_cluster(
            state, event["cluster"], thought_patch=event["decision"].get("thought_patch")
        )
        if result["status"] != "pass":
            issues.append(f"execute:{event['seq']}")
            break
        replayed = _replayed_state(event, state, result)
        issues.extend(_replay_event_issues(event, result, replayed))
        state = copy.deepcopy(event["state"])
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "turns": len(doc["events"]),
    }
