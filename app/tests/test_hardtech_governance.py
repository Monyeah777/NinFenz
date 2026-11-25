from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "hardtech_governance", ROOT / "app/scripts/hardtech_governance.py"
)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def load():
    return MOD.load()


def test_valid_registry():
    assert MOD.validate_registry(load()) == []


def test_coverage_count_is_112():
    data = load()
    assert len(data["coverage"]["nodes"]) == 112
    assert len(data["coverage"]["baseline_ids"]) == 92
    assert len(data["coverage"]["new_ids"]) == 20


def test_duplicate_hard_id_rejected():
    data = load()
    data["hard_capabilities"][1]["id"] = data["hard_capabilities"][0]["id"]
    assert any("duplicate hard capability" in e for e in MOD.validate_registry(data))


def test_hard_missing_benchmark_rejected():
    data = load()
    data["hard_capabilities"][0]["benchmark"] = ""
    assert any("benchmark/threshold/corpus" in e for e in MOD.validate_registry(data))


def test_unknown_trial_hard_id_rejected():
    data = load()
    data["trials"][0]["hard_ids"] = ["H9.9", "H1.1"]
    assert any("unknown hard capability" in e for e in MOD.validate_registry(data))


def test_uncovored_hard_capability_rejected():
    data = load()
    for t in data["trials"]:
        t["hard_ids"] = [h for h in t["hard_ids"] if h != "H1.1"]
    assert any("H1.1: not covered" in e for e in MOD.validate_registry(data))


def test_proven_without_evidence_rejected():
    data = load()
    h = data["hard_capabilities"][0]
    h["current_stage"] = "proven"
    h.pop("evidence", None)
    assert any("proven requires evidence" in e for e in MOD.validate_registry(data))


def test_p0_without_owner_rejected():
    data = load()
    node = next(n for n in data["coverage"]["nodes"] if n["priority"] == "P0")
    node["owner"] = ""
    assert any("P0 needs owner" in e for e in MOD.validate_registry(data))


def test_trial_needs_two_hard_capabilities():
    data = load()
    data["trials"][0]["hard_ids"] = ["H1.1"]
    assert any("needs >=2" in e for e in MOD.validate_registry(data))


def test_short_moat_rejected():
    data = load()
    data["hard_capabilities"][0]["moat"] = "too short"
    assert any("moat too short" in e for e in MOD.validate_registry(data))
