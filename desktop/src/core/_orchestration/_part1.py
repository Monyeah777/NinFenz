"""core.orchestration 私有实现分片 1/2（对外只经 core.orchestration 门面导入）：SCHEMA 等"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import json_doc

SCHEMA = "nf-orchestration/1"


DRIVER_REL = "protocol/driver.json"


_STEP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


_REF = re.compile(r"^\$([a-z][a-z0-9_-]*)(?:\.([A-Za-z0-9_.\[\]]*))?$")


_TYPES = {"string": str, "boolean": bool, "object": dict, "array": list}


#: 计划格式的**机器面自述**（随 catalog 一起交回给 agent：第一跳就知道计划怎么写）。
PLAN_GUIDE = {
    "schema": SCHEMA,
    "workflow": "driver.json 在册的工作流名（决定本计划可用的工具集）",
    "steps": "非空列表；每步为对象 {id, tool, args, needs?, expects?, purpose?}",
    "id": "小写字母起头、[a-z0-9_-]、≤64 字符，步内唯一（依赖与证据的锚）",
    "tool": "必须在该工作流的映射集内、且在运行时工具面在册",
    "args": "须满足该工具 inputSchema（必填 / 类型 / 封闭性）；以 $ 起头的字符串是引用"
            "（$<步 id>.<字段>），写法非法即判红、不静默当字面量",
    "needs": "显式依赖；$步.字段 引用必须落在 needs 的传递闭包内（隐式依赖判红）",
    "expects": "该步必须产出的字段；派发时即验，缺证据即停（fail-closed）",
}


def workflow_tools(root: str = ".") -> Dict[str, List[str]]:
    """`protocol/driver.json` 的工作流 → 允许的工具集（机器面映射真源）。"""
    p = Path(root) / DRIVER_REL
    if not p.is_file():
        return {}
    try:
        doc = json_doc.load(p, dict, what=str(p))
    except ValueError:
        return {}          # 坏件由 driver.scan 报出；同一规则不在两处各判一遍
    return {str(k): [str(t) for t in (v.get("mcp_tools") or [])]
            for k, v in (doc.get("workflows") or {}).items()}


def catalog(root: str = ".", tools: Optional[Dict[str, Dict[str, Any]]] = None
            ) -> Dict[str, Any]:
    """能力目录：工具面（说明 / 必填 / 属性 / 封闭性）+ 工作流面（允许工具集）。

    `tools` = 运行时工具面 `{name: tool_def}`，**由调用方注入**——本模块是叶子，不 import
    工具面（否则会给 `mcp_runtime` 多记一个依赖方，压低它的稳定度、造出 SDP 违例；见模块头）。
    """
    out: Dict[str, Any] = {"schema": SCHEMA, "tools": {}, "workflows": {}}
    for name, t in (tools or {}).items():
        sch = t.get("inputSchema") or {}
        out["tools"][name] = {
            "description": str(t.get("description") or ""),
            "required": [str(k) for k in (sch.get("required") or [])],
            "properties": dict(sch.get("properties") or {}),
            "additional_properties": bool(sch.get("additionalProperties", True)),
        }
    for name, wf_tools in workflow_tools(root).items():
        out["workflows"][name] = {"tools": wf_tools}
    out["plan"] = dict(PLAN_GUIDE)
    return out


def _closure(sid: str, needs: Dict[str, List[str]]) -> List[str]:
    """`sid` 的 `needs` 传递闭包（防环由调用方的拓扑判据负责，这里只做有限展开）。"""
    seen, stack = set(), list(needs.get(sid) or [])
    while stack:
        cur = stack.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(needs.get(cur) or [])
    return sorted(seen)


def _type_issue(value: Any, spec: Dict[str, Any]) -> str:
    """值是否满足 `inputSchema` 的类型声明 → 空串 = 合规。布尔不当整数（Python 的 bool ⊂ int）。"""
    want = str((spec or {}).get("type") or "")
    if want == "integer":
        return "" if (isinstance(value, int) and not isinstance(value, bool)) else "integer"
    if want == "number":
        return "" if (isinstance(value, (int, float)) and not isinstance(value, bool)) else "number"
    if want in _TYPES:
        return "" if isinstance(value, _TYPES[want]) else want
    return ""


def _args_issues(sid: str, args: Dict[str, Any], spec: Dict[str, Any],
                 ids: List[str], closure: List[str]) -> List[str]:
    """一步的 `args` 判据：必填 / 类型 / 封闭性 / 引用是**显式**依赖。"""
    issues: List[str] = []
    for key in (spec.get("required") or []):
        if key not in args:
            issues.append("步 %s 缺必填参数 %s（修复指引：见该工具 inputSchema.required）" % (sid,
 key))
    props = spec.get("properties") or {}
    for key, val in args.items():
        if key not in props:
            if not spec.get("additional_properties", True):
                issues.append("步 %s 传了未声明参数 %s（该工具 inputSchema 封闭；"
                              "修复指引：删掉或改用已声明参数）" % (sid, key))
            continue
        bad = _type_issue(val, props[key])
        if bad:
            issues.append("步 %s 的参数 %s 类型应为 %s（当前 %s）"
                          % (sid, key, bad, type(val).__name__))
    for key, val in args.items():
        if not (isinstance(val, str) and val.startswith("$")):
            continue
        m = _REF.match(val)
        if not m:
            issues.append("步 %s 的参数 %s 引用写法非法：%r（修复指引：$<步 id>.<字段>，步 id "
                          "小写字母起头；以 $ 起头的字符串一律当引用，不静默当字面量）"
                          % (sid, key, val))
            continue
        ref_id = m.group(1)
        if ref_id not in ids:
            issues.append("步 %s 的引用 $%s 指向不存在的步（修复指引：改用已声明的步 id）"
                          % (sid, ref_id))
        elif ref_id != sid and ref_id not in closure:
            issues.append("步 %s 的引用 $%s 是**隐式依赖**（修复指引：把 %s 写进本步 needs——"
                          "顺序必须显式，否则同一份计划两次执行可不同序）" % (sid, ref_id, ref_id))
    return issues


def _topo(ids: List[str], needs: Dict[str, List[str]]) -> List[str]:
    """确定性拓扑序：就绪集按（声明序, id）决胜——同输入同输出，不看字典哈希。"""
    index = {sid: i for i, sid in enumerate(ids)}
    indeg = {sid: 0 for sid in ids}
    kids: Dict[str, List[str]] = {sid: [] for sid in ids}
    for sid in ids:
        for dep in needs.get(sid) or []:
            if dep not in indeg or dep == sid:
                continue
            indeg[sid] += 1
            kids[dep].append(sid)
    ready = [s for s in ids if indeg[s] == 0]
    order: List[str] = []
    while ready:
        ready.sort(key=lambda s: (index[s], s))
        cur = ready.pop(0)
        order.append(cur)
        for kid in kids[cur]:
            indeg[kid] -= 1
            if indeg[kid] == 0:
                ready.append(kid)
    return order


def _tool_issues(sid: str, tool: str, cat: Dict[str, Any], wf: str) -> List[str]:
    """一步的工具面判据：非空 / 在运行时在册 / 在本工作流的映射集内。"""
    if not tool:
        return ["步 %s 缺 tool（修复指引：填工具面名字）" % sid]
    if tool not in cat["tools"]:
        return ["步 %s 的工具不在运行时工具面：%s（修复指引：改用 %s 在册工具）"
                % (sid, tool, DRIVER_REL)]
    allowed = list((cat["workflows"].get(wf) or {}).get("tools") or [])
    if wf in cat["workflows"] and tool not in allowed:
        return ["步 %s 的工具 %s 不在工作流 %s 的映射集内（允许：%s）"
                % (sid, tool, wf, "、".join(allowed) or "无")]
    return []


def _step_ids_issues(raw: List[Any], cat: Dict[str, Any], wf: str):
    """steps 的结构 + 工具面判据 → (issues, steps, ids, needs)；不可用的步被丢弃并记账。"""
    issues: List[str] = []
    steps: Dict[str, Dict[str, Any]] = {}
    ids: List[str] = []
    needs: Dict[str, List[str]] = {}
    for i, step in enumerate(raw, 1):
        if not isinstance(step, dict):
            issues.append("第 %d 步不是对象（修复指引：id / tool / args 三字段的对象）" % i)
            continue
        sid = str(step.get("id") or "")
        if not _STEP_ID.match(sid):
            issues.append("第 %d 步的 id 非法：%r（修复指引：小写字母起头，[a-z0-9_-]，≤64 字符）"
                          % (i, sid))
            continue
        if sid in steps:
            issues.append("步 id 重复：%s（修复指引：每步唯一——它是依赖与证据的锚）" % sid)
            continue
        tool = str(step.get("tool") or "")
        issues += _tool_issues(sid, tool, cat, wf)
        args = step.get("args") or {}
        if not isinstance(args, dict):
            issues.append("步 %s 的 args 须为对象" % sid)
            args = {}
        need = step.get("needs") or []
        if not isinstance(need, list):
            issues.append("步 %s 的 needs 须为列表" % sid)
            need = []
        exp = step.get("expects") or []
        if not isinstance(exp, list) or any(not str(x).strip() for x in exp):
            issues.append("步 %s 的 expects 须为非空字符串列表（修复指引：写清该步必须产出的字段，"
                          "派发时即按此验收）" % sid)
            exp = []
        steps[sid] = {"tool": tool, "args": args, "expects": [str(x) for x in exp],
                      "purpose": str(step.get("purpose") or "")}
        needs[sid] = [str(n) for n in need]
        ids.append(sid)
    return issues, steps, ids, needs


def _needs_issues(ids: List[str], steps: Dict[str, Any],
                  needs: Dict[str, List[str]]) -> List[str]:
    """`needs` 的引用判据：不得自依赖、必须指向在场的步。"""
    issues: List[str] = []
    for sid in ids:
        for dep in needs[sid]:
            if dep == sid:
                issues.append("步 %s 依赖自己（修复指引：删掉该 need）" % sid)
            elif dep not in steps:
                issues.append("步 %s 的 need 指向不存在的步：%s（修复指引：改用已声明的步 id）"
                              % (sid, dep))
    return issues


def compile_plan(root: str = ".", plan: Optional[Dict[str, Any]] = None,
                 tools: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """校验并编译编排计划 → `{"ok", "order", "issues", "steps", "workflow"}`（只读）。"""
    doc: Dict[str, Any] = plan if isinstance(plan, dict) else {}
    issues: List[str] = []
    if not doc:
        return {"schema": SCHEMA, "ok": False, "workflow": "", "order": [], "steps": {},
                "issues": ["计划为空（修复指引：给 {'schema': '%s', 'workflow': …, "
                           "'steps': [...]}）" % SCHEMA]}
    if str(doc.get("schema") or "") != SCHEMA:
        issues.append("计划 schema 须为 %s（当前 %r）" % (SCHEMA, doc.get("schema")))
    cat = catalog(root, tools)
    wf = str(doc.get("workflow") or "")
    if not wf:
        issues.append("计划缺 workflow（修复指引：填 %s 在册的工作流名）" % DRIVER_REL)
    elif wf not in cat["workflows"]:
        issues.append("工作流未在 %s 在册：%s（在册：%s）"
                      % (DRIVER_REL, wf, "、".join(sorted(cat["workflows"])) or "无"))
    raw = doc.get("steps")
    if not isinstance(raw, list) or not raw:
        return {"schema": SCHEMA, "ok": False, "workflow": wf, "order": [], "steps": {},
                "issues": issues + ["计划 steps 须为非空列表（修复指引：至少一步；"
                                    "一步一个工具调用）"]}
    s_issues, steps, ids, needs = _step_ids_issues(raw, cat, wf)
    issues += s_issues
    issues += _needs_issues(ids, steps, needs)
    for sid in ids:
        issues += _args_issues(sid, steps[sid]["args"],
                               cat["tools"].get(steps[sid]["tool"]) or {}, ids,
                               _closure(sid, needs))
    order = _topo(ids, needs)
    if len(order) != len(ids):
        left = sorted(set(ids) - set(order))
        issues.append("依赖成环（涉环步骤：%s；修复指引：依赖图必须是 DAG——环会让顺序不可判）"
                      % "、".join(left))
    return {"schema": SCHEMA, "ok": not issues, "workflow": wf, "order": order,
            "steps": steps, "issues": issues}


_CIRCUIT: Dict[str, Dict[str, float]] = {}


def _circuit_blocked(key: str, threshold: int, cooldown: float) -> bool:
    if not key:
        return False
    rec = _CIRCUIT.get(key)
    if not rec or rec.get("failures", 0) < threshold:
        return False
    if time.perf_counter() - rec.get("opened_at", 0.0) < cooldown:
        return True
    rec["failures"] = max(0, threshold - 1)   # half-open：放行一次探测
    return False


def _circuit_record(key: str, ok: bool, threshold: int) -> bool:
    """记录一次结果 → 熔断是否处于打开态。"""
    if not key:
        return False
    rec = _CIRCUIT.setdefault(key, {"failures": 0.0, "opened_at": 0.0})
    if ok:
        rec["failures"] = 0.0
        rec["opened_at"] = 0.0
        return False
    rec["failures"] = rec.get("failures", 0.0) + 1
    if rec["failures"] >= threshold:
        rec["opened_at"] = time.perf_counter()
        return True
    return False


def _skip_remaining(states: Dict[str, str], queue: deque) -> None:
    for rest in queue:
        states[rest] = "skipped"


@dataclass(frozen=True)
class DispatchOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    max_seconds: Optional[float] = None
    max_step_seconds: Optional[float] = None
    breaker_key: str = ''
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
