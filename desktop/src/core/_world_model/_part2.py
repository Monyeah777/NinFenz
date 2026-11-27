"""core.world_model 私有实现分片 2/3（对外只经 core.world_model 门面导入）：_check_check_item 等"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ._part1 import (
    _abstract_parts,
    _check_finite_sequence,
    _check_initial,
    _check_invariants,
    _check_reachability,
    _check_values,
    _nonempty,
    _phases,
    _transition_parts,
    _variables,
)


def _check_check_item(check: dict, at: str, declared_names: List[str],
                      declared_kinds: Dict[str, Any], valid_vars: list,
                      issues: List[str]) -> None:
    """单条 checks 项：kind/field/values 三面 + 按 kind 的类型约束。"""
    kind = check.get("kind")
    field = check.get("field")
    values = check.get("values")
    if kind not in ("finite_phase", "monotonic", "finite_sequence"):
        issues.append(f"{at}.kind: 非法检查类型 {kind!r}")
    if not _nonempty(field):
        issues.append(f"{at}.field: 非空字符串")
    elif field not in declared_names:
        issues.append(f"{at}.field: 未声明变量 {field!r}")
    if kind in ("finite_phase", "finite_sequence"):
        _check_values(values, kind, at, issues)
    elif kind == "monotonic" and declared_kinds.get(field) not in ("integer", "number"):
        issues.append(f"{at}.field: monotonic 只能用于 integer/number 变量")
    if kind == "finite_sequence":
        _check_finite_sequence(field, declared_kinds, valid_vars, at, issues)


def _check_checks(wm: dict, valid_vars: list, label: str,
                  issues: List[str]) -> None:
    """checks 面：缺省跳过；在场则须为非空数组且逐条合规。"""
    declared_names = [v.get("name") for v in valid_vars if isinstance(v.get("name"), str)]
    declared_kinds = {v.get("name"): v.get("kind") for v in valid_vars
                      if isinstance(v.get("name"), str)}
    checks = wm.get("checks")
    if checks is None:
        return
    if not isinstance(checks, list) or not checks:
        issues.append(f"{label}.checks: 非空数组")
        checks = []
    for idx, check in enumerate(checks):
        at = f"{label}.checks[{idx}]"
        if not isinstance(check, dict):
            issues.append(f"{at}: 非对象")
            continue
        _check_check_item(check, at, declared_names, declared_kinds, valid_vars, issues)


def _check_slot_registry(valid_vars: list, slot_registry: Dict[str, Dict[str, Any]],
                         label: str, issues: List[str]) -> None:
    """槽位面：在册 / kind 一致 / 元素类型一致 / owner 一致。"""
    for var in valid_vars:
        slot = var.get("slot")
        if not _nonempty(slot):
            continue
        name = var.get("name")
        source = var.get("source")
        spec = slot_registry.get(slot)
        if not isinstance(spec, dict):
            issues.append(
                f"{label}.abstract_state.variables[{name!r}].slot: "
                f"未在 protocol/world_slots.json 注册 {slot!r}"
            )
            continue
        if spec.get("kind") != var.get("kind"):
            issues.append(
                f"{label}.abstract_state.variables[{name!r}].slot: "
                f"类型漂移 slot={spec.get('kind')!r} var={var.get('kind')!r}"
            )
        if var.get("kind") == "array" and var.get("item_kind") and (
            spec.get("item_kind") != var.get("item_kind")
        ):
            issues.append(
                f"{label}.abstract_state.variables[{name!r}].slot: "
                f"元素类型漂移 slot={spec.get('item_kind')!r} "
                f"var={var.get('item_kind')!r}"
            )
        if spec.get("owner") and source != spec.get("owner"):
            issues.append(
                f"{label}.abstract_state.variables[{name!r}].slot: "
                f"owner 漂移 slot={spec.get('owner')!r} var.source={source!r}"
            )


def validate_contract(wm: Any, label: str = "world_model",
                      slot_registry: Dict[str, Dict[str, Any]] | None = None) -> List[str]:
    """校验单个 world_model 契约；返回可读违例清单。"""
    issues: List[str] = []
    if not isinstance(wm, dict):
        return [f"{label}: 非对象"]

    variables, initial = _abstract_parts(wm, label, issues)
    _names, _slots, valid_vars = _variables(variables, label, issues)
    _check_initial(initial, valid_vars, label, issues)

    initial_phase, phases = _transition_parts(wm, label, issues)
    phase_names, edges = _phases(phases, label, issues)
    _check_reachability(initial_phase, phase_names, edges, label, issues)

    _check_invariants(wm, label, issues)
    _check_checks(wm, valid_vars, label, issues)
    if slot_registry:
        _check_slot_registry(valid_vars, slot_registry, label, issues)
    return issues


def build_graph(wm: Dict[str, Any]) -> Dict[str, Any]:
    """把 world_model.transition 投影成可执行的确定性相位图。"""
    transition = wm.get("transition") or {}
    phases = transition.get("phases") or []
    by_name = {}
    for item in phases:
        if isinstance(item, dict) and isinstance(item.get("phase"), str):
            by_name[item["phase"]] = {
                "next": item.get("next"),
                "guard": item.get("guard", ""),
                "writes": list(item.get("writes") or []),
            }
    return {
        "initial_phase": transition.get("initial_phase"),
        "phases": by_name,
    }


class WorldModelViolation(ValueError):
    """world_model 运行态违例；issues 为可读违例清单。"""

    def __init__(self, issues: List[str]):
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))


def trace_digest(result: Dict[str, Any]) -> str:
    """对 replay 的 steps 做规范 JSON 摘要，作为确定性重放指纹。"""
    import hashlib

    payload = json.dumps(result.get("steps") or [], sort_keys=True,
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def initial_state(wm: Dict[str, Any]) -> Dict[str, Any]:
    """返回 abstract_state.initial 的深拷贝，作为可重放的初始状态。"""
    import copy

    abstract = wm.get("abstract_state") or {}
    return copy.deepcopy(abstract.get("initial") or {})
