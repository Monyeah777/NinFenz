"""Compile a selected method bundle into a bounded model work contract."""

from __future__ import annotations

from pathlib import Path

from . import json_asset
from . import live_selector as ls

BASE = Path(__file__).parent
ATOMS = {item["id"]: item for item in json_asset.load(BASE / "meta_atoms.json")["atoms"]}

FUNCTION_CONTEXT = {
    "knowledge": ["definition", "scope", "examples"],
    "monitoring": ["current-state", "events", "observable-signals"],
    "control": ["constraints", "budget", "fallback"],
    "evaluation": ["evidence", "counterexamples", "acceptance-obligations"],
    "integration": ["relations", "prerequisites", "unresolved-conflicts"],
}

CLOSURE_FOR_OUTPUT = {
    "parts": "每个 part 代表独立可检验的对象",
    "relations": "关系必须锚定已有 part，不得只给孤立关系词",
    "risks": "风险要说明触发条件、失败后果或回退义务",
    "plan": "综合必须覆盖当前全部 part",
    "evidence": "证据标记必须能落到已验证来源",
    "verified": "verified=true 只能与证据同时成立",
    "open_questions": "开放问题必须由冲突消解原子关闭",
}

LEVELS = ("M0", "M1", "M2", "M3", "M4")


def build_contract(candidate: dict, profile: dict | None = None) -> dict:
    atom_ids = list(candidate["cluster"])
    atoms = [ATOMS[atom_id] for atom_id in atom_ids]
    functions = sorted({atom["function"] for atom in atoms})
    levels = sorted(
        {atom["level_min"] for atom in atoms} | {atom["level_max"] for atom in atoms},
        key=LEVELS.index,
    )
    patch_keys = sorted({key for atom_id in atom_ids for key in ls.CONTRACTS[atom_id]["adds"]})
    roles = {role for function in functions for role in FUNCTION_CONTEXT[function]}
    if profile:
        roles |= set(profile.get("context_roles", []))
    closure = [CLOSURE_FOR_OUTPUT[key] for key in patch_keys if key in CLOSURE_FOR_OUTPUT]
    if candidate.get("resolves"):
        closure.append("预测必须由本回合真实状态增量兑现")
    return {
        "schema": "nf-thought-contract/1",
        "atom_ids": atom_ids,
        "meta_functions": functions,
        "meta_levels": levels,
        "patch_keys": patch_keys,
        "context_roles": sorted(roles),
        "closure_rules": sorted(set(closure)),
        "patch_required": False,
    }


def build_contracts(candidates: list[dict], profile: dict | None = None) -> list[dict]:
    return [build_contract(candidate, profile=profile) for candidate in candidates]
