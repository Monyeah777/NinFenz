"""Research 能力的生产自检面（把「只被单测引用」的模块接到可调用入口）。

App 门面 / 导入嗅探 / 灰度 / 实验健康 / PBE / 属性检查 / SMT 回退 / solver 策略
此前只被各自的单测 import，`test_dead_code` 会判成「路径不可达」的墓碑。
本模块用确定性、零网络、零写盘的样例**真调用**每个入口，供
`scripts/capabilities.py --research` 使用：跑不通就是入口不可用，不是「没跑到」。
"""
from __future__ import annotations

from typing import Any

from core.research import (
    app_facade,
    constraints,
    experiment_health,
    feature_gate,
    import_adapters,
    pbe,
    property_check,
    smt_constraints,
    solver_policy,
    tier_gate,
)

SCHEMA = "nf-research-selftest/1"


def _check(name: str, fn) -> dict[str, Any]:
    try:
        ok, detail = fn()
    except Exception as exc:  # 入口抛错 = 不可用，按失败记，不静默
        return {"module": name, "ok": False, "detail": type(exc).__name__ + ": " + str(exc)}
    return {"module": name, "ok": bool(ok), "detail": detail}


def selftest() -> dict[str, Any]:
    """→ 逐入口自检结果；同一输入必得同一输出（确定性）。"""
    rows: list[dict[str, Any]] = []

    def import_sniff():
        info = import_adapters.sniff("sample.md", b"# T\n\n- a\n- b\n")
        return (info["format"] == "markdown" and info["supported"]), info["format"]

    def facade_export():
        fac = app_facade.AppFacade(tier="free")
        opened = fac.open_import("sample", [{"id": "s1", "value": "a"}])
        exported = fac.export()
        return (opened["ok"] and exported.get("exported") is True), fac.state.status

    def free_tier():
        gate = tier_gate.check("free", "export")
        return gate["allowed"], gate["reason"]

    def pbe_learn():
        result = pbe.learn([pbe.Example("  a   b  ", "a b")])
        return result.exact, result.program.name if result.program else ""

    def required_property():
        out = property_check.check_required()
        return out["status"] == "passed", out["status"]

    def smt_assign():
        out = smt_constraints.assign_sections(["s1"], [constraints.Slot("a", True)])
        return out["status"] in {"sat", "ok"}, out["status"]

    def solver_symbolic():
        out = solver_policy.solve(
            [1], lambda _ex: [solver_policy.Candidate("v", 1.0)])
        return out.source == "symbolic", out.source

    def flag_bucket():
        gate = feature_gate.FeatureGate([feature_gate.Flag("probe")])
        return gate.evaluate("probe", "selftest")["enabled"], "bucket"

    def experiment_ok():
        snap = experiment_health.Snapshot(
            "probe", ("a", "b"), {"a": 100, "b": 100}, 100)
        out = experiment_health.health(snap)
        return out.get("status") == "ok", out.get("status", "")

    for name, fn in (
        ("app_facade", facade_export),
        ("feature_gate", flag_bucket),
        ("experiment_health", experiment_ok),
        ("import_adapters", import_sniff),
        ("pbe", pbe_learn),
        ("property_check", required_property),
        ("smt_constraints", smt_assign),
        ("solver_policy", solver_symbolic),
        ("tier_gate", free_tier),
    ):
        rows.append(_check(name, fn))

    passed = sum(1 for r in rows if r["ok"])
    return {"schema": SCHEMA, "total": len(rows), "passed": passed,
            "failed": len(rows) - passed, "rows": rows}
