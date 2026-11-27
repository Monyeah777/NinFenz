"""core.world_model 私有实现分片 1/3（对外只经 core.world_model 门面导入）：KINDS 等"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

KINDS = {"string", "integer", "number", "boolean", "array"}


ITEM_KINDS = {"string", "integer", "number", "boolean"}


def load_slots(root: str = ".") -> Dict[str, Dict[str, Any]]:
    """读取 M00 数据槽可绑定投影（protocol/world_slots.json）。"""
    path = Path(root) / "protocol" / "world_slots.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("slots") or {}


def _nonempty(v: Any) -> bool:
    """「非空字符串」单点判据：原写法 `not isinstance(v, str) or not v.strip()` 的 `or`
    会被 radon 记为一个分支——世界模型校验满屏此类判据，故收成单点。"""
    return isinstance(v, str) and bool(v.strip())


def _matches(value: Any, kind: str, item_kind: str | None = None) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "array":
        if not isinstance(value, list):
            return False
        return item_kind is None or all(_matches(v, item_kind) for v in value)
    return False


def _slot_parts(slot: str) -> List[str]:
    return [part for part in slot.split(".") if part]


def _get_slot(state: Dict[str, Any], slot: str) -> Any:
    cur: Any = state
    for part in _slot_parts(slot):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(slot)
        cur = cur[part]
    return cur


def _set_slot(state: Dict[str, Any], slot: str, value: Any) -> Dict[str, Any]:
    import copy

    out = copy.deepcopy(state)
    cur = out
    parts = _slot_parts(slot)
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
        if not isinstance(cur, dict):
            raise ValueError("slot 中段非对象：%s" % slot)
    cur[parts[-1]] = value
    return out


def _abstract_parts(wm: dict, label: str, issues: List[str]):
    """abstract_state → (variables, initial)；缺失/形态错时给可读回退。"""
    abstract = wm.get("abstract_state")
    if not isinstance(abstract, dict):
        issues.append(f"{label}.abstract_state: 缺失或非对象")
        return [], None
    variables = abstract.get("variables")
    initial = abstract.get("initial")
    if not isinstance(variables, list) or not variables:
        issues.append(f"{label}.abstract_state.variables: 非空数组")
        variables = []
    if not isinstance(initial, dict):
        issues.append(f"{label}.abstract_state.initial: 缺失或非对象")
        initial = None
    return variables, initial


def _check_slot_value(slot: Any, at: str, slots: List[str],
                      issues: List[str]) -> None:
    """槽位值面：非空字符串 + 不重复；None = 未占用槽位（放行）。"""
    if slot is None:
        return
    if not _nonempty(slot):
        issues.append(f"{at}.slot: 非空字符串")
    elif slot in slots:
        issues.append(f"{at}.slot: 槽位重复 {slot!r}")
    else:
        slots.append(slot)


def _check_variable(var: dict, at: str, names: List[str], slots: List[str],
                    issues: List[str]) -> None:
    """单个变量的 name/kind/item_kind/source/slot 面。"""
    name = var.get("name")
    kind = var.get("kind")
    source = var.get("source")
    slot = var.get("slot")
    item_kind = var.get("item_kind")
    if not _nonempty(name):
        issues.append(f"{at}.name: 非空字符串")
    else:
        if name in names:
            issues.append(f"{at}.name: 变量重名 {name!r}")
        names.append(name)
    if kind not in KINDS:
        issues.append(f"{at}.kind: 非法类型 {kind!r}")
    if kind == "array":
        if item_kind is not None and item_kind not in ITEM_KINDS:
            issues.append(f"{at}.item_kind: 非法元素类型 {item_kind!r}")
    elif item_kind is not None:
        issues.append(f"{at}.item_kind: 仅 kind=array 可用")
    if not _nonempty(source):
        issues.append(f"{at}.source: 非空字符串")
    _check_slot_value(slot, at, slots, issues)


def _variables(variables: list, label: str, issues: List[str]):
    """变量数组 → (names, slots, valid_vars)。"""
    names: List[str] = []
    slots: List[str] = []
    valid_vars: List[Dict[str, Any]] = []
    for idx, var in enumerate(variables):
        at = f"{label}.abstract_state.variables[{idx}]"
        if not isinstance(var, dict):
            issues.append(f"{at}: 非对象")
            continue
        _check_variable(var, at, names, slots, issues)
        valid_vars.append(var)
    return names, slots, valid_vars


def _check_initial_keys(initial: dict, valid_vars: list, label: str,
                        issues: List[str]) -> None:
    """initial 里出现、但变量表未声明的键。"""
    declared = [v.get("name") for v in valid_vars if isinstance(v.get("name"), str)]
    for key in sorted(initial):
        if key not in declared:
            issues.append(f"{label}.abstract_state.initial: 未声明变量 {key!r}")


def _check_initial_values(initial: dict, valid_vars: list, label: str,
                          issues: List[str]) -> None:
    """每个已声明变量都须有初始值，且值匹配其 kind。"""
    for var in valid_vars:
        name = var.get("name")
        if not isinstance(name, str):
            continue
        if name not in initial:
            issues.append(f"{label}.abstract_state.initial: 缺变量 {name!r} 的初始值")
            continue
        kind = var.get("kind")
        item_kind = var.get("item_kind")
        if kind in KINDS and not _matches(initial[name], kind, item_kind):
            issues.append(
                f"{label}.abstract_state.initial.{name}: 值 {initial[name]!r} "
                f"不匹配 kind={kind!r}"
            )


def _check_initial(initial: Any, valid_vars: list, label: str,
                   issues: List[str]) -> None:
    """initial 须为已声明变量的全集，且每个值匹配其 kind。"""
    if not isinstance(initial, dict):
        return
    _check_initial_keys(initial, valid_vars, label, issues)
    _check_initial_values(initial, valid_vars, label, issues)


def _transition_parts(wm: dict, label: str, issues: List[str]):
    """transition → (initial_phase, phases)。"""
    transition = wm.get("transition")
    if not isinstance(transition, dict):
        issues.append(f"{label}.transition: 缺失或非对象")
        return None, []
    initial_phase = transition.get("initial_phase")
    phases = transition.get("phases")
    if not _nonempty(initial_phase):
        issues.append(f"{label}.transition.initial_phase: 非空字符串")
        initial_phase = None
    if not isinstance(phases, list) or not phases:
        issues.append(f"{label}.transition.phases: 非空数组")
        phases = []
    return initial_phase, phases


def _check_phase(phase: dict, at: str, phase_names: List[str],
                 edges: Dict[str, str], issues: List[str]) -> None:
    """单个相位：phase/next/guard/writes 面；相位名非法即止（不建边）。"""
    pname = phase.get("phase")
    nxt = phase.get("next")
    guard = phase.get("guard")
    writes = phase.get("writes")
    if not _nonempty(pname):
        issues.append(f"{at}.phase: 非空字符串")
        return
    if pname in phase_names:
        issues.append(f"{at}.phase: 相位重名 {pname!r}")
    phase_names.append(pname)
    if not _nonempty(nxt):
        issues.append(f"{at}.next: 非空字符串")
    if not _nonempty(guard):
        issues.append(f"{at}.guard: 非空守卫说明")
    if not isinstance(writes, list) or any(
        not _nonempty(w) for w in writes
    ):
        issues.append(f"{at}.writes: 字符串数组（可为空）")
    if isinstance(pname, str) and isinstance(nxt, str):
        edges[pname] = nxt


def _phases(phases: list, label: str, issues: List[str]):
    """相位数组 → (phase_names, edges)。"""
    phase_names: List[str] = []
    edges: Dict[str, str] = {}
    for idx, phase in enumerate(phases):
        at = f"{label}.transition.phases[{idx}]"
        if not isinstance(phase, dict):
            issues.append(f"{at}: 非对象")
            continue
        _check_phase(phase, at, phase_names, edges, issues)
    return phase_names, edges


def _reachable_from(start: Any, edges: Dict[str, str]) -> set:
    """从 start 沿 edges 广度可达的相位集（含 start 自身）。"""
    seen = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop(0)
        nxt = edges.get(current)
        if nxt is not None and nxt not in seen:
            seen.add(nxt)
            frontier.append(nxt)
    return seen


def _check_reachability(initial_phase: Any, phase_names: List[str],
                        edges: Dict[str, str], label: str,
                        issues: List[str]) -> None:
    """initial_phase 须在册；edges 目标须在册；从 initial_phase 出发须可达全部相位。"""
    phase_set = set(phase_names)
    if initial_phase is not None and initial_phase not in phase_set:
        issues.append(
            f"{label}.transition.initial_phase: {initial_phase!r} 不在 phases 内"
        )
    for pname, nxt in edges.items():
        if nxt not in phase_set:
            issues.append(
                f"{label}.transition.phases[{pname!r}].next: {nxt!r} 无对应相位"
            )
    if initial_phase in phase_set and all(n in phase_set for n in edges.values()):
        unreachable = sorted(phase_set - _reachable_from(initial_phase, edges))
        if unreachable:
            issues.append(
                f"{label}.transition: 从 initial_phase 不可达的相位 {unreachable}"
            )


def _check_invariants(wm: dict, label: str, issues: List[str]) -> None:
    """invariants 须为非空字符串数组。"""
    invariants = wm.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        issues.append(f"{label}.invariants: 非空数组")
        return
    for idx, inv in enumerate(invariants):
        if not _nonempty(inv):
            issues.append(f"{label}.invariants[{idx}]: 非空字符串")


def _check_finite_sequence(field: Any, declared_kinds: Dict[str, Any], valid_vars: list,
                           at: str, issues: List[str]) -> None:
    """finite_sequence 只能用于 array 变量，且元素类型须为 string。"""
    if declared_kinds.get(field) != "array":
        issues.append(f"{at}.field: finite_sequence 只能用于 array 变量")
        return
    flow_spec = next((v for v in valid_vars if v.get("name") == field), {})
    if flow_spec.get("item_kind") not in (None, "string"):
        issues.append(f"{at}.field: finite_sequence 的 array 元素应为 string")


def _check_values(values: Any, kind: Any, at: str, issues: List[str]) -> None:
    """finite_phase / finite_sequence 的 values 须为非空字符串数组。"""
    if not isinstance(values, list) or not values or any(
        not _nonempty(v) for v in values
    ):
        issues.append(f"{at}.values: {kind} 需非空字符串数组")
