"""约束选择：模型只能在编译出的安全候选里选。"""

from __future__ import annotations

from pathlib import Path

from . import calibration_ledger as cl
from . import cognitive_cockpit as cc
from . import (
    coherence,
    context_pack,
    epistemic_agenda,
    evidence_roles,
    json_asset,
    secret_guard,
    task_profile,
)
from . import live_selector as ls
from . import plan_compiler as pc
from . import schema_compat as jsonschema
from . import thought_contract as tc

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "constrained_choice.schema.json")
V = jsonschema.Draft202012Validator(SCHEMA)
PAYLOAD_SCHEMA = json_asset.load(BASE / "constrained_candidates.schema.json")
PV = jsonschema.Draft202012Validator(PAYLOAD_SCHEMA)


def _raw_candidates(s: dict) -> list[dict]:
    raw = []
    families = ls.candidate_families(s, direct_limit=3, progress_limit=48, max_cost=3)
    # 候选面刻意混合“即刻补缺口”和“扩展方法能力”，而不是让结构覆盖率
    # 最高的同型链占满五个槽位。
    direct = families["direct"]
    for c in direct:
        raw.append(
            {
                "cluster": c["cluster"],
                "resolves": c["resolves"],
                "cost": c["cost"],
                "kind": "direct",
            }
        )
    try:
        comp = pc.compile_goals(s, max_cost=3)
        prefix: list[str] = []
        for st in comp["stages"]:
            if len(prefix) + len(st) > 3:
                break
            prefix += st
        if prefix:
            raw.append(
                {
                    "cluster": prefix,
                    "resolves": ls.resolved(tuple(prefix), s),
                    "cost": sum(ls.CONTRACTS[a]["cost"] for a in prefix),
                    "kind": "compiled",
                }
            )
    except ValueError:
        pass
    direct_keys = {tuple(c["cluster"]) for c in direct}
    for c in families["progress"]:
        if tuple(c["cluster"]) in direct_keys:
            continue
        raw.append({**c, "kind": "direct" if c["resolves"] else "prepare"})
    return raw


def _validated_candidates(s: dict, ledger: dict, raw: list[dict]) -> list[dict]:
    before_keys = ls.available_keys(s)
    out, seen = [], set()
    for c in raw:
        key = tuple(c["cluster"])
        if key in seen:
            continue
        seen.add(key)
        if not c["cluster"] or len(c["cluster"]) > 3:
            continue
        if len(set(c["cluster"])) != len(c["cluster"]):
            continue
        if any(a not in ls.CONTRACTS for a in c["cluster"]):
            continue
        if ls.simulate(key, s) is None or c["cost"] > 3:
            continue
        if any(ledger[a]["reliability"] < cl.RELIABILITY_FLOOR for a in c["cluster"]):
            continue
        # 契约模拟不等于执行可落地：预跑同一执行/写回路径，防止模型选中
        # 一个必然缺输入或无法兑现 resolves 的“纸面候选”。
        preview = cc.execute_cluster(s, c["cluster"])
        if preview["status"] != "pass":
            continue
        if coherence.new_issue_ids(s, preview["state"]):
            continue
        if set(preview["resolved"]) != set(c["resolves"]):
            continue
        effect = c.get("effect") or {}
        if not set(effect.get("adds", [])) <= set(preview["changed_keys"]):
            continue
        out.append(
            {
                **c,
                "effect": {
                    "adds": sorted(set(preview["changed_keys"])),
                    "removes": sorted(before_keys - ls.available_keys(preview["state"])),
                },
            }
        )
    return out


def _select_candidates(s: dict, profile: dict, out: list[dict]) -> list[dict]:
    if not out:
        return []
    desired = set(profile["functions"])
    preferred_atoms = set(profile["preferred_atoms"])
    repair_keys = set(task_profile.repair_keys(s, profile)) | set(coherence.repair_keys(s))
    covered_functions: set[str] = set()
    covered_preferred: set[str] = set()
    covered_repairs: set[str] = set()
    covered_effects: set[str] = set()
    selected: list[dict] = []
    remaining = list(range(len(out)))

    def functions(index: int) -> set[str]:
        return {tc.ATOMS[atom_id]["function"] for atom_id in out[index]["cluster"]}

    def take(index: int) -> None:
        item = out[index]
        selected.append(item)
        covered_functions.update(functions(index))
        covered_preferred.update(set(out[index]["cluster"]) & preferred_atoms)
        covered_repairs.update(set(out[index]["effect"]["adds"]) & repair_keys)
        covered_effects.update(item["effect"]["adds"])
        remaining.remove(index)

    def priority(index: int) -> tuple:
        item = out[index]
        funcs = functions(index)
        adds = set(item["effect"]["adds"])
        return (
            -len(adds & repair_keys - covered_repairs),
            -len(set(item["cluster"]) & preferred_atoms - covered_preferred),
            -len((funcs & desired) - covered_functions),
            -len(funcs - covered_functions),
            -len(adds - covered_effects),
            0 if item["kind"] == "compiled" else 1 if item["kind"] == "direct" else 2,
            item["cost"],
            index,
        )

    anchor = next(
        (index for index, item in enumerate(out) if item["kind"] == "direct" and item["resolves"]),
        None,
    )
    if anchor is None:
        take(min(remaining, key=priority))
        anchor = out.index(selected[0])
    else:
        take(anchor)
    while remaining and len(selected) < 5:
        take(min(remaining, key=priority))

    def basis(candidate: dict) -> list[str]:
        index = out.index(candidate)
        values = []
        if index == anchor:
            values.append("anchor")
        values += [
            "repair-key:" + key for key in sorted(set(candidate["effect"]["adds"]) & repair_keys)
        ]
        values += [
            "preferred-atom:" + atom_id
            for atom_id in candidate["cluster"]
            if atom_id in preferred_atoms
        ]
        values += ["function:" + function for function in sorted(functions(index) & desired)]
        values += ["resolves:" + need for need in candidate["resolves"]]
        values.append("kind:" + candidate["kind"])
        return list(dict.fromkeys(values))

    return [{**candidate, "basis": basis(candidate)} for candidate in selected]


def build_candidates(s: dict, ledger: dict) -> list[dict]:
    profile = task_profile.build(s["goal"])
    raw = _raw_candidates(s)
    validated = _validated_candidates(s, ledger, raw)
    return _select_candidates(s, profile, validated)


def validate(resp: dict, candidates: list[dict], state: dict | None = None) -> list[str]:
    issues = [e.message for e in V.iter_errors(resp)]
    issues.extend(
        "sensitive data: {} ({})".format(item["path"], item["kind"])
        for item in secret_guard.find(resp, "$.response")
    )
    if not isinstance(resp, dict):
        return issues
    choice, stop = resp.get("choice"), resp.get("stop")
    if choice is None:
        if stop is not True:
            issues.append("null choice requires stop=true")
    else:
        if stop is not False:
            issues.append("choice requires stop=false")
        if not isinstance(choice, int) or not (0 <= choice < len(candidates)):
            issues.append("choice out of range")
        elif "thought_patch" in resp:
            issues.extend(
                epistemic_agenda.validate_thought_patch(candidates[choice], resp["thought_patch"])
            )
    return issues


def build_prompt_payload(s: dict, candidates: list[dict], providers: list | None = None) -> dict:
    before = ls.available_keys(s)
    profile = task_profile.build(s["goal"])
    described = []
    for c in candidates:
        after = ls.simulate(tuple(c["cluster"]), s)
        effect = {
            "adds": sorted((after or set()) - before),
            "removes": sorted(before - (after or set())),
        }
        described.append(
            {
                "cluster": c["cluster"],
                "resolves": c["resolves"],
                "cost": c["cost"],
                "kind": c["kind"],
                "effect": effect,
                "contract": tc.build_contract(c, profile=profile),
                "basis": c.get("basis", []),
            }
        )
    payload = {
        "schema": "nf-constrained-candidates/1",
        "goal": s["goal"],
        "turn": int(s.get("turn", 0)),
        "unmet": ls.unmet(s),
        "agenda": epistemic_agenda.build_agenda(s),
        "task_profile": profile,
        "facet_agenda": task_profile.build_facet_agenda(s, profile),
        "coherence": coherence.evaluate(s),
        "candidate_context": {
            "anchor_cluster": next(
                (
                    candidate["cluster"]
                    for candidate in candidates
                    if "anchor" in candidate.get("basis", [])
                ),
                [],
            ),
            "repair_keys": sorted(
                set(task_profile.repair_keys(s, profile)) | set(coherence.repair_keys(s))
            ),
            "preferred_atoms": profile["preferred_atoms"],
            "desired_functions": profile["functions"],
            "candidate_limit": 5,
            "bounded_progress_pool": 48,
            "no_scoring": True,
        },
        "candidates": described,
        "constraints": {
            "max_atoms": 3,
            "max_cost": 3,
            "no_scoring": True,
            "no_full_plan": True,
            "thought_patch_mode": "optional",
        },
    }
    requested_roles = sorted(
        {role for item in described for role in item["contract"]["context_roles"]}
    )
    context = context_pack.build_context_pack(
        s["goal"], s, candidates, providers=providers, requested_roles=requested_roles
    )
    role_inventory = evidence_roles.build_role_inventory(s, context, requested_roles)
    payload["state_view"] = context.pop("state_view")
    payload["method_cards"] = context.pop("method_cards")
    payload["graph_slice"] = context.pop("graph_slice")
    payload["context"] = context
    payload["evidence_roles"] = role_inventory
    for _ in range(4):
        used = context_pack.enforce_budget(payload)
        if context["budget"]["estimated_units"] == used:
            break
        context["budget"]["estimated_units"] = used
    else:
        raise ValueError("context budget did not converge")
    issues = [e.message for e in PV.iter_errors(payload)]
    if issues:
        raise ValueError("invalid candidate payload: {}".format("; ".join(issues)))
    return payload


def apply(s: dict, candidates: list[dict], resp: dict, thought_patch: dict | None = None) -> dict:
    if resp.get("choice") is None:
        return {"status": "stop", "state": s, "resolved": []}
    before = set(ls.unmet(s))
    choice = resp.get("choice")
    if not isinstance(choice, int) or not 0 <= choice < len(candidates):
        return {"status": "fail", "state": s, "resolved": [], "error": "choice out of range"}
    c = candidates[choice]
    patch = thought_patch if thought_patch is not None else resp.get("thought_patch")
    executed = cc.execute_cluster(s, c["cluster"], thought_patch=patch)
    if executed["status"] != "pass":
        return executed
    resolved = sorted(before - set(ls.unmet(executed["state"])))
    return {**executed, "resolved": resolved}
