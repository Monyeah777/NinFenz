"""Agent Adapter 协议（WP-20）：有界任务 → 受契约约束的输出；2 个可替换 adapter + parity。

纪律（PR-03/PR-05 / §13A L4）：
- Adapter 只接收 `nf-task/1` 有界槽位（slot/spec_refs/context_refs/output_schema/acceptance/budget），
  **不得自由生成整篇**：输出 content 只由上下文页派生、受 budget 上限、引用必须来自 context_refs；
- 输出契约 `nf-adapter-output/1`：adapter/task_slot/output/citations/usage；编造引用=0；
- 两个 adapter（mock / local-template 子进程桩）跑同一 task 必须**同契约通过**（parity）；
- 失败语义：未知 adapter/坏 task/超时/越界 → 带修复指引的错误（exit 2 或 1）。
- 如实声明：`local-template` 是本地子进程桩，不是真实外部模型；真实外部 adapter 属外部操作（OPEN）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

OUTPUT_SCHEMA = "nf-adapter-output/1"
REPORT_SCHEMA = "nf-adapter-report/1"
TASK_SCHEMA = "nf-task/1"
TASK_SCHEMA_REL = "protocol/production/task.schema.json"
REPORT_REL = "results/adapter/adapter-report.json"
GUIDE = "修复指引："
TIMEOUT_S = 10
ADAPTERS: Dict[str, Dict[str, Any]] = {
    "mock": {"id": "mock", "kind": "in-process", "determinism": "strict",
             "cost": "zero", "desc": "确定性内存桩：按上下文页 summary 拼装 slot 内容"},
    "local-template": {"id": "local-template", "kind": "subprocess", "determinism": "strict",
                       "cost": "local-cpu", "desc": "本地子进程桩：同 spec 的独立实现（parity 对照）"},
}


class AdapterError(Exception):
    """带错误码的 adapter 拒绝（消息含修复指引，满足 check33 raise 审计）。"""

    def __init__(self, message: str, code: str = "ADAPTER-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def list_adapters() -> List[Dict[str, Any]]:
    return [dict(ADAPTERS[k]) for k in sorted(ADAPTERS)]


def _task_schema(root: str) -> Dict[str, Any]:
    path = Path(root) / TASK_SCHEMA_REL
    if not path.is_file():
        raise AdapterError("缺 task schema：%s（修复指引：先在仓库根运行）" % TASK_SCHEMA_REL,
                           code="TASK-INVALID")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_task(task: Dict[str, Any], root: str) -> None:
    from core import json_schema
    if not isinstance(task, dict) or str(task.get("schema")) != TASK_SCHEMA:
        raise AdapterError(
            "task 缺失或不是 nf-task/1（修复指引：先用 nf spec compile 生成任务）",
            code="TASK-INVALID")
    problems = json_schema.json_schema_check(task, _task_schema(root))
    if problems:
        raise AdapterError("task schema 不过：%s（修复指引：重编译 spec/task）"
                           % "；".join(problems[:3]), code="TASK-INVALID")
    slot = task.get("slot") or {}
    if not str(slot.get("id") or "").startswith("slot:"):
        raise AdapterError("task 缺有界槽位 id（修复指引：slot.id 必须 slot: 前缀）",
                           code="TASK-INVALID")
    if not task.get("context_refs"):
        raise AdapterError("task 缺 context_refs（修复指引：重新编译 spec/task 补上下文）",
                           code="TASK-INVALID")


def _budget(task: Dict[str, Any]) -> int:
    return int((task.get("budget") or {}).get("max_tokens") or 1)


def _context_ids(task: Dict[str, Any], pack: Optional[Dict[str, Any]]) -> List[str]:
    ids = [str((c or {}).get("id")) for c in task.get("context_refs") or []]
    if pack:
        ids = [str(e.get("id")) for e in pack.get("entries") or []]
    return ids


def _mock_output(task: Dict[str, Any], pack: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    entries = (pack or {}).get("entries") or []
    if not entries:
        raise AdapterError("空上下文无法产出（修复指引：先跑 Context Packer 打包）",
                           code="CONTEXT-EMPTY")
    lines = []
    for entry in entries:
        lines.append("## %s" % entry.get("id"))
        lines.append(str(entry.get("summary") or ""))
    content = "\n\n".join(lines)
    ids = [str(e.get("id")) for e in entries]
    return {"schema": OUTPUT_SCHEMA, "adapter": "mock", "task_slot": task["slot"]["id"],
            "output": {"kind": str((task.get("output_schema") or {}).get("kind") or "md"),
                       "path": str((task.get("output_schema") or {}).get("path") or "out.md"),
                       "content": content},
            "citations": ids,
            "usage": {"tokens": max(1, len(content) // 4), "steps": 1}}


def _local_template_output(task: Dict[str, Any], pack: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """子进程桩：把 task+pack 经 stdin 交给独立 Python 进程（同 spec 的另一实现）。"""
    payload = json.dumps({"task": task, "pack": pack or {}}, ensure_ascii=False)
    worker = (
        "import json,sys\n"
        "d=json.load(sys.stdin)\n"
        "task=d['task']; pack=d.get('pack') or {}\n"
        "entries=pack.get('entries') or []\n"
        "if not entries: print(json.dumps({'error':'CONTEXT-EMPTY'})); sys.exit(1)\n"
        "parts=[p.get('summary') or '' for p in entries]\n"
        "content='\\n\\n'.join('## '+str(p.get('id'))+'\\n'+str(p.get('summary') or '') "
        "for p in entries)\n"
        "out={'schema':'nf-adapter-output/1','adapter':'local-template',"
        "'task_slot':task['slot']['id'],"
        "'output':{'kind':str((task.get('output_schema') or {}).get('kind') or 'md'),"
        "'path':str((task.get('output_schema') or {}).get('path') or 'out.md'),"
        "'content':content},"
        "'citations':[str(p.get('id')) for p in entries],"
        "'usage':{'tokens':max(1,len(content)//4),'steps':1}}\n"
        "print(json.dumps(out, ensure_ascii=False))\n"
    )
    try:
        proc = subprocess.run([sys.executable, "-c", worker], input=payload,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise AdapterError("adapter 超时 >%ss（修复指引：缩短任务或调大超时）" % TIMEOUT_S,
                           code="ADAPTER-TIMEOUT") from None
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:]
        raise AdapterError("adapter 子进程失败：%s（修复指引：检查 adapter 输入/实现）"
                           % (tail[0] if tail else proc.returncode), code="ADAPTER-FAILED")
    try:
        out = json.loads(proc.stdout)
    except ValueError as exc:
        raise AdapterError("adapter 输出不可解析：%s（修复指引：输出必须是单个 JSON）" % exc,
                           code="ADAPTER-FAILED") from exc
    # 父进程统一 token 口径（子进程编码/平台差异不得影响报告确定性）
    content = str(((out.get("output") or {}).get("content")) or "")
    out.setdefault("usage", {})["tokens"] = max(1, len(content) // 4)
    return out


def run(adapter_id: str, task: Dict[str, Any], pack: Optional[Dict[str, Any]] = None,
        root: str = ".") -> Dict[str, Any]:
    _validate_task(task, root)
    if adapter_id not in ADAPTERS:
        raise AdapterError("未知 adapter：%s（修复指引：可选 %s）"
                           % (adapter_id, "/".join(sorted(ADAPTERS))), code="ADAPTER-UNKNOWN")
    out = _mock_output(task, pack) if adapter_id == "mock" else _local_template_output(task, pack)
    issues = validate_output(out, task, pack)
    if issues:
        raise AdapterError("adapter 输出不合契约：%s（修复指引：按 nf-adapter-output/1 修）"
                           % "；".join(issues[:3]), code="OUTPUT-INVALID")
    return out


def validate_output(out: Dict[str, Any], task: Dict[str, Any],
                    pack: Optional[Dict[str, Any]] = None) -> List[str]:
    issues: List[str] = []
    if str(out.get("schema")) != OUTPUT_SCHEMA:
        issues.append("output schema 必须 %s" % OUTPUT_SCHEMA)
    allowed = set(_context_ids(task, pack))
    cited = {str(c) for c in out.get("citations") or []}
    if not cited:
        issues.append("output 缺 citations")
    if cited - allowed:
        issues.append("编造引用（不在上下文内）：%s" % sorted(cited - allowed)[:3])
    content = str(((out.get("output") or {}).get("content")) or "")
    if not content.strip():
        issues.append("output.content 为空")
    max_chars = _budget(task) * 4
    if len(content) > max_chars:
        issues.append("output 超预算（%d > %d 字符）" % (len(content), max_chars))
    want_kind = str((task.get("output_schema") or {}).get("kind") or "")
    got_kind = str((out.get("output") or {}).get("kind") or "")
    if want_kind and got_kind != want_kind:
        issues.append("output.kind 与 task.output_schema 不符：%s != %s" % (got_kind, want_kind))
    usage = out.get("usage") or {}
    if int(usage.get("tokens") or 0) > _budget(task):
        issues.append("usage.tokens 超 budget")
    if str(out.get("task_slot")) != str((task.get("slot") or {}).get("id")):
        issues.append("output.task_slot 与 task 不一致")
    return issues


def parity_report(task: Dict[str, Any], pack: Optional[Dict[str, Any]] = None,
                  root: str = ".") -> Dict[str, Any]:
    """两 adapter 同 task 对比：都过同一契约 + citations 集一致 + 输出 kind 一致。"""
    rows = []
    issues: List[str] = []
    kinds = set()
    citations = []
    for aid in sorted(ADAPTERS):
        try:
            out = run(aid, task, pack, root)
        except AdapterError as exc:
            rows.append({"id": aid, "ok": False, "error": exc.code})
            issues.append("%s 失败：%s" % (aid, exc.code))
            continue
        rows.append({"id": aid, "ok": True,
                     "citations": sorted(str(c) for c in out.get("citations") or []),
                     "chars": len(str(((out.get("output") or {}).get("content")) or "")),
                     "tokens": int((out.get("usage") or {}).get("tokens") or 0)})
        kinds.add(str((out.get("output") or {}).get("kind")))
        citations.append(tuple(sorted(str(c) for c in out.get("citations") or [])))
    parity = len(citations) >= 2 and len(set(citations)) == 1 and len(kinds) == 1
    if not parity:
        issues.append("parity 不一致（citations/kind 不同）")
    return {"schema": REPORT_SCHEMA, "task_slot": str((task.get("slot") or {}).get("id")),
            "adapters": rows, "parity": parity, "issues": issues,
            "note": "local-template 是本地子进程桩（非真实外部模型）；真实外部 adapter 属外部操作（OPEN）"}


def render(report: Dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_report(report: Dict[str, Any], rel: str = REPORT_REL, root: str = ".") -> Path:
    from core import atomic_write
    path = Path(root) / rel
    atomic_write.write_text(path, render(report))
    return path
