"""Spec Compiler（WP-11）：intent → `nf-spec/1` → `nf-task/1`（有界任务）。

纪律（WK-07 / PR-02 / §4A INV-03/04）：
- **确定性**：同 intent + 同 Wiki 页 digest → 编译逐字节一致（含 sort_keys canonical）；
- **拒绝未知**：未知 kind / 不在场的 wiki id / 坏 intent → exit 2 + 修复指引（不自由生成）；
- **有界**：任务只含 slot/spec_refs/context_refs/output_schema/acceptance/budget，budget 必填；
- **任务图无环**：上下文页之间的 relations 组成图，编译前做拓扑检查（有环即拒）；
- 产物只引用 Wiki 页（id+digest）与 spec（ref+digest），不复制正文。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

INTENT_SCHEMA = "nf-intent/1"
BUNDLE_SCHEMA = "nf-spec-bundle/1"
SPEC_SCHEMA = "nf-spec/1"
TASK_SCHEMA = "nf-task/1"
PAGES_REL = "wiki/pages.json"
SPEC_SCHEMA_REL = "protocol/production/spec.schema.json"
TASK_SCHEMA_REL = "protocol/production/task.schema.json"
KINDS = ("protocol", "module", "pipeline", "asset", "domain", "output")
GUIDE = "修复指引："
CODES = ("SPEC-KIND-UNKNOWN", "WIKI-ID-UNKNOWN", "INTENT-INVALID", "TASK-GRAPH-CYCLE")


class SpecError(Exception):
    """带错误码与修复指引的编译拒绝（CLI exit 2）。

    参数顺序：**消息在前**（含「修复指引：…」，满足 check33 raise 审计），错误码用关键字。
    """

    def __init__(self, message: str, code: str = "INTENT-INVALID", fix: str = "") -> None:
        super().__init__(message)
        self.code = code if code in CODES else "INTENT-INVALID"
        self.message = message
        self.fix = fix or (GUIDE + "按 nf-intent/1 改 intent（kind/goal/wiki_ids/constraints/budget）")


def _canonical(doc: Any) -> bytes:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _digest(doc: Any) -> str:
    return hashlib.sha256(_canonical(doc)).hexdigest()


def _pages(root: str) -> Dict[str, Dict[str, Any]]:
    path = Path(root) / PAGES_REL
    if not path.is_file():
        raise SpecError(
            "缺 %s（Wiki 未编译；修复指引：先跑 python scripts/nf.py wiki build --write）"
            % PAGES_REL, code="WIKI-ID-UNKNOWN",
            fix=GUIDE + "先跑 python scripts/nf.py wiki build --write")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {str(p.get("id")): p for p in doc.get("pages") or [] if isinstance(p, dict)}


def parse_intent(doc: Dict[str, Any]) -> List[str]:
    """intent 结构判据（返回问题清单；不抛）。"""
    issues: List[str] = []
    if not isinstance(doc, dict):
        return ["intent 必须是 JSON 对象"]
    if str(doc.get("schema")) != INTENT_SCHEMA:
        issues.append("intent.schema 必须为 %s" % INTENT_SCHEMA)
    if str(doc.get("kind")) not in KINDS:
        issues.append("intent.kind 非法：%s（可选 %s）" % (doc.get("kind"), "/".join(KINDS)))
    if not str(doc.get("goal") or "").strip():
        issues.append("intent.goal 必填（本任务要达成什么）")
    ids = doc.get("wiki_ids")
    if not isinstance(ids, list) or not ids:
        issues.append("intent.wiki_ids 必填（非空数组，指向 Wiki 页 id）")
    allowed = {"schema", "kind", "goal", "wiki_ids", "constraints", "budget", "output"}
    extra = sorted(set(doc) - allowed)
    if extra:
        issues.append("intent 含未知字段：%s（unknown 即拒）" % extra)
    cons = doc.get("constraints") or []
    if not isinstance(cons, list) or not cons or not all(
            isinstance(x, str) and x.strip() for x in cons):
        issues.append("intent.constraints 必须是非空字符串数组（硬约束）")
    budget = doc.get("budget") or {}
    if not isinstance(budget, dict):
        issues.append("intent.budget 必须是对象")
    else:
        if not isinstance(budget.get("max_tokens"), int) or budget.get("max_tokens", 0) < 1:
            issues.append("intent.budget.max_tokens 必须是 ≥1 的整数")
        if "max_steps" in budget and (not isinstance(budget["max_steps"], int)
                                      or budget["max_steps"] < 1):
            issues.append("intent.budget.max_steps 必须是 ≥1 的整数")
    return issues


def _load_intent_file(root: str, rel: str) -> Dict[str, Any]:
    path = Path(root) / rel
    if not path.is_file():
        raise SpecError(
            "缺 intent 文件：%s（修复指引：用 --intent FILE 指向 nf-intent/1 JSON）" % rel,
            fix=GUIDE + "用 --intent FILE 指向 nf-intent/1 JSON")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpecError(
            "intent 不可解析：%s（修复指引：修 JSON（UTF-8、无注释）后重试）" % exc,
            fix=GUIDE + "修 JSON（UTF-8、无注释）后重试") from exc


def task_graph_issues(pages: Dict[str, Dict[str, Any]], ids: List[str]) -> List[str]:
    """上下文页 relations 图：端点必须在选中集内，且无环（拓扑检查）。"""
    issues: List[str] = []
    selected = [pid for pid in ids if pid in pages]
    edges = []
    for pid in selected:
        for rel in pages[pid].get("relations") or []:
            target = str((rel or {}).get("target"))
            if target in selected:
                edges.append((pid, target))
    nodes = {pid: set() for pid in selected}
    for src, dst in edges:
        nodes[src].add(dst)
    state: Dict[str, int] = {}

    def visit(node: str, stack: List[str]) -> None:
        if state.get(node) == 1:
            cyc = stack[stack.index(node):] + [node] if node in stack else [node, node]
            issues.append("任务图有环：%s（%s 拆掉循环引用）" % ("→".join(cyc), GUIDE))
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        stack.append(node)
        for nxt in sorted(nodes.get(node, ())):
            visit(nxt, stack)
        stack.pop()
        state[node] = 2

    for pid in sorted(selected):
        visit(pid, [])
    return issues


def compile_intent(intent: Dict[str, Any], root: str = ".",
                   intent_rel: Optional[str] = None) -> Dict[str, Any]:
    """编译 intent → bundle（确定性）；不合法任一项抛 SpecError（exit 2）。"""
    issues = parse_intent(intent)
    if issues:
        raise SpecError(
            "；".join(issues[:3])
            + "（修复指引：按 nf-intent/1 改 kind/goal/wiki_ids/constraints/budget）")
    pages = _pages(root)
    ids = [str(x) for x in intent["wiki_ids"]]
    missing = [pid for pid in ids if pid not in pages]
    if missing:
        raise SpecError(
            "Wiki 页不在场：%s（修复指引：先编译 Wiki 或改 wiki_ids）" % missing[:3],
            code="WIKI-ID-UNKNOWN",
            fix=GUIDE + "先编译 Wiki 或改 wiki_ids（nf wiki search 查 id）")
    graph_issues = task_graph_issues(pages, ids)
    if graph_issues:
        raise SpecError(
            graph_issues[0] + "（修复指引：拆掉选中页之间的循环引用）",
            code="TASK-GRAPH-CYCLE")
    kind = str(intent["kind"])
    anchor = pages[ids[0]]
    ref = "%s:%s" % (kind, ids[0])
    constraint = [str(x) for x in intent["constraints"]]
    spec_src = {"kind": kind, "ref": ref, "wiki_ids": ids,
                "constraints": constraint}
    spec = {"schema": SPEC_SCHEMA, "kind": kind, "ref": ref,
            "digest": _digest(spec_src), "constraints": constraint, "version": 1}
    budget = {"max_tokens": int(intent["budget"]["max_tokens"])}
    if isinstance(intent["budget"].get("max_steps"), int):
        budget["max_steps"] = int(intent["budget"]["max_steps"])
    tasks: List[Dict[str, Any]] = []
    for idx, pid in enumerate(ids):
        page = pages[pid]
        slug = pid.replace("wiki:", "").replace("/", "-").replace(":", "-")
        tasks.append({
            "schema": TASK_SCHEMA,
            "slot": {"id": "slot:" + slug, "kind": "section", "max_items": 1},
            "spec_refs": [{"ref": ref, "digest": spec["digest"]}],
            "context_refs": [{"id": pid,
                              "digest": str((page.get("provenance") or {}).get("digest"))}],
            "output_schema": {"kind": "md", "path": "out/%s.md" % slug},
            "acceptance": [{"id": "A-001",
                            "rule": "输出必须引用 Wiki 页 %s 的 spec_ref；不得超出 slot 范围" % pid},
                           {"id": "A-002",
                            "rule": "硬约束逐条可查：%s" % "；".join(constraint[:3])}],
            "budget": dict(budget),
        })
    bundle = {"schema": BUNDLE_SCHEMA, "spec": spec, "tasks": tasks,
              "graph": {"nodes": ids,
                        "edges": [{"from": str(r.get("target")),
                                   "kind": str(r.get("kind")), "to": pid}
                                  for pid in ids
                                  for r in (pages[pid].get("relations") or [])
                                  if str(r.get("target")) in ids]},
              "intent_digest": _digest(intent),
              "intent": intent_rel or ""}
    return bundle


def render(bundle: Dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def validate_bundle(bundle: Dict[str, Any], root: str = ".") -> List[str]:
    """用生产 schema 校验 spec/task，并检查引用可解析。"""
    from core import json_schema
    issues: List[str] = []
    spec_schema = json.loads((Path(root) / SPEC_SCHEMA_REL).read_text(encoding="utf-8"))
    task_schema = json.loads((Path(root) / TASK_SCHEMA_REL).read_text(encoding="utf-8"))
    spec = bundle.get("spec") or {}
    for item in json_schema.json_schema_check(spec, spec_schema)[:2]:
        issues.append("spec schema：%s" % item)
    pages = _pages(root)
    for task in bundle.get("tasks") or []:
        for item in json_schema.json_schema_check(task, task_schema)[:2]:
            issues.append("task schema：%s" % item)
        for ctx in task.get("context_refs") or []:
            pid = str(ctx.get("id"))
            if pid not in pages:
                issues.append("task context_ref 不在场：%s" % pid)
            elif str(ctx.get("digest")) != str((pages[pid].get("provenance") or {}).get("digest")):
                issues.append("task context_ref digest 与 Wiki 页不一致：%s" % pid)
        for sref in task.get("spec_refs") or []:
            if str(sref.get("ref")) != str(spec.get("ref")):
                issues.append("task spec_ref 与 spec.ref 不一致")
    return issues
