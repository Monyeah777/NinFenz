"""core.world_model 私有实现分片 3/3（对外只经 core.world_model 门面导入）：WorldModelRuntime 等"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ._part1 import _get_slot, _matches, _nonempty, _set_slot, load_slots
from ._part2 import (
    WorldModelViolation,
    build_graph,
    initial_state,
    trace_digest,
    validate_contract,
)


class WorldModelRuntime:
    """可执行 world_model：状态校验 + 相位前进 + 确定性重放。"""

    def __init__(self, contract: Dict[str, Any]):
        issues = validate_contract(contract)
        if issues:
            raise WorldModelViolation(issues)
        self.contract = contract
        self.graph = build_graph(contract)
        abstract = contract.get("abstract_state") or {}
        self.variables = {
            item["name"]: item
            for item in (abstract.get("variables") or [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        self.initial = initial_state(contract)

    def validate_state(self, state: Any,
                       previous: Dict[str, Any] | None = None) -> List[str]:
        """校验运行态：变量封闭、类型匹配、结构化 checks 全部成立。"""
        issues: List[str] = []
        if not isinstance(state, dict):
            return ["state 非对象"]
        declared = set(self.variables)
        unknown = sorted(set(state) - declared)
        missing = sorted(declared - set(state))
        if unknown:
            issues.append("state 含未声明变量 %s" % unknown)
        if missing:
            issues.append("state 缺声明变量 %s" % missing)
        for name, spec in self.variables.items():
            if name not in state:
                continue
            if not _matches(state[name], spec.get("kind") or "", spec.get("item_kind")):
                issues.append(
                    "state.%s 类型不匹配 kind=%r item_kind=%r"
                    % (name, spec.get("kind"), spec.get("item_kind"))
                )
        for check in self.contract.get("checks") or []:
            kind = check.get("kind")
            field = check.get("field")
            if kind == "finite_phase":
                values = set(check.get("values") or [])
                if field in state and state.get(field) not in values:
                    issues.append(
                        "check finite_phase：%s=%r 不在 %s"
                        % (field, state.get(field), sorted(values))
                    )
            elif kind == "monotonic":
                if field in state and previous is not None and field in previous:
                    if not _matches(state[field], "number") or not _matches(
                        previous[field], "number"
                    ):
                        issues.append("check monotonic：%s 非数值" % field)
                    elif state[field] < previous[field]:
                        issues.append(
                            "check monotonic：%s %s < 上一状态 %s"
                            % (field, state[field], previous[field])
                        )
            elif kind == "finite_sequence":
                values = set(check.get("values") or [])
                seq = state.get(field)
                if not isinstance(seq, list):
                    issues.append(
                        "check finite_sequence：%s 应为 array" % field
                    )
                else:
                    bad = [v for v in seq if v not in values]
                    if bad:
                        issues.append(
                            "check finite_sequence：%s 含非法相位 %s"
                            % (field, bad)
                        )
        return issues

    def extract_state(self, concrete: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """从 M00 具体 JSON 状态按 slot 路径抽取 world_model 抽象状态。"""
        issues: List[str] = []
        state: Dict[str, Any] = {}
        for name, spec in self.variables.items():
            slot = spec.get("slot")
            if not _nonempty(slot):
                issues.append("变量 %s 缺 slot，无法从具体状态抽取" % name)
                continue
            try:
                state[name] = _get_slot(concrete, slot)
            except KeyError:
                issues.append("slot 路径缺失：%s（%s）" % (slot, name))
        return state, issues

    def validate_concrete(self, concrete: Dict[str, Any],
                          previous_concrete: Dict[str, Any] | None = None) -> List[str]:
        """先按 slot 抽取抽象状态，再校验状态类型与 checks。"""
        state, issues = self.extract_state(concrete)
        if issues:
            return issues
        previous = None
        if previous_concrete is not None:
            previous, prev_issues = self.extract_state(previous_concrete)
            if prev_issues:
                return prev_issues
        return self.validate_state(state, previous)

    def advance(self, state: Dict[str, Any],
                previous: Dict[str, Any] | None = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """前进一步；先验状态，再按相位图更新 phase 与 phase_trace（若声明）。"""
        issues = self.validate_state(state, previous)
        if issues:
            raise WorldModelViolation(issues)
        phase_from = state.get("phase")
        if phase_from not in self.graph["phases"]:
            raise WorldModelViolation(["当前相位未声明：%r" % phase_from])
        import copy

        before = copy.deepcopy(state)
        after = copy.deepcopy(state)
        transition = self.graph["phases"][phase_from]
        after["phase"] = transition["next"]
        phase_trace = self.variables.get("phase_trace")
        if phase_trace and phase_trace.get("kind") == "array":
            chain = list(state.get("phase_trace") or [])
            chain.append(phase_from)
            after["phase_trace"] = chain
        trace = {
            "phase_from": phase_from,
            "phase_to": transition["next"],
            "guard": transition.get("guard", ""),
            "writes": list(transition.get("writes") or []),
            "state_before": before,
            "state_after": after,
        }
        return after, trace

    def replay(self, state: Dict[str, Any] | None = None,
               max_steps: int = 100) -> Dict[str, Any]:
        """从 initial 重放相位迁移，直到回到已见相位或超限。"""
        import copy

        current = copy.deepcopy(state) if state is not None else copy.deepcopy(self.initial)
        steps: List[Dict[str, Any]] = []
        seen: set = set()
        last: Dict[str, Any] | None = None
        reason = "limit"
        repeat = None
        for _ in range(max(1, max_steps)):
            phase = current.get("phase")
            if phase in seen:
                reason = "cycle"
                repeat = phase
                break
            seen.add(phase)
            next_state, trace = self.advance(current, last)
            trace["step"] = len(steps) + 1
            steps.append(trace)
            last = current
            current = next_state
        result = {
            "reason": reason,
            "repeat": repeat,
            "steps": steps,
            "final_state": current,
        }
        result["digest"] = trace_digest(result)
        return result

    def advance_concrete(self, concrete: Dict[str, Any],
                         previous_concrete: Dict[str, Any] | None = None
                         ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """从具体 M00 状态前进一步；校验、抽取、推进并写回 slot。"""
        state, extract_issues = self.extract_state(concrete)
        if extract_issues:
            raise WorldModelViolation(extract_issues)
        previous = None
        if previous_concrete is not None:
            previous, prev_issues = self.extract_state(previous_concrete)
            if prev_issues:
                raise WorldModelViolation(prev_issues)
        abstract_next, trace = self.advance(state, previous)
        concrete_next = dict(concrete)
        for name, spec in self.variables.items():
            slot = spec.get("slot")
            if isinstance(slot, str) and name in abstract_next:
                concrete_next = _set_slot(concrete_next, slot, abstract_next[name])
        trace["concrete_before"] = concrete
        trace["concrete_after"] = concrete_next
        return concrete_next, trace

    def replay_concrete(self, concrete: Dict[str, Any] | None = None,
                        max_steps: int = 100) -> Dict[str, Any]:
        """从具体 M00 状态重放，直到回到已见相位或超限。"""
        import copy

        if concrete is None:
            current: Dict[str, Any] = {}
            for name, spec in self.variables.items():
                slot = spec.get("slot")
                if isinstance(slot, str):
                    current = _set_slot(current, slot, self.initial.get(name))
        else:
            current = copy.deepcopy(concrete)
        steps: List[Dict[str, Any]] = []
        seen: set = set()
        last: Dict[str, Any] | None = None
        reason = "limit"
        repeat = None
        for _ in range(max(1, max_steps)):
            abstract, extract_issues = self.extract_state(current)
            if extract_issues:
                raise WorldModelViolation(extract_issues)
            phase = abstract.get("phase")
            if phase in seen:
                reason = "cycle"
                repeat = phase
                break
            seen.add(phase)
            previous_current = current
            current, trace = self.advance_concrete(current, last)
            trace["step"] = len(steps) + 1
            steps.append(trace)
            last = previous_current
        result = {
            "reason": reason,
            "repeat": repeat,
            "steps": steps,
            "final_state": current,
        }
        result["digest"] = trace_digest(result)
        return result


def advance_phase(wm: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """按相位图前进一步；不解释 guard，只执行已声明的确定性 next。"""
    graph = build_graph(wm)
    phase = state.get("phase")
    if phase not in graph["phases"]:
        raise ValueError("当前相位未在 world_model.transition.phases 声明: %r" % phase)
    nxt = graph["phases"][phase]["next"]
    out = dict(state)
    out["phase"] = nxt
    return out


def phase_sequence(wm: Dict[str, Any], limit: int = 100) -> Tuple[List[str], str, str | None]:
    """从 initial_phase 重放相位序列；返回 (序列, 终止原因, 重复相位)。"""
    graph = build_graph(wm)
    current = graph["initial_phase"]
    if current is None:
        return [], "dangling", None
    sequence: List[str] = []
    seen = set()
    for _ in range(max(1, limit)):
        if current in seen:
            return sequence, "cycle", current
        sequence.append(current)
        seen.add(current)
        nxt = graph["phases"].get(current, {}).get("next")
        if nxt is None:
            return sequence, "dangling", current
        current = nxt
    return sequence, "limit", current


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _slot_count(var_list: Any) -> int:
    return sum(1 for v in var_list if isinstance(v, dict) and v.get("slot"))


def _model_entry(wm: Any, mc: Dict[str, Any], rel: str):
    """world_model 块 → (models 条目, 计数增量)；非对象按空块处理（与旧行为一致）。"""
    if not isinstance(wm, dict):
        wm = {}
    abstract = _as_dict(wm.get("abstract_state"))
    transition = _as_dict(wm.get("transition"))
    var_list = abstract.get("variables") or []
    invs = wm.get("invariants")
    check_list = wm.get("checks")
    inv_list = invs if isinstance(invs, list) else []
    checks = check_list if isinstance(check_list, list) else []
    phases = transition.get("phases") or []
    slots = _slot_count(var_list)
    counts = {"variables": len(var_list), "phases": len(phases),
              "invariants": len(inv_list), "checks": len(checks), "slots": slots}
    model = {"module": (mc.get("id") or rel), "source": rel,
             "initial_phase": transition.get("initial_phase"),
             "phases": len(phases), "invariants": len(inv_list),
             "checks": len(checks), "slots": slots}
    return model, counts


def _scan_doc(r: Path, doc: str, slot_registry: Dict[str, Any], csc):
    """单模块文档 → (issues, model|None, 计数增量|None)。"""
    rel = os.path.relpath(doc, str(r)).replace(os.sep, "/")
    try:
        text = csc.read_text_cached(doc)
    except Exception as exc:
        return [f"{rel}: 读取失败 {exc}"], None, None
    parsed = csc._fence_yaml(text, "machine_contract")
    mc = parsed.get("machine_contract") if isinstance(parsed, dict) else None
    if not isinstance(mc, dict) or "world_model" not in mc:
        return [], None, None
    wm = mc["world_model"]
    issues = list(validate_contract(wm, f"{rel}.world_model", slot_registry=slot_registry))
    model, counts = _model_entry(wm, mc, rel)
    return issues, model, counts


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """扫描全部模块文档中的 world_model 契约。"""
    r = Path(root)
    from core import conformance_scan as csc

    issues: List[str] = []
    slot_registry = load_slots(str(r))
    if not slot_registry:
        issues.append("protocol/world_slots.json 缺失或 slots 为空")
    stats: Dict[str, Any] = {"modules": 0, "variables": 0, "phases": 0, "invariants": 0,
                             "checks": 0, "slots": 0}
    models: List[Dict[str, Any]] = []
    for doc in csc._module_docs(str(r)):
        doc_issues, model, counts = _scan_doc(r, doc, slot_registry, csc)
        issues.extend(doc_issues)
        if model is None:
            continue
        models.append(model)
        for key, value in counts.items():
            stats[key] += value
    stats["modules"] = len(models)
    stats["slot_registry"] = len(slot_registry)
    stats["models"] = models
    return issues, stats
