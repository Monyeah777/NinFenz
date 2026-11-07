"""过程控制面（nf-control-state/1）+ 触发引擎 + 双 trace。

三层职责：
1. control state：策略/预算/中止/未覆盖——只记过程事实，不记内容；
2. apply()：执行一次算子请求（校验 witness → 真改状态 → 写 control 记录）；
3. triggers()：确定性谓词，从「状态 + 记录」推出该触发哪些算子（不含随机、不含时间）。

反仪式化判据（写死在实现里）：
- 同一算子同一 witness digest 连续出现 → 判「仪式化」拒绝（observe 连续读数不变最典型）；
- 算子必须产生 effect 差异（switch from==to、allocate 同值、revise 同值在 operators 层已拒）；
- stop 之后 session 层必须拒绝新动作（真终止，不是记个日志）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from core import json_doc
from core.cognition_workspace import discourse as dc
from core.cognition_workspace import operators as op

SCHEMA = op.CONTROL_SCHEMA
GUIDE = "修复指引："
RITUAL_WINDOW = 3     # 同算子同 witness 连续 N 次 → 判仪式化


def digest_of(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new() -> dict[str, Any]:
    state: dict[str, Any] = {"schema": SCHEMA, "status": "running", "strategy": "explore",
                             "last_observation": None, "estimate": None, "detected": [],
                             "calibration": [], "revision": None, "abstained": [],
                             "context_request": None, "audit": [], "records": []}
    state["digest"] = digest_of({k: v for k, v in state.items() if k != "digest"})
    return state


def _bump(state: dict[str, Any]) -> None:
    state["digest"] = digest_of({k: v for k, v in state.items() if k != "digest"})


def validate(state: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(state, dict) or str(state.get("schema") or "") != SCHEMA:
        return ["控制面 schema 不匹配（" + GUIDE + "用 control.new 生成）"]
    if state.get("status") not in ("running", "stopped", "abstained"):
        issues.append("status 只能是 running/stopped/abstained（" + GUIDE + "用 apply 改）")
    if not isinstance(state.get("records"), list):
        issues.append("records 必须是数组（" + GUIDE + "手搓状态会破坏 trace）")
    expected = digest_of({k: v for k, v in state.items() if k != "digest"})
    if state.get("digest") != expected:
        issues.append("控制面 digest 不匹配（" + GUIDE + "被手改过——重建）")
    return issues


def ritual_issue(state: dict[str, Any], op_id: str, payload: dict[str, Any]) -> str:
    """同一算子 + 同一 witness 连续 RITUAL_WINDOW 次 → 判仪式化。"""
    witness_digest = digest_of(payload)
    need = RITUAL_WINDOW - 1          # 已连续 N-1 次相同 ⇒ 这次是第 N 次
    tail = [r for r in (state.get("records") or []) if r.get("op") == op_id][-need:]
    if len(tail) >= need and all(
            r.get("witness_digest") == witness_digest for r in tail):
        return ("算子 " + op_id + " 连续 " + str(RITUAL_WINDOW)
                + " 次给出相同 witness——仪式化（" + GUIDE + "换观测点或承认没变化）")
    return ""


def _apply_effect(state: dict[str, Any], op_id: str, payload: dict[str, Any],
                  discourse: dict[str, Any] | None) -> dict[str, Any]:
    """执行副作用（返回被改动的字段，供记录回填）。"""
    effect: dict[str, Any] = {}
    if op_id == "observe":
        state["last_observation"] = {"reading": payload["reading"],
                                     "observation": payload["observation"]}
        effect["last_observation"] = state["last_observation"]
    elif op_id == "estimate":
        state["estimate"] = {"claim": payload["claim"], "value": payload["value"],
                             "basis": payload["basis"], "digest": digest_of(payload)}
        effect["estimate"] = state["estimate"]
    elif op_id == "detect":
        state["detected"].append({"anomaly": payload["anomaly"],
                                  "evidence": payload["evidence"]})
        effect["detected"] = len(state["detected"])
    elif op_id == "calibrate":
        state["calibration"].append({"estimate_ref": payload["estimate_ref"],
                                     "actual": payload["actual"], "gap": payload["gap"]})
        effect["calibration"] = state["calibration"][-1]
    elif op_id == "allocate":
        if discourse is not None:
            discourse["budget"]["steps_max"] = int(payload["to"])
        effect["budget"] = {"from": payload["from"], "to": payload["to"]}
    elif op_id == "switch":
        state["strategy"] = str(payload["to"])
        effect["strategy"] = state["strategy"]
    elif op_id == "stop":
        state["status"] = "stopped"
        effect["status"] = "stopped"
    elif op_id == "abstain":
        state["abstained"].append({"question": payload["question"],
                                   "missing": payload["missing"]})
        state["status"] = "abstained"
        effect["abstained"] = state["abstained"][-1]
    elif op_id == "revise":
        state["revision"] = {"target": payload["target"], "before": payload["before"],
                             "after": payload["after"]}
        effect["revision"] = state["revision"]
    elif op_id == "request_context":
        state["context_request"] = {"missing": payload["missing"],
                                    "needed_for": payload["needed_for"]}
        effect["context_request"] = state["context_request"]
    elif op_id == "audit":
        state["audit"].append({"target": payload["target"],
                               "finding": payload["finding"]})
        effect["audit"] = state["audit"][-1]
    return effect


def apply(control: dict[str, Any], op_id: str, payload: dict[str, Any],
          discourse: dict[str, Any] | None = None,
          trigger: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    """执行一次算子请求 → (新控制面, 输出)。失败抛 ValueError（带修复指引）。"""
    issues = op.validate_request(op_id, payload)
    if issues:
        raise ValueError("算子请求不合法：" + "；".join(issues[:3]))
    bad = validate(control)
    if bad:
        raise ValueError("控制面不合法：" + "；".join(bad[:2]))
    if control["status"] != "running":
        raise ValueError("控制面已 " + control["status"] + "，不能再执行算子（"
                         + GUIDE + "stop/abstain 之后只能开新会话）")
    ritual = ritual_issue(control, op_id, payload)
    if ritual:
        raise ValueError(ritual)
    new_control = json_doc.loads(json.dumps(control))
    new_discourse = json_doc.loads(json.dumps(discourse)) if discourse is not None else None
    effect = _apply_effect(new_control, op_id, payload, new_discourse)
    record = {"seq": len(new_control["records"]) + 1, "op": op_id,
              "trigger": trigger or "manual",
              "witness": payload, "witness_digest": digest_of(payload),
              "effect": effect,
              "prev": (new_control["records"][-1]["digest"]
                       if new_control["records"] else "")}
    record["digest"] = digest_of({k: v for k, v in record.items() if k != "digest"})
    new_control["records"].append(record)
    _bump(new_control)
    if new_discourse is not None and op_id == "allocate":
        new_discourse["budget"]["steps_used"] = len(new_discourse["moves"])
        new_discourse["digest"] = dc.digest_of(
            {k: v for k, v in new_discourse.items() if k != "digest"})
    return new_control, {"record": record, "discourse": new_discourse}


def replay(control: dict[str, Any], discourse: dict[str, Any] | None = None) -> dict[str, Any]:
    """重放控制面记录 → {ok, control, issues}（校验 effect 与记录一致）。"""
    res: dict[str, Any] = {"ok": False, "control": None, "issues": []}
    bad = validate(control)
    if bad:
        res["issues"].extend(bad)
        return res
    fresh = new()
    fresh["records"] = []
    disc = json_doc.loads(json.dumps(discourse)) if discourse is not None else None
    prev = ""
    for item in control["records"]:
        if str(item.get("prev") or "") != prev:
            res["issues"].append("控制记录链断在第 " + str(item.get("seq"))
                                 + " 条（" + GUIDE + "prev 必须等于上一条 digest）")
            return res
        if digest_of({k: v for k, v in item.items() if k != "digest"}) != item.get("digest"):
            res["issues"].append("控制记录 digest 不符（" + GUIDE + "被改过）")
            return res
        try:
            fresh, out = apply(fresh, str(item["op"]), dict(item["witness"]),
                               discourse=disc, trigger=str(item.get("trigger") or ""))
        except ValueError as exc:
            res["issues"].append("第 " + str(item.get("seq")) + " 条无法重放：" + str(exc))
            return res
        if out["record"]["effect"] != item.get("effect"):
            res["issues"].append("第 " + str(item.get("seq")) + " 条 effect 与记录不符")
            return res
        prev = str(item["digest"])
    res.update({"ok": True, "control": fresh})
    return res


def triggers(discourse: dict[str, Any], control: dict[str, Any]) -> list[dict[str, Any]]:
    """确定性触发谓词 → [{trigger, op, why}]（顺序固定，便于判据比对）。"""
    out: list[dict[str, Any]] = []
    moves = discourse.get("moves") or []
    budget = discourse.get("budget") or {}
    steps_used = int(budget.get("steps_used") or 0)
    steps_max = int(budget.get("steps_max") or 1)
    recent = [m.get("move") for m in moves[-3:]]
    if len(recent) == 3 and len(set(recent)) == 1:
        out.append({"trigger": "loop", "op": "switch",
                    "why": "最近三步都是 " + str(recent[0]) + "（回环）"})
    if steps_used >= max(1, int(steps_max * 0.75)):
        out.append({"trigger": "budget_low", "op": "allocate",
                    "why": "已用 " + str(steps_used) + "/" + str(steps_max) + " 步"})
    tensions = discourse.get("tensions") or []
    has_challenge = any(m.get("move") in ("counterexample", "boundary_case")
                        for m in moves[-3:])
    if tensions and not has_challenge:
        out.append({"trigger": "unresolved_tension", "op": "detect",
                    "why": "存在 " + str(len(tensions)) + " 条张力且最近三步无反驳"})
    kinds = [((m.get("delta") or {}).get("kind")) for m in moves]
    if steps_used >= 4 and not any(k in ("counterexample_found", "boundary_added")
                                   for k in kinds):
        out.append({"trigger": "blind_spot", "op": "audit",
                    "why": "已走 " + str(steps_used) + " 步仍无反例/边界"})
    estimate = control.get("estimate")
    calibration = control.get("calibration") or []
    if estimate and not calibration and steps_used >= 3:
        out.append({"trigger": "calibration_drift", "op": "calibrate",
                    "why": "有估计但从未校准"})
    if control.get("context_request") and control.get("status") == "running":
        out.append({"trigger": "missing_context", "op": "abstain",
                    "why": "缺上下文未标记弃权"})
    return out
