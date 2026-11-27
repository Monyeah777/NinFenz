"""core.orchestration 私有实现分片 2/2（对外只经 core.orchestration 门面导入）：dispatch 等"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._part1 import (
    DRIVER_REL,
    SCHEMA,
    DispatchOptions,
    _circuit_blocked,
    _circuit_record,
    _skip_remaining,
    catalog,
    compile_plan,
    workflow_tools,
)


def dispatch(
    order: List[str],
    steps: Dict[str, Dict[str, Any]],
    call: Callable[[str, Dict[str, Any]], Any],
    opts: DispatchOptions | None = None,
) -> Dict[str, Any]:
    """按编译出的序派发：**首个失败即停**（fail-closed），如实回执已执行 / 停在 / 未执行。

    每步若声明了 `expects`，则在**派发时**按此验收：返回值不是对象、或缺任一字段即视为失败
    （证据不齐不得往下走——「完成了」不是证据，产物字段才是）。

    韧性扩展（2026-10-23，默认关闭以保持既有语义）：
    - `max_seconds` / `max_step_seconds`：总/单步预算。Python 不能抢占已阻塞的同步调用，
      故单步超时在调用返回后判定并 fail-closed（需要硬抢占时把 `call` 放到进程边界）；
    - `breaker_key` + `failure_threshold` + `cooldown_seconds`：跨调用熔断；打开期间直接返回
      `status=circuit_open`，冷却后放行一次半开探测；
    - `states`：pending / running / done / failed / skipped 两阶段状态。
    """

    opts = opts if opts is not None else DispatchOptions()
    max_seconds = opts.max_seconds
    max_step_seconds = opts.max_step_seconds
    breaker_key = opts.breaker_key
    failure_threshold = opts.failure_threshold
    cooldown_seconds = opts.cooldown_seconds
    results: List[Dict[str, Any]] = []
    states: Dict[str, str] = {sid: "pending" for sid in order}
    started = time.perf_counter()
    queue = deque(order)
    if _circuit_blocked(breaker_key, failure_threshold, cooldown_seconds):
        return {"executed": [], "results": [],
                "stopped_at": order[0] if order else None,
                "not_executed": list(order), "states": {sid: "skipped" for sid in order},
                "status": "circuit_open", "stopped_reason": "circuit_open",
                "circuit_open": True, "elapsed_s": 0.0}

    while queue:
        sid = queue.popleft()
        step = steps.get(sid) or {}
        if (results and max_seconds is not None
                and time.perf_counter() - started > max_seconds):
            states[sid] = "skipped"
            _skip_remaining(states, queue)
            _circuit_record(breaker_key, False, failure_threshold)
            return {"executed": [r["id"] for r in results], "results": results,
                    "stopped_at": sid, "not_executed": [sid] + list(queue),
                    "states": states, "status": "stopped",
                    "stopped_reason": "timeout", "circuit_open": False,
                    "elapsed_s": time.perf_counter() - started}
        states[sid] = "running"
        step_started = time.perf_counter()
        try:
            out = call(str(step.get("tool") or ""), dict(step.get("args") or {}))
        except Exception as exc:                              # noqa: BLE001 - 派发失败即停：异常也是「停」的证据
            states[sid] = "failed"
            _skip_remaining(states, queue)
            results.append({"id": sid, "tool": step.get("tool"), "ok": False, "detail": str(exc),
                            "elapsed_s": time.perf_counter() - step_started})
            opened = _circuit_record(breaker_key, False, failure_threshold)
            return {"executed": [r["id"] for r in results], "results": results,
                    "stopped_at": sid, "not_executed": list(queue),
                    "states": states, "status": "stopped",
                    "stopped_reason": "exception", "circuit_open": opened,
                    "elapsed_s": time.perf_counter() - started}
        elapsed = time.perf_counter() - step_started
        if max_step_seconds is not None and elapsed > max_step_seconds:
            states[sid] = "failed"
            _skip_remaining(states, queue)
            results.append({"id": sid, "tool": step.get("tool"), "ok": False,
                            "detail": "单步超预算：%.3fs > %.3fs（修复指引：把该工具放到可抢占的"
                                      "进程边界，或提高预算）" % (elapsed, max_step_seconds),
                            "elapsed_s": elapsed})
            opened = _circuit_record(breaker_key, False, failure_threshold)
            return {"executed": [r["id"] for r in results], "results": results,
                    "stopped_at": sid, "not_executed": list(queue),
                    "states": states, "status": "stopped",
                    "stopped_reason": "timeout", "circuit_open": opened,
                    "elapsed_s": time.perf_counter() - started}
        missing = [str(k) for k in (step.get("expects") or [])
                   if not isinstance(out, dict) or str(k) not in out]
        if missing:
            states[sid] = "failed"
            _skip_remaining(states, queue)
            results.append({"id": sid, "tool": step.get("tool"), "ok": False,
                            "detail": "缺证据：%s（该步 expects 未满足）" % "、".join(missing),
                            "elapsed_s": elapsed})
            opened = _circuit_record(breaker_key, False, failure_threshold)
            return {"executed": [r["id"] for r in results], "results": results,
                    "stopped_at": sid, "not_executed": list(queue),
                    "states": states, "status": "stopped",
                    "stopped_reason": "evidence", "circuit_open": opened,
                    "elapsed_s": time.perf_counter() - started}
        states[sid] = "done"
        _circuit_record(breaker_key, True, failure_threshold)
        results.append({"id": sid, "tool": step.get("tool"), "ok": True, "detail": out,
                        "elapsed_s": elapsed})
    return {"executed": [r["id"] for r in results], "results": results,
            "stopped_at": None, "not_executed": [], "states": states,
            "status": "complete", "stopped_reason": None, "circuit_open": False,
            "elapsed_s": time.perf_counter() - started}


def _sample_args(spec: Dict[str, Any]) -> Dict[str, Any]:
    """按 `inputSchema` 合成一组**可编译**的最小实参（只覆盖 required 项，按声明类型取样）。"""
    samples = {"string": "x", "integer": 1, "boolean": True, "array": [], "object": {}}
    out: Dict[str, Any] = {}
    for key in spec.get("required") or []:
        ptype = str(((spec.get("properties") or {}).get(key) or {}).get("type") or "")
        out[str(key)] = samples.get(ptype, "x")
    return out


def scan(root: str = ".", tools: Optional[Dict[str, Dict[str, Any]]] = None
         ) -> Tuple[List[str], Dict[str, Any]]:
    """机检**编排可达性**：每条工作流映射的每个工具都必须能组成一步可编译计划（空根安全）。

    与 `driver.scan`（工具名在运行时在册）**互补而非重复**：那条判“名字对不对”，这条判
    “名字对应的工具在本工作流里能不能真被编排”（required 参数可满足、schema 可判、在映射集内）。
    """
    issues: List[str] = []
    cat = catalog(root, tools)
    wf = workflow_tools(root)
    if not wf:
        issues.append("缺工作流映射 %s（修复指引：见 protocol/driver.json 的 workflows）" % DRIVER_REL)
    mapped = 0
    for name in sorted(wf):
        for tool in wf[name]:
            spec = cat["tools"].get(tool) or {}
            plan = {"schema": SCHEMA, "workflow": name,
                    "steps": [{"id": "s1", "tool": tool, "args": _sample_args(spec)}]}
            bad = compile_plan(root, plan, tools)["issues"]
            if bad:
                issues.append("工作流 %s 的工具 %s 不可编排：%s" % (name, tool, bad[0]))
            mapped += 1
    return issues, {"workflows": len(wf), "tools": len(cat["tools"]), "mapped": mapped}
