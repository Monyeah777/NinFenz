#!/usr/bin/env python3
# nf-io: inputs=plan,state,fixture outputs=trace,fixture
"""NF 参考运行时（T7.3）：确定性 harness + record/replay，**不接真实模型、不发网络请求**。

要证明的一件事
--------------
给定「装配计划 + 状态」，按**管线层序**跑一遍应当产出**逐字节可复现**的 trace 与产物 digest；
模型调用可以先录成 fixture，之后离线回放同一结果。这是后续接真实模型客户端之前，
把「运行时语义」与「模型能力」解耦的最小地基。

三条硬纪律
----------
1. **确定性**：无随机、无时钟、无网络。MockModel 的响应 = sha256(契约摘要 + step) 派生；
   trace 里 `duration_ms` 只是**占位 0**（真实耗时属不确定面，永不进判据）。
2. **fail-closed**：fixture 缺失 / 篡改 / 与当前计划或状态不符 / 调用序列缺项，
   一律 FAIL 并给修复指引——**不猜、不用默认值补齐**。
3. **可替换**：运行时只依赖 `ModelClient.respond(contract_digest, step_id) -> str` 这一个接口。
   将来接真实模型 = 新增一个实现同一接口的 client 注入 `execute()`，本模块其余逻辑不动
   （替换点见 `ModelClient` 文档与仓库报告）。

产物形状
--------
- trace（`nf-runtime-trace/1`）：plan_digest / state_digest / steps[]（step/layer/module/
  输入摘要/输出摘要/时长占位）+ artifacts[]（每步响应）+ artifact_digest。
- fixture（`nf-runtime-fixture/1`）：plan_digest / state_digest / calls[]（step_id +
  contract_digest + response + response_digest）+ trace_digest / artifact_digest。

用法（经 CLI）
--------------
    nf runtime run --plan plan.json --trace trace.json [--state state.json]
                   [--record fixture.json] [--replay fixture.json] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]

from core import atomic_write, json_doc  # noqa: E402  - core 包内导入（与同层模块同写法）

TRACE_SCHEMA = "nf-runtime-trace/1"
FIXTURE_SCHEMA = "nf-runtime-fixture/1"
JSON_SCHEMA = "nf-runtime-run/1"
DURATION_PLACEHOLDER_MS = 0
DEFAULT_STATE_REL = "protocol/world_slots.json"


class RuntimeFailure(RuntimeError):
    """运行时判据失败（fixture 缺失/篡改/不一致等）；消息必带修复指引（purity R4）。"""


# ---------------------------------------------------------------- 确定性基元
def canonical(obj: Any) -> str:
    """规范 JSON：键排序、无空白、非 ASCII 原样——同对象必得同一字节串。"""
    import json

    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(obj: Any) -> str:
    """对象 → `sha256:<hex>`（内容寻址；用于计划/状态/产物摘要）。"""
    return "sha256:" + hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _load_json(path: Path, what: str) -> Any:
    try:
        return json_doc.load(path, dict, what=what)
    except ValueError as exc:
        raise RuntimeFailure("%s（修复指引：本件须是 UTF-8 JSON 对象；"
                             "计划由 `nf assemble --plan-output` 样式的 assemble_plan.plan 产出）"
                             % exc) from exc


# ---------------------------------------------------------------- 模型接口（替换点）
class ModelClient:
    """模型客户端协议：**唯一替换点**（MockModel → 真实模型 client）。

    约定（运行时只依赖这三条）：
    - `respond(contract_digest, step_id)` 必须是**纯函数式**的：同参数同响应；
    - 不读时钟 / 不用随机 / 不发网络（真实 client 也须把这三类不确定面留在运行时之外，
      或以 fixture 形式先录制）；
    - 抛异常 = 该步失败，运行时整体 FAIL（不吞）。
    """

    def respond(self, contract_digest: str, step_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("子类须实现 respond（修复指引：MockModel / ReplayModel / 真实 client）")


class MockModel(ModelClient):
    """确定性假模型：响应由 `sha256(contract_digest + step_id)` 派生（无随机/无网络）。"""

    def respond(self, contract_digest: str, step_id: str) -> str:
        h = hashlib.sha256(("%s|%s" % (contract_digest, step_id)).encode("utf-8")).hexdigest()
        return ("mock-output | step=%s | contract=%s | token=%s"
                % (step_id, contract_digest.replace("sha256:", "")[:12], h[:16]))


class ReplayModel(ModelClient):
    """回放模型：按 step_id 取 fixture 里的响应；fixture 已由 `_load_fixture` 校验过。"""

    def __init__(self, calls: Dict[str, Dict[str, Any]]) -> None:
        self._calls = dict(calls)

    def respond(self, contract_digest: str, step_id: str) -> str:
        call = self._calls.get(step_id)
        if call is None:
            raise RuntimeFailure("回放缺该步调用：%s（修复指引：重跑 `nf runtime run --plan … "
                                 "--trace … --record <fixture>` 重录；不要手补 fixture）" % step_id)
        return str(call["response"])


# ---------------------------------------------------------------- 计划 → 步骤
def _dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _module_ref(value: Any) -> str:
    return str(value).strip()


def plan_steps(plan: Dict[str, Any]) -> List[Dict[str, str]]:
    """装配计划 → 有序步骤 [{layer, module}]（**管线层序**优先；无管线件按取件序兜底）。"""
    from core import pipeline_loader  # 延迟导入：只在真跑时付一次

    steps: List[Dict[str, str]] = []
    for rel in plan.get("pipeline_files") or []:
        path = Path(str(rel))
        if not path.is_absolute():
            path = ROOT / path
        try:
            pipe = pipeline_loader.load_pipeline_file(path)
        except Exception:  # noqa: BLE001 - 坏管线件不在这里判死（由 check28 另判），退兜底序
            pipe = None
        if pipe is None:
            continue
        for layer in pipe.layers:
            mods = _dedupe([_module_ref(m) for m in
                            list(layer.default_modules) + list(layer.allowed_modules)])
            for module in mods:
                steps.append({"layer": str(layer.name), "module": module})
    if not steps:
        for module in _dedupe([_module_ref(m) for m in
                               (plan.get("fetch_modules") or plan.get("allowed_module_ids") or [])]):
            if module:
                steps.append({"layer": "core", "module": module})
    if not steps:
        raise RuntimeFailure(
            "装配计划没有可执行步骤（修复指引：计划须含 `pipeline_files`（可解析层序）"
            "或非空 `fetch_modules`；请用 assemble_plan.plan 的真实产出，不要手写空壳）")
    return steps


def step_contract(plan_digest: str, state_digest: str, step_id: str,
                  module: str, layer: str) -> str:
    """单步契约摘要（含计划/状态/步骤身份——状态变则契约变，响应也随之一致地变）。"""
    return digest({"plan": plan_digest, "state": state_digest, "step_id": step_id,
                   "module": module, "layer": layer})


def _step_id(index: int, layer: str, module: str) -> str:
    return "%02d|%s|%s" % (index, layer, module)


# ---------------------------------------------------------------- 执行
def execute(plan: Dict[str, Any], state: Dict[str, Any],
            client: Optional[ModelClient] = None) -> Dict[str, Any]:
    """跑一遍 → trace 文档（纯函数 + 注入 client；同输入同字节）。"""
    model = client or MockModel()
    plan_d = digest(plan)
    state_d = digest(state)
    steps = plan_steps(plan)
    events: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []
    calls: List[Dict[str, Any]] = []
    for index, step in enumerate(steps, 1):
        sid = _step_id(index, step["layer"], step["module"])
        contract = step_contract(plan_d, state_d, sid, step["module"], step["layer"])
        try:
            response = model.respond(contract, sid)
        except RuntimeFailure:
            raise
        except Exception as exc:  # noqa: BLE001 - 任何模型失败都整体 FAIL，不静默降级
            raise RuntimeFailure("第 %d 步模型调用失败（%s）：%s（修复指引：核对 client 实现或 "
                                 "fixture 完整性；真实模型不自动重试）"
                                 % (index, sid, exc)) from exc
        resp_d = digest_text(response)
        events.append({
            "step": index, "step_id": sid, "layer": step["layer"],
            "module": step["module"], "contract_digest": contract,
            "inputs": {"state_digest": state_d, "layer": step["layer"],
                       "module": step["module"]},
            "outputs": {"response_digest": resp_d, "excerpt": str(response)[:80]},
            "duration_ms": DURATION_PLACEHOLDER_MS,
        })
        artifacts.append({"step": index, "step_id": sid, "module": step["module"],
                          "response": response, "response_digest": resp_d})
        calls.append({"step_id": sid, "contract_digest": contract,
                      "response": response, "response_digest": resp_d})
    artifact_digest = digest([{"step_id": a["step_id"], "response_digest": a["response_digest"]}
                              for a in artifacts])
    return {"schema": TRACE_SCHEMA, "plan_digest": plan_d, "state_digest": state_d,
            "steps": events, "artifacts": artifacts,
            "artifact_digest": artifact_digest}


# ---------------------------------------------------------------- fixture ⊂ trace
def fixture_from(trace: Dict[str, Any], calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"schema": FIXTURE_SCHEMA,
            "plan_digest": trace["plan_digest"],
            "state_digest": trace["state_digest"],
            "calls": calls,
            "trace_digest": digest(trace),
            "artifact_digest": trace["artifact_digest"]}


def _verify_fixture_shape(doc: Dict[str, Any], rel: str) -> List[Dict[str, Any]]:
    if str(doc.get("schema") or "") != FIXTURE_SCHEMA:
        raise RuntimeFailure("%s 不是 %s fixture（实为 %r）（修复指引：--replay 只接受本运行时的 "
                             "--record 产出；不要手造 fixture）"
                             % (rel, FIXTURE_SCHEMA, doc.get("schema")))
    calls = doc.get("calls")
    if not isinstance(calls, list) or not calls:
        raise RuntimeFailure("%s 的 calls 为空/非数组（修复指引：重跑 --record 重录）" % rel)
    for i, call in enumerate(calls):
        if not isinstance(call, dict) or not {"step_id", "contract_digest", "response",
                                              "response_digest"} <= set(call):
            raise RuntimeFailure("%s 的 calls[%d] 形状不全（修复指引：重录；不要手补字段）"
                                 % (rel, i))
        if digest_text(str(call["response"])) != str(call["response_digest"]):
            raise RuntimeFailure("%s 的 calls[%d] 响应摘要不符（fixture 被篡改）"
                                 "（修复指引：用原台架重录，不要改 fixture）" % (rel, i))
    return calls


def load_fixture(path: Path, rel: str, plan: Dict[str, Any],
                 state: Dict[str, Any]) -> Tuple[ReplayModel, Dict[str, Any]]:
    """读 fixture + 校验（计划/状态一致、调用序列完整、响应摘要自洽）→ (client, doc)。"""
    if not path.is_file():
        raise RuntimeFailure("fixture 缺失：%s（修复指引：先 `nf runtime run --plan … --trace … "
                             "--record <fixture>` 录制；或检查 --replay 路径）" % rel)
    doc = _load_json(path, rel)
    calls = _verify_fixture_shape(doc, rel)
    if str(doc.get("plan_digest")) != digest(plan):
        raise RuntimeFailure("%s 与当前计划不符（fixture 是别的计划的录像）"
                             "（修复指引：同一 --plan 才可回放；换计划请重录）" % rel)
    if str(doc.get("state_digest")) != digest(state):
        raise RuntimeFailure("%s 与当前状态不符（fixture 是别的 state 的录像）"
                             "（修复指引：同一 --state 才可回放；换状态请重录）" % rel)
    by_step: Dict[str, Dict[str, Any]] = {}
    for call in calls:
        sid = str(call["step_id"])
        if sid in by_step:
            raise RuntimeFailure("%s 的 calls 重复 step_id：%s（修复指引：重录）" % (rel, sid))
        by_step[sid] = call
    return ReplayModel(by_step), doc


def replay_check(doc: Dict[str, Any], rel: str, trace: Dict[str, Any],
                 calls: List[Dict[str, Any]]) -> None:
    """回放后对账：调用序列/契约摘要/trace 与产物摘要必须与 fixture 完全一致。"""
    if sorted(c["step_id"] for c in calls) != sorted(c["step_id"] for c in doc["calls"]):
        raise RuntimeFailure("%s 的调用序列与本次步骤不一致（计划/状态已变？）"
                             "（修复指引：重录 fixture，不要沿用旧录像）" % rel)
    want = {str(c["step_id"]): str(c["contract_digest"]) for c in doc["calls"]}
    for call in calls:
        sid = str(call["step_id"])
        if want.get(sid) != str(call["contract_digest"]):
            raise RuntimeFailure("%s 的 step %s 契约摘要不符（fixture 被篡改或计划已变）"
                                 "（修复指引：重录）" % (rel, sid))
    if str(doc.get("artifact_digest")) != str(trace["artifact_digest"]):
        raise RuntimeFailure("%s 记录的产物摘要与回放结果不符（修复指引：重录；"
                             "不得手改 fixture 的 artifact_digest）" % rel)
    if str(doc.get("trace_digest")) != digest(trace):
        raise RuntimeFailure("%s 记录的 trace 摘要与回放结果不符（fixture 被篡改）"
                             "（修复指引：重录）" % rel)


# ---------------------------------------------------------------- 状态/计划装载
def load_state(state_path: str) -> Tuple[Dict[str, Any], str]:
    """→ (state, 来源说明)。未传 --state 时读 protocol/world_slots.json（无则空对象）。"""
    if state_path:
        path = Path(state_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.is_file():
            raise RuntimeFailure("状态件缺失：%s（修复指引：--state 给在场 JSON 文件；"
                                 "不要让它静默按空状态跑）" % state_path)
        return _load_json(path, state_path), state_path
    default = ROOT / DEFAULT_STATE_REL
    if default.is_file():
        return _load_json(default, DEFAULT_STATE_REL), DEFAULT_STATE_REL
    return {}, "（空状态）"


def _load_plan(plan_path: str) -> Dict[str, Any]:
    path = Path(plan_path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise RuntimeFailure("装配计划缺失：%s（修复指引：先由 assemble_plan.plan 产出计划 JSON；"
                             "本命令只读计划、不替你猜）" % plan_path)
    plan = _load_json(path, plan_path)
    if not any(plan.get(k) for k in ("pipeline_files", "fetch_modules", "allowed_module_ids")):
        raise RuntimeFailure("装配计划缺执行面（%s 里没有 pipeline_files/fetch_modules/"
                             "allowed_module_ids）（修复指引：用 assemble_plan.plan 的真实产出）"
                             % plan_path)
    return plan


# ---------------------------------------------------------------- 落盘
def _write_json(path: Path, rel: str, doc: Dict[str, Any]) -> None:
    try:
        atomic_write.write_text(path, canonical(doc) + "\n")
    except OSError as exc:
        raise RuntimeFailure("写盘失败 %s：%s（修复指引：确认落点目录可写；"
                             "或改用可写的 --trace / --record 路径）" % (rel, exc)) from exc


def _write_fixture(path: Path, rel: str, doc: Dict[str, Any]) -> None:
    """fixture 用**可读**缩进写（审阅优先）；内容与 canonical 同源，回放按对象判等。"""
    import json

    try:
        atomic_write.write_text(path, json.dumps(doc, ensure_ascii=False, indent=2,
                                                 sort_keys=True) + "\n")
    except OSError as exc:
        raise RuntimeFailure("写 fixture 失败 %s：%s（修复指引：确认落点可写）"
                             % (rel, exc)) from exc


# ---------------------------------------------------------------- CLI 入口
def cli_run(plan: str, trace: str, state: str = "", record: str = "",
            replay: str = "", as_json: bool = False) -> int:
    """`nf runtime run` 的执行体 → 退出码（0 成功 / 1 fail-closed 拒绝）。"""
    try:
        if record and replay:
            raise RuntimeFailure("--record 与 --replay 互斥（修复指引：录制用 --record，"
                                 "回放用 --replay；不要在同一跑里既录又放）")
        plan_doc = _load_plan(plan)
        state_doc, state_src = load_state(state)
        if replay:
            client, fixture_doc = load_fixture(Path(replay) if Path(replay).is_absolute()
                                               else ROOT / replay, replay, plan_doc, state_doc)
            trace_doc = execute(plan_doc, state_doc, client)
            replay_check(fixture_doc, replay, trace_doc,
                         [{"step_id": e["step_id"], "contract_digest": e["contract_digest"]}
                          for e in trace_doc["steps"]])
        else:
            trace_doc = execute(plan_doc, state_doc, MockModel())
            if record:
                fixture = fixture_from(trace_doc, [
                    {"step_id": e["step_id"], "contract_digest": e["contract_digest"],
                     "response": a["response"], "response_digest": a["response_digest"]}
                    for e, a in zip(trace_doc["steps"], trace_doc["artifacts"])])
                _write_fixture(Path(record) if Path(record).is_absolute() else ROOT / record,
                               record, fixture)
        trace_path = Path(trace) if Path(trace).is_absolute() else ROOT / trace
        _write_json(trace_path, trace, trace_doc)
    except RuntimeFailure as exc:
        payload = {"ok": False, "error": str(exc), "exit": 1}
        if as_json:
            import json

            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        print("  ✗ %s" % exc, file=sys.stderr)
        return 1
    if as_json:
        import json

        print(json.dumps({
            "schema": JSON_SCHEMA, "ok": True,
            "plan_digest": trace_doc["plan_digest"],
            "state_digest": trace_doc["state_digest"],
            "state_source": state_src,
            "steps": len(trace_doc["steps"]),
            "artifact_digest": trace_doc["artifact_digest"],
            "trace_path": str(Path(trace)),
            "mode": "replay" if replay else "run",
            "record_path": str(Path(record)) if record else "",
        }, ensure_ascii=False, sort_keys=True))
        return 0
    mode = "replay" if replay else "run"
    print("== nf runtime %s ==" % ("run（录制/执行）" if mode == "run" else "replay（回放）"))
    print("  计划 %s · 状态 %s · 步骤 %d"
          % (trace_doc["plan_digest"][:19], state_src, len(trace_doc["steps"])))
    for event in trace_doc["steps"]:
        print("  [%02d] %-10s %-8s %s → %s"
              % (event["step"], event["layer"], event["module"],
                 event["contract_digest"][:19], event["outputs"]["response_digest"][:19]))
    print("  产物摘要：%s" % trace_doc["artifact_digest"])
    print("  trace：%s%s" % (trace, (" · fixture：%s" % record) if record else ""))
    return 0


def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - CLI 由 nf.py 承载
    """模块自跑入口（与 `nf runtime run` 同参数；供排障直调，不是第二套判据）。"""
    ap = argparse.ArgumentParser(description="NF 参考运行时（确定性 harness）")
    sub = ap.add_subparsers(dest="rt_cmd", required=True)
    run = sub.add_parser("run", help="跑一次：--plan/--trace（可 --record/--replay）")
    run.add_argument("--plan", required=True, help="装配计划 JSON 路径")
    run.add_argument("--trace", required=True, help="trace 输出 JSON 路径")
    run.add_argument("--state", default="", help="状态 JSON 路径（缺省 protocol/world_slots.json）")
    run.add_argument("--record", default="", help="录制 fixture JSON 路径")
    run.add_argument("--replay", default="", help="回放 fixture JSON 路径")
    run.add_argument("--json", action="store_true", help="输出结构化 JSON 摘要")
    args = ap.parse_args(argv)
    return cli_run(args.plan, args.trace, args.state, args.record, args.replay, args.json)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
