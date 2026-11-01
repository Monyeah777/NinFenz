"""插件**晋升门**（P5-10）：缺一不可的三条判据，可机检、可复算。

§18.4 原文的三条：
  (a) 热面实测 ≥ N× 加速；
  (b) 第三部分仲裁证明与 Python **逐字节等价**；
  (c) 工具链维护成本可接受。

本模块只做**判定**（纯函数）：证据（evidence）由适配器侧真测出来（scripts/plugin_promote.py），
判定在这里，两者的分界就是「测量」与「规则」的分界。

一条刻意的纪律：**不通过是正常结果**。§18.2 说「按测得成本分配语言，不是按偏好」——若插件
并不更快（wasm 沙箱有启动/边界成本），门就必须判不通过。所以 decide 的失败路径与成功路径
一样是交付物，必须可机检、有理由、带数字。本机实测两侧都出现过：1 MiB 输入插件快 2.8×，
32 MiB 输入插件慢 0.8×。

覆盖棘轮：已晋升的面只增不减（§18.4「覆盖棘轮只增不减」）。ratchet 判当前集合是否少了
冻结基线里的面。

依赖姿态：零 core 依赖（只 stdlib）——SDP 叶子。
"""
from __future__ import annotations

from typing import Any

SCHEMA = "nf-plugin-gate/1"
#: 默认阈值。min_speedup=2.0 取「加速得看得见」的量级；max_toolchain_cost 用「新增工具链
#: 数量」计（0=纯 Python，1=借用既有工具链，2=新增一条链），2 是上限。
DEFAULTS = {"min_speedup": 2.0, "max_toolchain_cost": 2, "require_arbitration": "PASS"}
#: 仲裁里被视为「已证字节等价」的结论。SPEC-GAP 明确**不算**通过（那是规范有缺口）。
_PASS_OUTCOMES = ("PASS",)


def _criterion(ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {"ok": bool(ok), "detail": detail, **extra}


def decide(evidence: dict[str, Any], thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    """把证据按三条判据判定 → 机检报告（含逐条数字与不通过理由）。

    evidence 形状：
        {"face": "sha256", "baseline_ms": 12.0, "plugin_ms": 3.0,
         "arbitration": {"outcome": "PASS", "comparable": 2},
         "toolchain": {"available": True, "kind": "wasm32-wasip1+wasmtime",
                       "toolchain_cost": 1}}
    """
    th = dict(DEFAULTS)
    th.update(thresholds or {})
    base = evidence.get("baseline_ms")
    plug = evidence.get("plugin_ms")
    arb = evidence.get("arbitration") or {}
    tc = evidence.get("toolchain") or {}

    if isinstance(base, (int, float)) and isinstance(plug, (int, float)) and plug > 0:
        speedup = float(base) / float(plug)
        a_ok = speedup >= float(th["min_speedup"])
        a = _criterion(a_ok, f"加速 {speedup:.2f}×（阈值 {th['min_speedup']:.2f}×）",
                       speedup=round(speedup, 4), value=speedup, threshold=th["min_speedup"])
    else:
        speedup = None
        a = _criterion(False, "缺可比耗时（baseline_ms / plugin_ms 至少一侧不可用）",
                       speedup=None, value=None, threshold=th["min_speedup"])

    outcome = str(arb.get("outcome") or "UNKNOWN")
    comparable = int(arb.get("comparable") or 0)
    b_ok = outcome in _PASS_OUTCOMES and comparable >= 2 and outcome == th["require_arbitration"]
    b = _criterion(b_ok, "仲裁 {}（可比实现 {}，须 {} 且 ≥2 个可比）"
                   .format(outcome, comparable, th["require_arbitration"]),
                   outcome=outcome, comparable=comparable)

    cost = tc.get("toolchain_cost")
    cap = int(th["max_toolchain_cost"])
    c_ok = bool(tc.get("available")) and isinstance(cost, int) and cost <= cap
    c = _criterion(c_ok, "工具链 {} · 成本 {}（上限 {}）"
                   .format("在场" if tc.get("available") else "缺席", cost,
                           th["max_toolchain_cost"]),
                   available=bool(tc.get("available")), toolchain_cost=cost, kind=tc.get("kind"))

    reasons = [k + "：" + v["detail"] for k, v in
               (("speedup", a), ("byte_equivalence", b), ("toolchain_cost", c)) if not v["ok"]]
    return {
        "schema": SCHEMA,
        "face": str(evidence.get("face") or ""),
        "promoted": not reasons,
        "criteria": {"speedup": a, "byte_equivalence": b, "toolchain_cost": c},
        "reasons": reasons,
        "thresholds": th,
        "measured": {"baseline_ms": base, "plugin_ms": plug,
                     "speedup": None if speedup is None else round(speedup, 4)},
        "invariants": {
            "reference_always_present": True,
            "plugin_never_on_correctness_path": True,
            "spec_gap_is_not_a_pass": outcome == "SPEC-GAP" and not b_ok,
        },
    }


def ratchet(current: list[str], frozen: list[str]) -> list[str]:
    """覆盖棘轮：冻结基线里已晋升的面不得从当前集合消失（只增不减）。"""
    cur = set(current or [])
    return [f"已晋升面消失：{f}" for f in sorted(set(frozen or [])) if f not in cur]


def gate_ok(report: dict[str, Any]) -> bool:
    """报告是否判「晋升」（便于调用方不重写判定）。"""
    return bool(report.get("promoted"))
