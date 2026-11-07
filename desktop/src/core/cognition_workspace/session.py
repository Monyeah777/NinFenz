"""会话门面：begin / step / close / status，把 discourse + moves + records 串起来。

设计纪律：
- step 必须带 frame_delta，且经过 moves.validate_delta（语义判据，不只看格式）；
- 每步返回 (records, state)，两者都可落盘；replay 用 records 就能复算出 state；
- 不写墙钟：需要时间就由调用方传 at（缺省不写）。
"""
from __future__ import annotations

from typing import Any

from core.cognition_workspace import control as ct
from core.cognition_workspace import discourse as dc
from core.cognition_workspace import moves as mv
from core.cognition_workspace import records as rc

SCHEMA = "nf-cog-session/1"
GUIDE = "修复指引："


def begin(problem: str, steps_max: int = 24) -> dict[str, Any]:
    state = dc.new(problem, steps_max=steps_max)
    return {"schema": SCHEMA, "state": state, "records": rc.new_records(state),
            "control": ct.new()}


def _control_of(bundle: dict[str, Any]) -> dict[str, Any]:
    return bundle.get("control") or ct.new()


def step(bundle: dict[str, Any], move_id: str, delta: dict[str, Any]) -> dict[str, Any]:
    """执行一步（bundle = {state, records, control}），返回新 bundle。"""
    control = _control_of(bundle)
    if control["status"] != "running":
        raise ValueError("控制面已 " + control["status"]
                         + "——stop/abstain 之后不能再加动作（修复指引：新开会话）")
    problems = mv.validate_delta(move_id, delta)
    if problems:
        raise ValueError("动作不合法：" + "；".join(problems[:3]))
    new_records, new_state = rc.append(bundle["records"], bundle["state"],
                                       move_id, delta)
    return {"schema": SCHEMA, "state": new_state, "records": new_records,
            "control": control}


def control(bundle: dict[str, Any], op_id: str, payload: dict[str, Any],
            trigger: str = "") -> dict[str, Any]:
    """执行一个元算子（过程控制），返回新 bundle。"""
    control_state = _control_of(bundle)
    new_control, out = ct.apply(control_state, op_id, payload,
                                discourse=bundle["state"], trigger=trigger)
    new_bundle = dict(bundle)
    new_bundle["control"] = new_control
    if out.get("discourse") is not None:
        new_bundle["state"] = out["discourse"]
    return new_bundle


def triggers(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return ct.triggers(bundle["state"], _control_of(bundle))


def replay_control(bundle: dict[str, Any]) -> dict[str, Any]:
    return ct.replay(_control_of(bundle), bundle.get("state"))


def close(bundle: dict[str, Any], verdict: str = "") -> dict[str, Any]:
    state = dc.close(bundle["state"], verdict=verdict)
    return {"schema": SCHEMA, "state": state, "records": bundle["records"],
            "control": _control_of(bundle)}


def status(bundle: dict[str, Any]) -> dict[str, Any]:
    return dc.summary(bundle["state"])


def replay(bundle: dict[str, Any]) -> dict[str, Any]:
    return rc.replay(bundle["records"])


def diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return rc.diff(a.get("records") or {}, b.get("records") or {})
