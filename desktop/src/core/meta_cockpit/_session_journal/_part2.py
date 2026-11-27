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


def append_turn(path: Path, goal: str, opts: TurnOptions) -> tuple[dict | None, str]:
    before_state = opts.before_state
    after_state = opts.after_state
    cluster = opts.cluster
    kind = opts.kind
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
