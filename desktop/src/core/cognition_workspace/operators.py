"""11 个元算子：改「过程」而不改「内容」的一层动作。

平面分离（本层最硬的约束）：
- meta move 改**问题/框架**（discourse 面）；
- object atom 改**产物/证据**（契约面）；
- operator 只改**过程控制**（策略/预算/焦点/中止）——
  它**不得**写 open_questions/tensions/assumptions。

每个算子必须带 witness（副作用证据）且必须有真实 effect（无变化即拒绝），否则就是「元认知表演」。
"""
from __future__ import annotations

from typing import Any

SCHEMA = "nf-control-operator/1"

#: discourse 面的字段：算子 payload 里出现这些键 = 越界（改内容而不是改过程）
DISCOURSE_KEYS = ("problem", "assumptions", "tensions", "open_questions", "moves",
                  "statement", "objection", "hypothesis")

OPERATORS: dict[str, dict[str, Any]] = {
    "observe": {
        "name": "观测",
        "when": "需要拿到当前状态的客观读数（计数/比率/耗时），而不是再想一遍",
        "witness": ("observation", "reading"),
        "effect": "last_observation",
        "failure_mode": "连续多轮 observe 但读数没变（仪式化观测）",
    },
    "estimate": {
        "name": "估计",
        "when": "缺精确值、但需要一个可校准的猜测（区间/点估计）",
        "witness": ("claim", "value", "basis"),
        "effect": "estimate",
        "failure_mode": "给估计但不给依据（basis 空），后面无法校准",
    },
    "detect": {
        "name": "检测",
        "when": "怀疑出现异常（无进展/回环/冲突/预算异常）",
        "witness": ("anomaly", "evidence"),
        "effect": "detected",
        "failure_mode": "只报「感觉不对」，不给可复核的证据",
    },
    "calibrate": {
        "name": "校准",
        "when": "已有 estimate 且拿到了实测值，需要修正偏差",
        "witness": ("estimate_ref", "actual", "gap"),
        "effect": "calibration",
        "failure_mode": "没有先前的 estimate 就校准（凭空校准）",
    },
    "allocate": {
        "name": "分配",
        "when": "资源（步数/注意力）配置与目标不匹配",
        "witness": ("resource", "from", "to", "reason"),
        "effect": "budget",
        "failure_mode": "分配前后数值相同（假分配）",
    },
    "switch": {
        "name": "换策略",
        "when": "当前策略反复无效（循环/无进展/冲突），需要换一条",
        "witness": ("from", "to", "reason"),
        "effect": "strategy",
        "failure_mode": "from == to（没换）或没有理由",
    },
    "stop": {
        "name": "停止",
        "when": "已达目标、或明显不可达、或风险不可接受",
        "witness": ("reason", "terminal_state"),
        "effect": "stopped",
        "failure_mode": "没到终点就停（逃避），或停了还能继续跑（假停止）",
    },
    "abstain": {
        "name": "弃权",
        "when": "证据不足以下结论，但必须显式标记未覆盖",
        "witness": ("question", "missing", "why_not_guess"),
        "effect": "abstained",
        "failure_mode": "把「不知道」写成「通过了」",
    },
    "revise": {
        "name": "修订",
        "when": "既有结论/假设被新证据推翻一部分",
        "witness": ("target", "before", "after"),
        "effect": "revision",
        "failure_mode": "before == after（没改）或没写依据",
    },
    "request_context": {
        "name": "请求上下文",
        "when": "缺关键输入（数据/权限/领域知识），继续算只是在猜",
        "witness": ("missing", "needed_for"),
        "effect": "context_request",
        "failure_mode": "缺什么都说不清就要求「更多信息」",
    },
    "audit": {
        "name": "审计",
        "when": "要检查自己的记录/判据是否自洽（红队自己的输出）",
        "witness": ("target", "finding"),
        "effect": "audit",
        "failure_mode": "审计完没有任何 finding（等于没审）",
    },
}

OPERATOR_IDS = tuple(OPERATORS)

CONTROL_SCHEMA = "nf-control-state/1"
RECORD_SCHEMA = "nf-control-record/1"
GUIDE = "修复指引："


def validate_request(op_id: str, payload: Any) -> list[str]:
    """校验一次算子请求 → 问题列表（空 = 可执行）。"""
    if op_id not in OPERATORS:
        return ["未知元算子：" + str(op_id) + "（可用：" + "、".join(OPERATOR_IDS) + "）"]
    if not isinstance(payload, dict):
        return ["算子 payload 必须是对象（" + GUIDE + "见 operators.OPERATORS）"]
    issues: list[str] = []
    for key in OPERATORS[op_id]["witness"]:
        value = payload.get(key)
        if value is None or (isinstance(value, (str, list, dict)) and not value):
            issues.append("算子 " + op_id + " 缺 witness 字段 " + key
                          + "（" + GUIDE + "没有副作用证据的算子请求要拒绝）")
    crossed = [key for key in DISCOURSE_KEYS if key in payload]
    if crossed:
        issues.append("算子 " + op_id + " 越界写了 discourse 字段 " + str(crossed)
                      + "（" + GUIDE + "算子只改过程，内容变化要用 meta move）")
    if op_id == "switch" and str(payload.get("from")) == str(payload.get("to")):
        issues.append("switch 的 from 与 to 相同——没换策略（" + GUIDE + "写清换到哪条）")
    if op_id == "allocate" and str(payload.get("from")) == str(payload.get("to")):
        issues.append("allocate 前后数值相同——假分配（" + GUIDE + "写真实改变）")
    if op_id == "revise" and str(payload.get("before")) == str(payload.get("after")):
        issues.append("revise 的 before 与 after 相同——没改（" + GUIDE + "写改成了什么）")
    if op_id == "calibrate" and not str(payload.get("estimate_ref") or "").strip():
        issues.append("calibrate 缺 estimate_ref——凭空校准（" + GUIDE + "先 estimate）")
    return issues


def describe(op_id: str) -> dict[str, Any]:
    cfg = OPERATORS.get(op_id)
    if not cfg:
        return {}
    return {"id": op_id, "schema": SCHEMA, **cfg}
