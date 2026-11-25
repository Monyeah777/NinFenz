#!/usr/bin/env python3
"""Validate the NF hard-tech governance registry.

This is a planning artifact validator, not a runtime feature.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "results/app/governance/registry.json"
SCHEMA = ROOT / "results/app/governance/schema.json"

STATES = {"absent", "partial", "conformant", "benchmarked", "leading"}
STAGES = {"not-started", "research", "prototype", "product", "proven"}
LAYERS = {f"C{i}" for i in range(10)}
H_LAYERS = {f"H{i}" for i in range(1, 7)}


def load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def validate_registry(data: dict, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        import jsonschema
        schema = json.loads((root / "results/app/governance/schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(data, schema)
    except Exception as exc:  # schema or validation failure
        errors.append(f"schema: {exc}")

    cov = data.get("coverage", {})
    nodes = cov.get("nodes", [])
    if len(nodes) != 112:
        errors.append(f"coverage must be 112, got {len(nodes)}")
    ids = [n.get("id") for n in nodes]
    if len(set(ids)) != len(ids):
        errors.append("coverage has duplicate ids")
    base_ids = cov.get("baseline_ids", [])
    new_ids = cov.get("new_ids", [])
    if len(base_ids) != 92:
        errors.append(f"baseline_ids must be 92, got {len(base_ids)}")
    if len(new_ids) != 20:
        errors.append(f"new_ids must be 20, got {len(new_ids)}")
    if set(base_ids) & set(new_ids):
        errors.append("baseline_ids and new_ids overlap")
    if set(ids) != set(base_ids) | set(new_ids):
        errors.append("coverage nodes must equal baseline_ids + new_ids")
    for n in nodes:
        if n.get("layer") not in LAYERS:
            errors.append(f"{n.get('id')}: bad layer")
        if n.get("current_state") not in STATES:
            errors.append(f"{n.get('id')}: bad current_state")
        if n.get("source") not in {"baseline", "gap", "open"}:
            errors.append(f"{n.get('id')}: bad source")
        if n.get("priority") == "P0" and (not n.get("owner") or not n.get("next")):
            errors.append(f"{n.get('id')}: P0 needs owner/next")

    hs = data.get("hard_capabilities", [])
    ts = data.get("trials", [])
    if len(hs) != 24:
        errors.append(f"hard_capabilities must be 24, got {len(hs)}")
    if len(ts) != 10:
        errors.append(f"trials must be 10, got {len(ts)}")
    h_ids = [h.get("id") for h in hs]
    if len(set(h_ids)) != len(h_ids):
        errors.append("duplicate hard capability ids")
    t_ids = [t.get("id") for t in ts]
    if len(set(t_ids)) != len(t_ids):
        errors.append("duplicate trial ids")

    for layer in H_LAYERS:
        count = sum(1 for h in hs if h.get("layer") == layer)
        if count != 4:
            errors.append(f"{layer}: expected 4 hard capabilities, got {count}")

    known_nodes = set(ids)
    known_h = set(h_ids)
    known_t = set(t_ids)
    trial_by_id = {t.get("id"): t for t in ts}
    for h in hs:
        hid = h.get("id")
        if h.get("layer") not in H_LAYERS:
            errors.append(f"{hid}: bad layer")
        if h.get("hardness") not in {"H1", "H2", "H3"}:
            errors.append(f"{hid}: bad hardness")
        if len(h.get("moat", "")) < 20:
            errors.append(f"{hid}: moat too short")
        if h.get("current_stage") not in STAGES:
            errors.append(f"{hid}: bad current_stage")
        if h.get("target_stage") != "proven":
            errors.append(f"{hid}: target_stage must be proven")
        if not h.get("benchmark") or not h.get("threshold") or not h.get("corpus"):
            errors.append(f"{hid}: benchmark/threshold/corpus required")
        if h.get("current_stage") == "proven":
            ev = h.get("evidence")
            if not isinstance(ev, dict):
                errors.append(f"{hid}: proven requires evidence")
            else:
                kind = ev.get("kind", "trial")
                if kind == "benchmark":
                    if not ev.get("benchmark"):
                        errors.append(f"{hid}: benchmark evidence needs benchmark id")
                else:
                    tid = ev.get("trial_id")
                    if tid not in h.get("trial_ids", []):
                        errors.append(f"{hid}: evidence trial {tid} not in trial_ids")
                    t = trial_by_id.get(tid)
                    if t is None:
                        errors.append(f"{hid}: evidence trial {tid} not found")
                    elif t.get("status") != "passed":
                        errors.append(f"{hid}: proven requires passed trial {tid}")
                if not ev.get("result_path") or not ev.get("result_sha256") or not ev.get("run_at"):
                    errors.append(f"{hid}: evidence needs result_path/result_sha256/run_at")
                else:
                    rp = (root / ev["result_path"]).resolve()
                    if not rp.is_file():
                        errors.append(f"{hid}: evidence result missing {ev['result_path']}")
                    else:
                        actual = hashlib.sha256(rp.read_bytes()).hexdigest()
                        if actual != ev["result_sha256"]:
                            errors.append(f"{hid}: evidence result sha mismatch")
                if not isinstance(ev.get("n"), int) or ev.get("n", 0) < 1:
                    errors.append(f"{hid}: evidence n must be >=1")
        if not h.get("node_ids"):
            errors.append(f"{hid}: node_ids required")
        for nid in h.get("node_ids", []):
            if nid not in known_nodes:
                errors.append(f"{hid}: unknown node {nid}")
        if not h.get("trial_ids"):
            errors.append(f"{hid}: no trial covers it")

    for t in ts:
        tid = t.get("id")
        if len(t.get("hard_ids", [])) < 2:
            errors.append(f"{tid}: needs >=2 hard capabilities")
        for hid in t.get("hard_ids", []):
            if hid not in known_h:
                errors.append(f"{tid}: unknown hard capability {hid}")
        if t.get("status") not in {"planned", "running", "passed", "failed"}:
            errors.append(f"{tid}: bad status")
        if t.get("status") == "passed":
            if not t.get("result_path") or not t.get("result_sha256"):
                errors.append(f"{tid}: passed trial requires result_path/result_sha256")
            else:
                rp = (root / t["result_path"]).resolve()
                if not rp.is_file():
                    errors.append(f"{tid}: trial result missing {t['result_path']}")
                else:
                    actual = hashlib.sha256(rp.read_bytes()).hexdigest()
                    if actual != t["result_sha256"]:
                        errors.append(f"{tid}: trial result sha mismatch")

    covered = set()
    for t in ts:
        covered.update(t.get("hard_ids", []))
    for hid in known_h:
        if hid not in covered:
            errors.append(f"{hid}: not covered by any trial")

    # Coverage hard_ids must point to known H.
    for n in nodes:
        for hid in n.get("hard_ids", []):
            if hid not in known_h:
                errors.append(f"{n.get('id')}: unknown hard_id {hid}")

    # Summary consistency.
    summary = data.get("summary", {})
    if summary.get("coverage_total") != 112:
        errors.append("summary.coverage_total must be 112")
    if summary.get("hard_capabilities") != 24:
        errors.append("summary.hard_capabilities must be 24")
    if summary.get("trials") != 10:
        errors.append("summary.trials must be 10")
    proven_count = sum(1 for h in hs if h.get("current_stage") == "proven")
    if summary.get("proven_hard") != proven_count:
        errors.append(f"summary.proven_hard must equal actual proven ({proven_count})")
    for layer in H_LAYERS:
        if summary.get("by_layer", {}).get(layer) != 4:
            errors.append(f"summary.by_layer.{layer} must be 4")

    return errors


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "validate"
    data = load()
    if cmd == "coverage":
        print(json.dumps(data.get("summary", {}), ensure_ascii=False, indent=2))
        return 0
    errors = validate_registry(data)
    if errors:
        print("INVALID")
        for e in errors:
            print("- " + e)
        return 1
    print("OK")
    print(json.dumps(data.get("summary", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
