"""驾驶会话事件账本：提交、恢复、哈希链与重复提交防护。"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import atomic_io, calibration_ledger, epistemic_agenda, file_lock, json_asset, method_memory
from . import live_selector as ls
from . import schema_compat as jsonschema
from .repo_context import implementation_files, repository_root

BASE = Path(__file__).parent
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


def _validate(doc: dict) -> list[str]:
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
        if event["seq"] != index:
            issues.append(f"sequence:{index}")
        if event["prev_digest"] != chain_digest:
            issues.append(f"chain:{index}")
        if event["state_before_digest"] != state_digest:
            issues.append(f"state-before:{index}")
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
        decision = event["decision"]
        choice = decision["choice"]
        candidates = decision["candidates"]
        if decision["candidate_count"] != len(candidates):
            issues.append(f"candidate-count:{index}")
        if digest(candidates) != decision["candidate_set_digest"]:
            issues.append(f"candidate-digest:{index}")
        if not 0 <= choice < len(candidates):
            issues.append(f"candidate-choice:{index}")
        else:
            chosen = candidates[choice]
            if chosen["cluster"] != event["cluster"]:
                issues.append(f"candidate-cluster:{index}")
            if digest(chosen) != decision["chosen_candidate_digest"]:
                issues.append(f"chosen-digest:{index}")
        if digest(decision["source_snapshot"]) != decision["source_snapshot_digest"]:
            issues.append(f"source-snapshot-digest:{index}")
        patch = decision.get("thought_patch")
        if patch is not None and (
            "thought_patch_digest" not in decision
            or digest(patch) != decision["thought_patch_digest"]
        ):
            issues.append(f"thought-patch-digest:{index}")
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


def load(path: Path) -> tuple[dict | None, str]:
    p = Path(path)
    if not p.is_file():
        return None, "missing"
    if p.stat().st_size > MAX_JOURNAL_BYTES:
        return None, "tampered:size"
    try:
        doc = json_asset.load(p)
    except (OSError, UnicodeError, ValueError, RecursionError):
        return None, "tampered:json"
    issues = _validate(doc)
    if not issues:
        drift = _source_drift(doc)
        if drift:
            return None, "stale-source:" + ",".join(drift)
    if not issues:
        replay_result = replay(doc)
        if replay_result["status"] != "pass":
            issues.extend("replay:" + issue for issue in replay_result["issues"])
    if issues:
        return None, "tampered:" + ",".join(issues)
    return doc, "ok"


def ensure(
    path: Path, goal: str, initial_state: dict, initial_ledger: dict | None = None
) -> tuple[dict | None, str]:
    doc, status = load(path)
    if doc is not None:
        if doc["goal"] != goal:
            return None, "goal-conflict"
        return doc, "resumed" if doc["events"] else "new"
    if status != "missing":
        return None, status
    state = copy.deepcopy(initial_state)
    ledger = initial_ledger or calibration_ledger.initial_ledger()
    doc = {
        "schema": SCHEMA_NAME,
        "session_id": uuid.uuid4().hex,
        "goal": goal,
        "atom_contracts_digest": contracts_digest(),
        "runtime_digest": runtime_digest(),
        "initial_calibration_digest": digest(ledger),
        "created_at": _now(),
        "initial_state": state,
        "events": [],
    }
    doc["digest"] = _document_digest(doc)
    _write(Path(path), doc)
    return doc, "new"


def append_turn(
    path: Path,
    goal: str,
    before_state: dict,
    after_state: dict,
    cluster: list[str],
    kind: str,
    predicted: list[str],
    resolved: list[str],
    changed_keys: list[str],
    atom_trace: list[dict],
    decision: dict,
    calibration_before_digest: str | None = None,
    calibration_after_digest: str | None = None,
    observations: list[str] | None = None,
) -> tuple[dict | None, str]:
    revision = _file_revision(Path(path))
    doc, status = load(path)
    if doc is None:
        return None, status
    if doc["goal"] != goal:
        return None, "goal-conflict"
    persisted = current_state(doc)
    if digest(before_state) != digest(persisted):
        return None, "stale-state"
    if set(predicted) != set(resolved):
        return None, "calibration-mismatch"
    if _forbidden_paths({"state": after_state, "cluster": cluster}):
        return None, "forbidden-drive-key"
    if [item.get("atom_id") for item in atom_trace] != list(cluster):
        return None, "atom-trace-mismatch"
    if any(item.get("status") != "pass" for item in atom_trace):
        return None, "atom-trace-failed"
    choice = decision.get("choice")
    candidates = decision.get("candidates")
    if not isinstance(choice, int) or not isinstance(candidates, list):
        return None, "decision-invalid"
    context_digest = decision.get("context_digest")
    if not isinstance(context_digest, str) or len(context_digest) != 64:
        return None, "decision-invalid"
    context_units = decision.get("context_units")
    if not isinstance(context_units, int) or isinstance(context_units, bool):
        return None, "decision-invalid"
    source_snapshot = decision.get("source_snapshot")
    if not isinstance(source_snapshot, list):
        return None, "decision-invalid"
    external_context = decision.get("external_context")
    if not isinstance(external_context, bool):
        return None, "decision-invalid"
    if not 0 <= choice < len(candidates):
        return None, "decision-invalid"
    if candidates[choice]["cluster"] != list(cluster):
        return None, "decision-mismatch"
    thought_patch = decision.get("thought_patch")
    if thought_patch is not None:
        patch_issues = epistemic_agenda.validate_thought_patch(candidates[choice], thought_patch)
        if patch_issues:
            return None, "thought-patch-invalid"
        if digest(thought_patch) != decision.get("thought_patch_digest"):
            return None, "thought-patch-digest"
    previous_digest = (
        doc["events"][-1]["event_digest"]
        if doc["events"]
        else digest(
            {
                "type": "session-start",
                "session_id": doc["session_id"],
                "state_digest": digest(doc["initial_state"]),
            }
        )
    )
    stored_decision = {
        "choice": choice,
        "candidate_count": len(candidates),
        "candidate_set_digest": digest(candidates),
        "chosen_candidate_digest": digest(candidates[choice]),
        "context_digest": context_digest,
        "context_units": context_units,
        "source_snapshot": copy.deepcopy(source_snapshot),
        "source_snapshot_digest": digest(source_snapshot),
        "external_context": external_context,
        "candidates": copy.deepcopy(candidates),
    }
    if thought_patch is not None:
        stored_decision["thought_patch"] = copy.deepcopy(thought_patch)
        stored_decision["thought_patch_digest"] = digest(thought_patch)
    event = {
        "seq": len(doc["events"]) + 1,
        "type": "turn-commit",
        "prev_digest": previous_digest,
        "state_before_digest": digest(before_state),
        "state_after_digest": digest(after_state),
        "cluster": list(cluster),
        "kind": kind,
        "predicted": sorted(set(predicted)),
        "resolved": sorted(set(resolved)),
        "changed_keys": sorted(set(changed_keys)),
        "state": copy.deepcopy(after_state),
        "atom_trace": copy.deepcopy(atom_trace),
        "decision": stored_decision,
        "calibration_before_digest": (calibration_before_digest or digest({})),
        "calibration_after_digest": (calibration_after_digest or digest({})),
        "observations": list(observations or []),
        "created_at": _now(),
    }
    event["event_digest"] = _event_digest(event)
    doc["events"].append(event)
    try:
        _write(Path(path), doc, expected_revision=revision)
    except (RuntimeError, ValueError) as exc:
        return None, str(exc)
    return doc, "appended"


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


def replay(doc: dict) -> dict:
    """从 initial_state 确定性重放每个已提交原子簇。"""
    from . import context_pack
    from .cognitive_cockpit import execute_cluster
    from .constrained_choice import build_prompt_payload

    issues = []
    state = copy.deepcopy(doc["initial_state"])
    for event in doc["events"]:
        for question in event["observations"]:
            state.setdefault("open_questions", []).append(question)
        if not event["decision"]["external_context"]:
            try:
                payload = build_prompt_payload(state, event["decision"]["candidates"])
                if context_pack.digest(payload) != event["decision"]["context_digest"]:
                    issues.append(f"context:{event['seq']}")
            except Exception:
                issues.append(f"context-build:{event['seq']}")
        result = execute_cluster(
            state, event["cluster"], thought_patch=event["decision"].get("thought_patch")
        )
        if result["status"] != "pass":
            issues.append(f"execute:{event['seq']}")
            break
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
        if digest(replayed) != event["state_after_digest"]:
            issues.append(f"state:{event['seq']}")
        if set(result["resolved"]) != set(event["resolved"]):
            issues.append(f"resolved:{event['seq']}")
        if set(result["changed_keys"]) != set(event["changed_keys"]):
            issues.append(f"changed:{event['seq']}")
        if result["atom_trace"] != event["atom_trace"]:
            issues.append(f"trace:{event['seq']}")
        state = copy.deepcopy(event["state"])
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "turns": len(doc["events"]),
    }
