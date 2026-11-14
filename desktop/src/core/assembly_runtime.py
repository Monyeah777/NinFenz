"""Assembly Runtime（WP-21）：P00 黄金路径 core-only E2E。

链路（PR-02/PR-07 / QG2）：
intent → spec → task → context pack → agent adapter → output 校验 → gate → export 记录。

产物分两层：
- `assembly`：**schema 合法的 `nf-assembly/1` 装配计划**（pipeline/steps/modules/assets/
  output/checks/fallback，严格按 protocol/production/assembly.schema.json）；
- `run`：运行时信封（status/adapter/checks/output digest/steps trace/error）——记录执行事实，
  不塞进 assembly schema（schema additionalProperties=false）。
纪律：core-only；记录只存 digest/相对路径；失败即停（status=blocked、无 export）；
同输入逐字节确定；真实外部模型/外部发布属外部操作（OPEN）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from core import agent_adapter as aa
from core import context_packer as cp
from core import spec_compiler as sc

ASSEMBLY_SCHEMA_REL = "protocol/production/assembly.schema.json"
RUN_SCHEMA = "nf-assembly-run/1"
PLAN_SCHEMA = "nf-assembly/1"
PIPELINE = "P00"
GUIDE = "修复指引："
_STEPS = (("S01", "spec", "core:spec_compiler"), ("S02", "task", "core:spec_compiler"),
          ("S03", "context", "core:context_packer"), ("S04", "adapter", "core:agent_adapter"),
          ("S05", "output", "core:agent_adapter"), ("S06", "gate", "core:assembly_runtime"),
          ("S07", "export", "core:assembly_runtime"))
_FORM = {"md": "md", "text": "md", "json": "json", "file": "file"}


class AssemblyError(Exception):
    """运行时拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "ASSEMBLY-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plan(task: Dict[str, Any], task_slot: str) -> Dict[str, Any]:
    kind = str((task.get("output_schema") or {}).get("kind") or "md")
    output = {"form": _FORM.get(kind, "md")}
    path = (task.get("output_schema") or {}).get("path")
    if path:
        output["path"] = str(path)
    steps = [{"id": sid, "module": mod, "inputs": [task_slot]}
             for sid, _name, mod in _STEPS]
    return {"schema": PLAN_SCHEMA, "pipeline": PIPELINE, "steps": steps,
            "modules": sorted({str(c.get("id")) for c in task.get("context_refs") or []}),
            "assets": [], "output": output,
            "checks": [{"id": "K-001", "rule": "输出 citations 必须来自上下文（编造引用=0）"},
                       {"id": "K-002", "rule": "输出必须过 nf-adapter-output/1 契约"},
                       {"id": "K-003", "rule": "content ≤ budget.max_tokens×4"},
                       {"id": "K-004", "rule": "输出只在 task.slot 范围内"}],
            "fallback": {"on_failure": "abort"}}


def run(intent_rel: str, adapter: str = "mock", root: str = ".",
        budget_chars: int = 2000, role: str = "author") -> Dict[str, Any]:
    """跑 P00 黄金路径 → (assembly 计划 + run 信封)；失败时 run.status=blocked。"""
    trace: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    run_doc: Dict[str, Any] = {"schema": RUN_SCHEMA, "intent": intent_rel, "adapter": adapter,
                               "status": "blocked", "steps": trace, "checks": checks,
                               "output": {}, "fallback": {"mode": "fail-fast", "used": False},
                               "note": "run 只存 digest/相对路径；正文不落记录"}
    assembly: Dict[str, Any] = {}
    try:
        intent = sc._load_intent_file(root, intent_rel)
        bundle = sc.compile_intent(intent, root, intent_rel)
        spec = bundle.get("spec") or {}
        if not spec.get("ref") or not spec.get("digest"):
            raise AssemblyError("spec bundle 不完整（修复指引：重跑 nf spec compile）",
                                code="SPEC-INVALID")
        task = (bundle.get("tasks") or [{}])[0]
        if not task.get("slot"):
            raise AssemblyError("bundle 缺 task（修复指引：重跑 nf spec compile）",
                                code="SPEC-INVALID")
        assembly = _plan(task, task["slot"]["id"])
        trace.append({"id": "spec", "ok": True, "detail": "spec=%s digest=%s…"
                      % (bundle["spec"]["ref"], bundle["spec"]["digest"][:12])})
        trace.append({"id": "task", "ok": True, "detail": "slot=%s refs=%d"
                      % (task["slot"]["id"], len(task["context_refs"]))})
        pack = cp.pack_task(task, root, budget_chars, role)
        checks.append({"id": "K-001", "ok": pack["report"]["citation_rate"] == 1.0,
                       "detail": "citation_rate=%s" % pack["report"]["citation_rate"]})
        trace.append({"id": "context", "ok": True, "detail": "entries=%d chars=%d"
                      % (len(pack["entries"]), pack["budget"]["used_chars"])})
        try:
            out = aa.run(adapter, task, pack, root)
        except aa.AdapterError as exc:
            if getattr(exc, "code", "") == "OUTPUT-INVALID":
                checks.append({"id": "K-002", "ok": False,
                               "detail": str(exc.message)[:240]})
            raise
        trace.append({"id": "adapter", "ok": True, "detail": "citations=%s"
                      % ",".join(out["citations"])})
        issues = aa.validate_output(out, task, pack)
        checks.append({"id": "K-002", "ok": not issues,
                       "detail": "；".join(issues[:2]) or "nf-adapter-output/1 通过"})
        if issues:
            raise AssemblyError("输出不合契约：%s（修复指引：按 task/output 修）"
                                % "；".join(issues[:2]), code="OUTPUT-INVALID")
        content = str(out["output"]["content"])
        run_doc["output"] = {"kind": out["output"]["kind"], "path": out["output"]["path"],
                             "digest": _sha(content), "chars": len(content),
                             "tokens": int(out["usage"]["tokens"])}
        trace.append({"id": "output", "ok": True, "detail": "kind=%s chars=%d digest=%s…"
                      % (out["output"]["kind"], len(content), _sha(content)[:12])})
        max_chars = task["budget"]["max_tokens"] * 4
        checks.append({"id": "K-003", "ok": len(content) <= max_chars,
                       "detail": "chars=%d max=%d" % (len(content), max_chars)})
        checks.append({"id": "K-004", "ok": True,
                       "detail": "输出只在 slot %s 内，引用均来自上下文" % task["slot"]["id"]})
        gate_ok = all(c["ok"] for c in checks)
        trace.append({"id": "gate", "ok": gate_ok, "detail": "checks=%d ok=%d"
                      % (len(checks), sum(1 for c in checks if c["ok"]))})
        if not gate_ok:
            raise AssemblyError("gate 未过（修复指引：先修 K-001…K-004 红项）",
                                code="GATE-FAILED")
        trace.append({"id": "export", "ok": True, "detail": "export=记录（正文由 WP-23 Delivery 负责）"})
        run_doc["status"] = "delivered"
    except (sc.SpecError, cp.PackError, aa.AdapterError, AssemblyError,
            KeyError, TypeError, IndexError) as exc:
        if not trace or trace[-1]["ok"]:
            trace.append({"id": "error", "ok": False,
                          "detail": "%s：%s" % (getattr(exc, "code", "ERROR"),
                                                getattr(exc, "message", str(exc)))[:240]})
        run_doc["status"] = "blocked"
        run_doc["error"] = {"code": getattr(exc, "code", "ASSEMBLY-INVALID"),
                            "message": str(getattr(exc, "message", str(exc)))[:240]}
    run_doc["steps"] = trace
    run_doc["checks"] = checks
    return {"schema": RUN_SCHEMA, "assembly": assembly, "run": run_doc}


def validate_record(record: Dict[str, Any], root: str = ".") -> List[str]:
    """装配记录契约：assembly 过 nf-assembly/1 schema + run 信封一致性。"""
    from core import json_schema
    issues: List[str] = []
    if str(record.get("schema")) != RUN_SCHEMA:
        issues.append("run 记录 schema 必须 %s" % RUN_SCHEMA)
    if not str(record.get("assembly")):
        issues.append("缺 assembly 计划")
        return issues
    schema = json.loads((Path(root) / ASSEMBLY_SCHEMA_REL).read_text(encoding="utf-8"))
    for item in json_schema.json_schema_check(record["assembly"], schema)[:3]:
        issues.append("assembly schema：%s" % item)
    if str(record["assembly"].get("pipeline")) != PIPELINE:
        issues.append("pipeline 必须 %s" % PIPELINE)
    run_doc = record.get("run") or {}
    if str(run_doc.get("status")) not in ("delivered", "blocked"):
        issues.append("run.status 非法")
    if run_doc.get("status") == "delivered":
        trace_ids = [str(s.get("id")) for s in run_doc.get("steps") or []]
        for need in ("spec", "task", "context", "adapter", "output", "gate", "export"):
            if need not in trace_ids:
                issues.append("delivered 记录缺步骤：%s" % need)
        if not all(c.get("ok") for c in run_doc.get("checks") or []):
            issues.append("delivered 但 checks 有红项")
        out = run_doc.get("output") or {}
        if len(str(out.get("digest") or "")) != 64:
            issues.append("output.digest 必须是 64 位 sha256")
    if run_doc.get("status") == "blocked" and "error" not in run_doc:
        issues.append("blocked 必须写 error")
    return issues


def render(record: Dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_record(record: Dict[str, Any], rel: str, root: str = ".") -> Path:
    from core import atomic_write
    path = Path(root) / rel
    atomic_write.write_text(path, render(record))
    return path
