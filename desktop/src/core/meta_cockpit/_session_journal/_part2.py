"""core.session_journal 私有实现分片 2/2（对外只经 core.session_journal 门面导入）：load 等"""

from __future__ import annotations

import copy
import uuid
from pathlib import Path

from core.meta_cockpit import calibration_ledger, epistemic_agenda, json_asset

from ._part1 import (
    MAX_JOURNAL_BYTES,
    SCHEMA_NAME,
    TurnOptions,
    _document_digest,
    _event_digest,
    _file_revision,
    _forbidden_paths,
    _now,
    _source_drift,
    _validate,
    _write,
    contracts_digest,
    current_state,
    digest,
    replay,
    runtime_digest,
)


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


def _append_guard(after_state: dict, cluster: list[str], atom_trace: list[dict]) -> str | None:
    if _forbidden_paths({"state": after_state, "cluster": cluster}):
        return "forbidden-drive-key"
    if [item.get("atom_id") for item in atom_trace] != list(cluster):
        return "atom-trace-mismatch"
    if any(item.get("status") != "pass" for item in atom_trace):
        return "atom-trace-failed"
    return None


def _decision_scalar_ok(decision: dict) -> bool:
    context_digest = decision.get("context_digest")
    if not isinstance(context_digest, str) or len(context_digest) != 64:
        return False
    context_units = decision.get("context_units")
    if not isinstance(context_units, int) or isinstance(context_units, bool):
        return False
    if not isinstance(decision.get("source_snapshot"), list):
        return False
    return isinstance(decision.get("external_context"), bool)


def _decision_guard(decision: dict, cluster: list[str]) -> str | None:
    choice = decision.get("choice")
    candidates = decision.get("candidates")
    if not isinstance(choice, int) or not isinstance(candidates, list):
        return "decision-invalid"
    if not _decision_scalar_ok(decision):
        return "decision-invalid"
    if not 0 <= choice < len(candidates):
        return "decision-invalid"
    if candidates[choice]["cluster"] != list(cluster):
        return "decision-mismatch"
    return None


def _patch_guard(decision: dict, candidate: dict) -> str | None:
    thought_patch = decision.get("thought_patch")
    if thought_patch is None:
        return None
    patch_issues = epistemic_agenda.validate_thought_patch(candidate, thought_patch)
    if patch_issues:
        return "thought-patch-invalid"
    if digest(thought_patch) != decision.get("thought_patch_digest"):
        return "thought-patch-digest"
    return None


def _previous_digest(doc: dict) -> str:
    if doc["events"]:
        return doc["events"][-1]["event_digest"]
    return digest(
        {
            "type": "session-start",
            "session_id": doc["session_id"],
            "state_digest": digest(doc["initial_state"]),
        }
    )


def _stored_decision(decision: dict) -> dict:
    choice = decision["choice"]
    candidates = decision["candidates"]
    stored_decision = {
        "choice": choice,
        "candidate_count": len(candidates),
        "candidate_set_digest": digest(candidates),
        "chosen_candidate_digest": digest(candidates[choice]),
        "context_digest": decision["context_digest"],
        "context_units": decision["context_units"],
        "source_snapshot": copy.deepcopy(decision["source_snapshot"]),
        "source_snapshot_digest": digest(decision["source_snapshot"]),
        "external_context": decision["external_context"],
        "candidates": copy.deepcopy(candidates),
    }
    thought_patch = decision.get("thought_patch")
    if thought_patch is not None:
        stored_decision["thought_patch"] = copy.deepcopy(thought_patch)
        stored_decision["thought_patch_digest"] = digest(thought_patch)
    return stored_decision


def _turn_event(doc: dict, opts: TurnOptions, before_state: dict, after_state: dict) -> dict:
    return {
        "seq": len(doc["events"]) + 1,
        "type": "turn-commit",
        "prev_digest": _previous_digest(doc),
        "state_before_digest": digest(before_state),
        "state_after_digest": digest(after_state),
        "cluster": list(opts.cluster),
        "kind": opts.kind,
        "predicted": sorted(set(opts.predicted)),
        "resolved": sorted(set(opts.resolved)),
        "changed_keys": sorted(set(opts.changed_keys)),
        "state": copy.deepcopy(after_state),
        "atom_trace": copy.deepcopy(opts.atom_trace),
        "decision": _stored_decision(opts.decision),
        "calibration_before_digest": (opts.calibration_before_digest or digest({})),
        "calibration_after_digest": (opts.calibration_after_digest or digest({})),
        "observations": list(opts.observations or []),
        "created_at": _now(),
    }


def append_turn(path: Path, goal: str, opts: TurnOptions) -> tuple[dict | None, str]:
    before_state = opts.before_state
    after_state = opts.after_state
    cluster = opts.cluster
    predicted = opts.predicted
    resolved = opts.resolved
    changed_keys = opts.changed_keys
    atom_trace = opts.atom_trace
    decision = opts.decision
    calibration_before_digest = opts.calibration_before_digest
    calibration_after_digest = opts.calibration_after_digest
    observations = opts.observations
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
    guard = _append_guard(after_state, cluster, atom_trace)
    if guard is not None:
        return None, guard
    guard = _decision_guard(decision, cluster)
    if guard is not None:
        return None, guard
    guard = _patch_guard(decision, decision["candidates"][decision["choice"]])
    if guard is not None:
        return None, guard
    event = _turn_event(doc, opts, before_state, after_state)
    event["event_digest"] = _event_digest(event)
    doc["events"].append(event)
    try:
        _write(Path(path), doc, expected_revision=revision)
    except (RuntimeError, ValueError) as exc:
        return None, str(exc)
    return doc, "appended"
