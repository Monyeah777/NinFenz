"""跨运行可靠性存储：schema/契约 digest/完整性/一致性/衰减/原子写。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from . import atomic_io, file_lock, json_asset
from . import calibration_ledger as cl
from . import live_selector as ls

BASE = Path(__file__).parent
SCHEMA = "nf-calibration-store/1"
MAX_TRIALS = 500
MAX_STORE_BYTES = 1_048_576
ATOM_IDS = set(ls.CONTRACTS)
REVISION_KEY = "_file_revision"


def contracts_digest() -> str:
    return hashlib.sha256((BASE / "atom_contracts.json").read_bytes()).hexdigest()


def _digest(doc: dict) -> str:
    payload = {k: doc[k] for k in ("schema", "rounds", "atom_contracts_digest", "atoms")}
    canon = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def initial_store() -> dict:
    return {
        "schema": SCHEMA,
        "rounds": 0,
        "atom_contracts_digest": contracts_digest(),
        "atoms": cl.initial_ledger(),
    }


def _normalize(atoms: dict) -> dict:
    for rec in atoms.values():
        if rec["trials"] > MAX_TRIALS:
            factor = MAX_TRIALS / rec["trials"]
            rec["successes"] = round(rec["successes"] * factor)
            rec["trials"] = MAX_TRIALS
            rec["reliability"] = round(rec["successes"] / rec["trials"], 3)
    return atoms


def _validate(doc: dict) -> list[str]:
    issues = []
    if doc.get("schema") != SCHEMA:
        issues.append("schema")
    if doc.get("atom_contracts_digest") != contracts_digest():
        issues.append("contracts")
    atoms = doc.get("atoms")
    if not isinstance(atoms, dict):
        return issues + ["atoms"]
    if set(atoms) != ATOM_IDS:
        issues.append("atom-set")
    for aid, rec in atoms.items():
        if aid not in ATOM_IDS or not isinstance(rec, dict):
            continue
        s, t, r = rec.get("successes"), rec.get("trials"), rec.get("reliability")
        if (
            not isinstance(s, (int, float))
            or isinstance(s, bool)
            or not isinstance(t, (int, float))
            or isinstance(t, bool)
            or not isinstance(r, (int, float))
            or isinstance(r, bool)
        ):
            issues.append(f"types:{aid}")
            continue
        if s < 0 or t <= 0 or s > t:
            issues.append(f"counts:{aid}")
        elif abs(float(r) - s / t) > 0.02:
            issues.append(f"reliability:{aid}")
    if doc.get("digest") != _digest(doc):
        issues.append("digest")
    return issues


def load(path: Path) -> tuple[dict, str]:
    p = Path(path)
    if not p.is_file():
        return initial_store(), "missing"
    if p.stat().st_size > MAX_STORE_BYTES:
        return initial_store(), "tampered:size"
    try:
        doc = json_asset.load(p)
    except (OSError, UnicodeError, ValueError, RecursionError):
        return initial_store(), "tampered:json"
    issues = _validate(doc)
    if issues:
        return initial_store(), "tampered:" + ",".join(issues)
    doc["atoms"] = _normalize(doc["atoms"])
    doc[REVISION_KEY] = hashlib.sha256(p.read_bytes()).hexdigest()
    return doc, "ok"


def save(path: Path, store: dict) -> dict:
    p = Path(path)
    with file_lock.locked(p):
        if p.is_file() and p.stat().st_size > MAX_STORE_BYTES:
            raise ValueError("calibration store too large")
        expected_revision = store.get(REVISION_KEY)
        current_revision = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        if expected_revision is not None and current_revision != expected_revision:
            raise RuntimeError("concurrent-write")
        atoms = _normalize(store["atoms"])
        doc = {
            "schema": SCHEMA,
            "rounds": int(store.get("rounds", 0)) + 1,
            "atom_contracts_digest": contracts_digest(),
            "atoms": atoms,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        doc["digest"] = _digest(doc)
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if len(text.encode("utf-8")) > MAX_STORE_BYTES:
            raise ValueError("calibration store too large")
        atomic_io.write_text(p, text)
        doc[REVISION_KEY] = hashlib.sha256(p.read_bytes()).hexdigest()
        return doc
