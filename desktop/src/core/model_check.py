"""T10.1 · world_model 有限状态模型检查（不依赖 TLA+ 工具链）。

对模块头 `machine_contract.world_model` 的**确定性抽象控制状态**做有限状态检查：

  1. 相位可达性：initial_phase 在册；每个声明的 phase 从 initial 可达；next 目标在册（无悬空相位）。
  2. 确定性：同一 phase 不得重复声明，且其后继唯一（同一 (state,tick) 唯一后继）。
  3. 不变式保持：模块 `checks` 的可判定子集——
       · `finite_phase`：所有可达相位值 ∈ 声明 values；
       · `finite_sequence`：相位轨迹域 values 覆盖所有可达相位；
       · `monotonic` 等**变量级**不变式：迁移只声明 writes 名、无更新表达式 ⇒ 控制状态图上
         **不可判定** → WARN 并写原因（不假装通过）；自然语言 invariants 同样 WARN。
  4. 无死锁/终态显式：可达的非终态相位至少一个后继；sink 相位须显式标注终态
       （phase 名或 guard 含 terminal/终态/终止）→ 否则 FAIL。
  5. 槽位绑定一致：变量 `slot` 必须在 `protocol/world_slots.json` 注册（kind 漂移 WARN）。

BFS 覆盖相位图（状态 = 相位节点，边 = 确定性 next）；`--max-states` 上限：BFS 发现状态数超限
即中止并返回 **undecided（exit 2）**，不输出 PASS（fail-closed）。

范围（诚实边界）：只有声明 `world_model` 的模块可检查；无 `world_model` 的模块（当前仓 247 件）
不可有限状态化，统计里如实列出。变量更新函数/guard 语义未在契约中形式化，故数据面不变式
（tick 单调等）不可判定，只做 WARN。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from core import json_doc

SCHEMA = "nf-model-check/1"
DEFAULT_MAX_STATES = 256
SLOTS_REL = "protocol/world_slots.json"
TERMINAL_MARKERS = ("terminal", "终态", "终止", "halt", "final")


def _root(root: Any) -> Path:
    return Path(root)


def load_slots(root: Any = ".") -> Dict[str, Dict[str, Any]]:
    path = _root(root) / SLOTS_REL
    if not path.is_file():
        raise ValueError("缺 %s（修复指引：恢复槽注册表；模型检查不做「读不到 = 通过」）"
                         % SLOTS_REL)
    data = json_doc.load(path, dict, what=SLOTS_REL)
    return data.get("slots") or {}


def _issue(rule: str, severity: str, subject: str, message: str,
           module: str, trace: Sequence[str] = (),
           evidence: Sequence[str] = (), fix: str = "") -> Dict[str, Any]:
    return {"rule": rule, "severity": severity, "subject": str(subject),
            "module": module, "message": message, "trace": list(trace),
            "evidence": list(evidence), "fix": fix}


def _terminal(phase: str, guard: str, writes: Sequence[str]) -> bool:
    blob = ("%s %s %s" % (phase, guard, " ".join(writes))).lower()
    return any(mark in blob for mark in TERMINAL_MARKERS)


def _ordered_phases(wm: Dict[str, Any]) -> List[Dict[str, Any]]:
    transition = wm.get("transition") if isinstance(wm.get("transition"), dict) else {}
    phases = transition.get("phases") if isinstance(transition.get("phases"), list) else []
    out = []
    for i, item in enumerate(phases):
        if isinstance(item, dict) and str(item.get("phase") or "").strip():
            out.append({"phase": str(item["phase"]), "next": str(item.get("next") or ""),
                        "guard": str(item.get("guard") or ""),
                        "writes": [str(x) for x in (item.get("writes") or [])],
                        "index": i})
    return out


def _bfs(initial: str, succ: Dict[str, List[str]], max_states: int
         ) -> Dict[str, Any]:
    """BFS over phase nodes → 可达集/父指针/深度；超 max_states 即标记 aborted。"""
    seen: Set[str] = set()
    parent: Dict[str, Optional[str]] = {}
    depth: Dict[str, int] = {}
    order: List[str] = []
    queue: List[str] = [initial]
    parent[initial] = None
    depth[initial] = 0
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        order.append(cur)
        if len(seen) > max_states:
            return {"aborted": True, "seen": seen, "parent": parent,
                    "depth": depth, "order": order}
        for nxt in succ.get(cur, []):
            if nxt not in parent:
                parent[nxt] = cur
                depth[nxt] = depth.get(cur, 0) + 1
                queue.append(nxt)
    return {"aborted": False, "seen": seen, "parent": parent,
            "depth": depth, "order": order}


def _path(parent: Dict[str, Optional[str]], target: str) -> List[str]:
    out: List[str] = []
    cur: Optional[str] = target
    guard = 0
    while cur is not None and guard < 10000:
        out.append(cur)
        cur = parent.get(cur)
        guard += 1
    return list(reversed(out))


def _slot_issues(wm: Dict[str, Any], slots: Dict[str, Dict[str, Any]],
                 module: str, evidence: Sequence[str]) -> Tuple[List[Dict[str, Any]], int]:
    issues: List[Dict[str, Any]] = []
    abstract = wm.get("abstract_state") if isinstance(wm.get("abstract_state"), dict) else {}
    variables = [v for v in (abstract.get("variables") or []) if isinstance(v, dict)]
    for var in variables:
        slot = str(var.get("slot") or "").strip()
        if not slot:
            continue
        spec = slots.get(slot)
        if not isinstance(spec, dict):
            issues.append(_issue(
                "slot_registration", "FAIL", slot,
                "变量 %r 引用未注册槽 %s（不在 %s）"
                % (var.get("name"), slot, SLOTS_REL), module,
                evidence=list(evidence) + [SLOTS_REL + ":4-46"],
                fix="在 protocol/world_slots.json 注册该槽，或改绑已注册槽"))
            continue
        if str(spec.get("kind") or "") != str(var.get("kind") or ""):
            issues.append(_issue(
                "slot_kind_drift", "WARN", slot,
                "槽 kind=%r ≠ 变量 kind=%r（结构校验已另判，模型检查按 WARN 记账）"
                % (spec.get("kind"), var.get("kind")), module,
                evidence=list(evidence) + [SLOTS_REL + ":4-46"]))
        if spec.get("owner") and str(spec.get("owner")) != str(var.get("source") or ""):
            issues.append(_issue(
                "slot_owner_drift", "WARN", slot,
                "槽 owner=%r ≠ 变量 source=%r" % (spec.get("owner"), var.get("source")),
                module, evidence=list(evidence) + [SLOTS_REL + ":4-46"]))
    return issues, len(variables)


def check_world_model(module: str, wm: Dict[str, Any],
                      slots: Dict[str, Dict[str, Any]],
                      max_states: int = DEFAULT_MAX_STATES,
                      evidence: Sequence[str] = ()) -> Dict[str, Any]:
    """单个 world_model 的有限状态检查 → {module, verdict, issues, stats, undecided}。"""
    issues: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"phases_declared": 0, "phases_reachable": 0,
                             "states": 0, "edges": 0, "depth": 0,
                             "terminals": [], "variables": 0,
                             "max_states": int(max_states)}
    phase_rows = _ordered_phases(wm)
    stats["phases_declared"] = len({p["phase"] for p in phase_rows})
    names = [p["phase"] for p in phase_rows]
    transition = wm.get("transition") if isinstance(wm.get("transition"), dict) else {}
    initial = str(transition.get("initial_phase") or "").strip()

    # 槽位面（先判；即便图非法也要把绑定问题报出）
    slot_issues, n_vars = _slot_issues(wm, slots, module, evidence)
    issues += slot_issues
    stats["variables"] = n_vars

    if not phase_rows:
        return {"module": module, "verdict": "fail",
                "issues": issues + [_issue("reachability", "FAIL", module,
                                           "world_model.transition.phases 为空，无可检查相位图",
                                           module, evidence=list(evidence),
                                           fix="补 transition.phases")],
                "stats": stats, "undecided": False}
    if not initial or initial not in names:
        issues.append(_issue("reachability", "FAIL", initial or "<缺 initial_phase>",
                             "initial_phase=%r 不在 phases 内" % initial, module,
                             evidence=list(evidence),
                             fix="initial_phase 须为声明相位之一"))

    # 确定性：重复相位声明 = 同一相位多后继（非确定）
    succ: Dict[str, List[str]] = {}
    seen_decl: Set[str] = set()
    for row in phase_rows:
        p, nxt = row["phase"], row["next"]
        if p in seen_decl:
            issues.append(_issue("determinism", "FAIL", p,
                                 "相位 %r 重复声明 → 同一 (state,tick) 存在多个后继（非确定）" % p,
                                 module, trace=[p], evidence=list(evidence),
                                 fix="每个相位只声明一条 next（非确定分支须建模为显式状态）"))
        seen_decl.add(p)
        if not nxt:
            succ.setdefault(p, [])
            continue
        succ.setdefault(p, [])
        if nxt not in succ[p]:
            succ[p].append(nxt)

    # 悬空相位 + 可达性
    for p, nxts in succ.items():
        for nxt in nxts:
            if nxt not in names:
                issues.append(_issue("reachability", "FAIL", "%s→%s" % (p, nxt),
                                     "next 目标 %r 无对应相位声明（悬空相位）" % nxt,
                                     module, trace=[p, nxt], evidence=list(evidence),
                                     fix="补声明该相位或修正 next"))
    bfs = _bfs(initial, succ, max_states) if initial in names else {
        "aborted": False, "seen": set(), "parent": {}, "depth": {}, "order": []}
    if bfs["aborted"]:
        return {"module": module, "verdict": "undecided", "issues": issues,
                "stats": stats, "undecided": True,
                "reason": "state_limit：BFS 发现状态数超过 --max-states=%d（不假装通过）"
                          % max_states}
    reachable = bfs["seen"]
    stats.update({"phases_reachable": len(reachable), "states": len(reachable),
                  "edges": sum(len([n for n in succ.get(p, []) if n in reachable])
                               for p in reachable),
                  "depth": max(bfs["depth"].values()) if bfs["depth"] else 0})
    for p in sorted(set(names) - reachable):
        issues.append(_issue("reachability", "FAIL", p,
                             "相位 %r 从 initial_phase=%r 不可达（悬空相位）" % (p, initial),
                             module, trace=[initial, "…", p], evidence=list(evidence),
                             fix="从可达相位接入，或删除该相位"))

    # 死锁：可达相位无后继，须显式终态
    row_by_phase = {r["phase"]: r for r in phase_rows}
    for p in sorted(reachable):
        if succ.get(p):
            continue
        row = row_by_phase.get(p, {})
        if _terminal(p, row.get("guard", ""), row.get("writes", [])):
            stats["terminals"].append(p)
        else:
            issues.append(_issue("deadlock", "FAIL", p,
                                 "相位 %r 无后继且未显式声明终态（死锁）" % p, module,
                                 trace=_path(bfs["parent"], p), evidence=list(evidence),
                                 fix="补 next，或在 phase/guard 显式标注终态（terminal/终态）"))

    # 不变式（checks 可判定子集）
    abstract = wm.get("abstract_state") if isinstance(wm.get("abstract_state"), dict) else {}
    initial_state = abstract.get("initial") if isinstance(abstract.get("initial"), dict) else {}
    checks = wm.get("checks") if isinstance(wm.get("checks"), list) else []
    phase_vars = {str(v.get("name")) for v in (abstract.get("variables") or [])
                  if isinstance(v, dict) and str(v.get("slot") or "") == "data_bus.round.phase"}
    phase_vars.add("phase")
    for chk in checks:
        if not isinstance(chk, dict):
            continue
        kind, field = str(chk.get("kind") or ""), str(chk.get("field") or "")
        values = [str(x) for x in (chk.get("values") or [])]
        if kind == "finite_phase":
            if not values:
                continue
            for p in sorted(reachable - set(values)):
                issues.append(_issue("invariant", "FAIL", "%s=%s" % (field, p),
                                     "可达相位 %r 不在 finite_phase 声明域 %s（不变式破坏）"
                                     % (p, values), module,
                                     trace=_path(bfs["parent"], p), evidence=list(evidence),
                                     fix="扩 values 或删/改该相位迁移"))
            init_value = str(initial_state.get(field) or "")
            if init_value and init_value not in values:
                issues.append(_issue("invariant", "FAIL", "%s=%s" % (field, init_value),
                                     "初始状态 %s=%r 不在 finite_phase 声明域" % (field, init_value),
                                     module, trace=[initial], evidence=list(evidence),
                                     fix="修正 abstract_state.initial 或 values"))
            if field in phase_vars and initial and str(initial_state.get(field) or "") != initial:
                issues.append(_issue("invariant", "FAIL", field,
                                     "abstract_state.initial.%s=%r ≠ transition.initial_phase=%r"
                                     % (field, initial_state.get(field), initial), module,
                                     trace=[initial], evidence=list(evidence),
                                     fix="对齐初始相位与 initial 变量值"))
        elif kind == "finite_sequence":
            if not values or not field:
                continue
            bad = sorted(reachable - set(values))
            if bad:
                issues.append(_issue("invariant", "FAIL", field,
                                     "相位轨迹域 values 未覆盖可达相位 %s（不变式破坏）" % bad,
                                     module, trace=bad[:3], evidence=list(evidence),
                                     fix="把可达相位补进 finite_sequence.values"))
        elif kind == "monotonic":
            issues.append(_issue("invariant", "WARN", field,
                                 "monotonic(%s) 在控制状态图上**不可判定**：迁移只声明 writes 名、"
                                 "无更新表达式；未判 PASS" % field, module,
                                 evidence=list(evidence) + ["04_模块库/通用类/M50_调度器.md"],
                                 fix="如需判定，须在契约补变量更新语义（本轮不改 world_model 契约）"))
    prose = wm.get("invariants") if isinstance(wm.get("invariants"), list) else []
    if prose:
        issues.append(_issue("invariant", "WARN", "invariants",
                             "自然语言不变式 %d 条未形式化（不可机判，不判 PASS）" % len(prose),
                             module, evidence=list(evidence),
                             fix="可判定子集请用 checks（finite_phase/finite_sequence）声明"))

    fails = [i for i in issues if i["severity"] == "FAIL"]
    warns = [i for i in issues if i["severity"] == "WARN"]
    verdict = "fail" if fails else ("warn" if warns else "pass")
    return {"module": module, "verdict": verdict, "issues": issues,
            "stats": stats, "undecided": False,
            "fails": len(fails), "warns": len(warns)}


def _module_world_models(root: Path) -> Tuple[List[Tuple[str, Dict[str, Any]]], int, List[str]]:
    """扫描模块头 → ([(module, world_model)], 模块总数, 无 world_model 的模块列表)。"""
    from core import conformance_scan as csc

    found: List[Tuple[str, Dict[str, Any]]] = []
    docs = csc._module_docs(str(root))
    missing: List[str] = []
    for doc in docs:
        rel = Path(doc).relative_to(root).as_posix()
        try:
            text = Path(doc).read_text(encoding="utf-8")
        except OSError:
            missing.append(rel)
            continue
        mc = csc._fence_yaml(text, "machine_contract").get("machine_contract")
        wm = mc.get("world_model") if isinstance(mc, dict) else None
        if isinstance(wm, dict):
            found.append((rel, wm))
        else:
            missing.append(rel)
    return found, len(docs), missing


def run(root: Any = ".", max_states: int = DEFAULT_MAX_STATES,
        as_json: bool = False) -> int:
    """CLI 内核：全部 world_model 有限状态检查。
    PASS/WARN → 0；任一 FAIL → 1；超状态上限/无模型/真源不可读 → 2（不假装通过）。
    """
    root_p = _root(root)
    if max_states <= 0:
        print("  ✗ --max-states 须为正整数（实为 %r）" % max_states, file=sys.stderr)
        return 2
    try:
        slots = load_slots(root_p)
        models, total_docs, no_model = _module_world_models(root_p)
    except (OSError, ValueError) as exc:
        print("  ✗ 模型检查不可判定：%s（修复指引：核对 world_slots 与模块头；"
              "本命令不做「读不到 = 通过」）" % exc, file=sys.stderr)
        return 2
    if not models:
        print("  ✗ 无可检查模型：0 个模块声明 world_model（%d 份模块头已扫描）"
              "—— 不可判定，不判 PASS" % total_docs, file=sys.stderr)
        return 2
    results = []
    undecided = []
    for rel, wm in models:
        mid = rel.split("/")[-1].split("_")[0]
        res = check_world_model(mid, wm, slots, max_states=max_states, evidence=[rel])
        results.append(res)
        if res.get("undecided"):
            undecided.append(res)
    fails = [i for r in results for i in r["issues"] if i["severity"] == "FAIL"]
    warns = [i for r in results for i in r["issues"] if i["severity"] == "WARN"]
    if undecided:
        verdict = "undecided"
    elif fails:
        verdict = "fail"
    elif warns:
        verdict = "warn"
    else:
        verdict = "pass"
    report = {
        "schema": SCHEMA, "verdict": verdict,
        "issues": [i for r in results for i in r["issues"]],
        "modules": results,
        "stats": {
            "modules_scanned": total_docs,
            "modules_with_world_model": len(models),
            "modules_without_world_model": len(no_model),
            "states": sum(r["stats"].get("states", 0) for r in results),
            "edges": sum(r["stats"].get("edges", 0) for r in results),
            "depth": max([r["stats"].get("depth", 0) for r in results] or [0]),
            "max_states": max_states,
            "undecided_modules": [r["module"] for r in undecided],
            "fail": len(fails), "warn": len(warns),
        },
        "scope": {
            "covered": [r["module"] for r in results],
            "not_finitely_modelable_count": len(no_model),
            "not_finitely_modelable_sample": no_model[:12],
            "reason": "无 machine_contract.world_model 的模块不可有限状态化（仅结构/语义扫描覆盖）",
        },
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf spec modelcheck（world_model 有限状态检查：相位图 BFS）==")
        print("  判定：%s（FAIL %d · WARN %d · 状态 %d · 边 %d · 深度 %d · 上限 %d）"
              % (verdict.upper(), len(fails), len(warns), report["stats"]["states"],
                 report["stats"]["edges"], report["stats"]["depth"], max_states))
        for r in results:
            s = r["stats"]
            print("  · %s：%s（相位 %d/%d 可达 · 终态 %s）"
                  % (r["module"], r["verdict"].upper(), s["phases_reachable"],
                     s["phases_declared"], "、".join(s["terminals"]) or "—"))
            for i in r["issues"]:
                print("    [%s] %s/%s %s：%s" % (i["severity"], i["rule"], i["subject"],
                                                i["module"], i["message"]))
                if i["trace"]:
                    print("           trace：%s" % " → ".join(i["trace"]))
        print("  覆盖：%d 模块声明 world_model；%d 模块无 world_model（不可有限状态化）"
              % (report["stats"]["modules_with_world_model"],
                 report["stats"]["modules_without_world_model"]))
        if verdict == "undecided":
            print("  [UNDECIDED] 超状态上限，未完成穷举 —— 不判 PASS（exit 2）")
    if verdict == "undecided":
        return 2
    return 1 if verdict == "fail" else 0
