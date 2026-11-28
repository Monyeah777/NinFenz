"""entity 类型注册表 / 组合准入内部件（对外只经 core.trust.entity 门面导入）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core import json_doc, json_schema

GUIDE = "修复指引："


TYPE_REGISTRY_SCHEMA_REL = "protocol/trust/type-registry.schema.json"
TYPE_REGISTRY_SCHEMA = "nf-type-registry/1"
ISSUER_KINDS = ("human", "service", "ai-agent", "institution")
REF_KINDS = ("claim", "evidence", "process-step", "bundle", "card", "artifact", "context")
MAX_COMPOSE_DEPTH = 32
REASON_TYPE_REGISTRY = "TYPE-REGISTRY-INVALID"
REASON_TYPE_UNKNOWN = "TYPE-UNKNOWN"
REASON_ISSUER_NOT_REGISTERED = "ISSUER-NOT-REGISTERED"
REASON_ISSUER_KIND = "ISSUER-KIND-NOT-ALLOWED"
REASON_ISSUER_NOT_AUTHORED = "ISSUER-NOT-AUTHORED-FOR-TYPE"
REASON_REFS_TOO_MANY = "REFS-TOO-MANY"
REASON_REF_KIND = "REF-KIND-NOT-ALLOWED"
REASON_DUP_REF = "DUPLICATE-REF"
REASON_SELF_REF = "SELF-REFERENCE"
REASON_VALIDITY = "VALIDITY-WINDOW-INVALID"
REASON_REF_UNRESOLVED = "REF-UNRESOLVED"
REASON_COMPOSE = "COMPOSE-NOT-ALLOWED"
REASON_CYCLE = "COMPOSITION-CYCLE"
REASON_DEPTH = "COMPOSITION-TOO-DEEP"


def load_type_schema(root: str = ".", rel: str = TYPE_REGISTRY_SCHEMA_REL) -> dict:
    """读冻结的类型注册表 schema（缺件/坏 JSON 直接抛）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺类型注册表 schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != TYPE_REGISTRY_SCHEMA:
        raise ValueError(f"{rel} 不是 {TYPE_REGISTRY_SCHEMA} 定义（{GUIDE}核对 schema.const）")
    return doc


def load_type_registry(path: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺类型注册表：{path}（{GUIDE}传存在且 schema 正确的 JSON）")
    return json_doc.load(target, dict, what="type registry")


def _cycle_in_compose(types: dict) -> list:
    """返回环路径（空 = DAG）。组合图必须无环，否则「A 引用 B、B 引用 A」会绕开准入。"""
    state: dict = {}
    stack: list = []

    def visit(node: str) -> list:
        state[node] = 1
        stack.append(node)
        for child in types[node].get("compose_with") or []:
            if child not in types:
                continue
            if state.get(child) == 1:
                return stack[stack.index(child):] + [child]
            if state.get(child) is None:
                found = visit(child)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return []

    for node in types:
        if state.get(node) is None:
            found = visit(node)
            if found:
                return found
    return []


def _type_entries(doc: Any, issues: list, stats: dict) -> dict:
    types: dict = {}
    for index, item in enumerate(doc.get("types") or []):
        tid = str(item.get("id") or "")
        if tid in types:
            issues.append(f"types[{index}] id 重复：{tid}（{GUIDE}类型 id 全表唯一）")
        types[tid] = item
        stats["types"] += 1
        stats["edges"] += len(item.get("compose_with") or [])
    return types


def _compose_edge_issues(tid: str, item: dict, types: dict) -> list:
    issues: list = []
    for target in item.get("compose_with") or []:
        if target == tid:
            issues.append(f"{tid} 的 compose_with 含自环（{GUIDE}组合图必须无环）")
        elif target not in types:
            issues.append(f"{tid} 的 compose_with 指向不存在类型：{target}"
                          f"（{GUIDE}先注册目标类型或删该边）")
    return issues


def _ref_kind_issues(tid: str, item: dict) -> list:
    refs = item.get("allowed_ref_kinds")
    issues: list = []
    for kind in refs or []:
        if kind not in REF_KINDS:
            issues.append(f"{tid} 的 allowed_ref_kinds 越界：{kind!r}"
                          f"（{GUIDE}取 {REF_KINDS}）")
    if refs is not None and not refs:
        issues.append(f"{tid} 的 allowed_ref_kinds 为空（{GUIDE}至少 1 种引用类别）")
    return issues


def _max_refs_issue(tid: str, item: dict) -> list:
    max_refs = item.get("max_refs")
    if max_refs is not None and (int(max_refs) < 0 or int(max_refs) > 1024):
        return [f"{tid} 的 max_refs 越界：{max_refs}"]
    return []


def _type_edges_issues(types: dict) -> list:
    issues: list = []
    for tid, item in types.items():
        issues += _compose_edge_issues(tid, item, types)
        issues += _ref_kind_issues(tid, item)
        issues += _max_refs_issue(tid, item)
    return issues


def validate_type_registry(doc: Any, schema: dict | None = None,
                           root: str = ".") -> tuple:
    """类型注册表体检 → (issues, stats)。结构 + 语义（唯一/目标存在/无自环/无环/max_refs）。"""
    issues: list = []
    stats = {"types": 0, "edges": 0}
    check_schema = schema if schema is not None else load_type_schema(root)
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        return ([f"schema：{problems[0]}"], stats)
    types = _type_entries(doc, issues, stats)
    issues += _type_edges_issues(types)
    cycle = _cycle_in_compose(types)
    if cycle:
        issues.append(f"compose_with 存在环：{' -> '.join(cycle)}"
                      f"（{GUIDE}组合关系必须是 DAG）")
    return issues, stats


def _type_entry(registry: dict, type_id: str) -> dict | None:
    for item in (registry or {}).get("types") or []:
        if str(item.get("id")) == type_id:
            return item
    return None


def _issuer_kind(issuer_registry: dict, issuer_id: str) -> str:
    from core.trust import keys as tk
    resolved = tk.resolve_issuer(issuer_registry, issuer_id)
    if not resolved.get("ok"):
        return ""
    return str((resolved.get("issuer") or {}).get("kind") or "")


@dataclass(frozen=True)
class AdmissibilityOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    schema: dict | None = None
    type_schema: dict | None = None
    issuer_schema: dict | None = None
    root: str = '.'



def _registry_failure(type_registry: dict, type_schema: dict | None, root: str):
    issues, _stats = validate_type_registry(type_registry, type_schema, root)
    if issues:
        return {"admissible": False, "reason": REASON_TYPE_REGISTRY, "detail": issues[0]}
    return None


def _type_check(entity: Any, type_registry: dict) -> tuple[str, dict | None, dict | None]:
    type_id = str(entity.get("type") or "")
    entry = _type_entry(type_registry, type_id)
    if entry is None:
        return type_id, None, {"admissible": False, "reason": REASON_TYPE_UNKNOWN}
    return type_id, entry, None


def _issuer_schema_failure(issuer_registry: dict, issuer_schema: dict | None):
    if issuer_schema is None:
        return None
    problems = json_schema.json_schema_check(issuer_registry, issuer_schema)
    if problems:
        return {"admissible": False, "reason": REASON_TYPE_REGISTRY, "detail": problems[0]}
    return None


def _issuer_failure(entity: Any, entry: dict, issuer_registry: dict):
    issuer_id = str(entity.get("issuer") or "")
    kind = _issuer_kind(issuer_registry, issuer_id)
    if not kind:
        return {"admissible": False, "reason": REASON_ISSUER_NOT_REGISTERED}
    if kind not in (entry.get("allowed_issuer_kinds") or []):
        return {"admissible": False, "reason": REASON_ISSUER_KIND}
    allowed_issuers = entry.get("allowed_issuers")
    if allowed_issuers and issuer_id not in allowed_issuers:
        return {"admissible": False, "reason": REASON_ISSUER_NOT_AUTHORED}
    return None


def _validity_failure(entity: Any):
    validity = entity.get("validity") or {}
    if (isinstance(validity, dict) and validity.get("not_before")
            and validity.get("not_after")
            and str(validity["not_before"]) > str(validity["not_after"])):
        return {"admissible": False, "reason": REASON_VALIDITY}
    return None


def _ref_issue(ref: dict, subject_digest: str, seen: set, allowed_kinds) -> str | None:
    ref_kind = str(ref.get("kind") or "")
    ref_digest = str(ref.get("digest") or "")
    if allowed_kinds is not None and ref_kind not in allowed_kinds:
        return REASON_REF_KIND
    if ref_digest == subject_digest:
        return REASON_SELF_REF
    if ref_digest in seen:
        return REASON_DUP_REF
    seen.add(ref_digest)
    return None


def _refs_failure(entity: Any, entry: dict):
    refs = entity.get("refs") or []
    max_refs = entry.get("max_refs")
    if max_refs is not None and len(refs) > int(max_refs):
        return {"admissible": False, "reason": REASON_REFS_TOO_MANY}
    seen = set()
    subject_digest = str((entity.get("subject") or {}).get("digest") or "")
    allowed_kinds = entry.get("allowed_ref_kinds")
    for ref in refs:
        issue = _ref_issue(ref, subject_digest, seen, allowed_kinds)
        if issue is not None:
            return {"admissible": False, "reason": issue}
    return None


def typed_admissibility(
    entity: Any,
    type_registry: dict,
    policy: Any,
    issuer_registry: dict,
    opts: AdmissibilityOptions | None = None,
) -> dict:
    """类型化准入：在既有 issuer/type 准入之上叠加类型注册表 + issuer registry 规则。

    顺序固定（fail-closed）：结构 → policy/issuer/type → 类型注册表有效 → issuer 注册 →
    type 存在 → issuer kind 授权 → issuer 显式授权 → 有效期窗 → refs（数量/类别/重复/自引）。
    """

    opts = opts if opts is not None else AdmissibilityOptions()
    from core.trust import keys as tk
    from core.trust.entity import _base_admissible

    del tk
    failure = _base_admissible(entity, policy, opts.schema, opts.root)
    if failure is not None:
        return failure
    failure = _registry_failure(type_registry, opts.type_schema, opts.root)
    if failure is not None:
        return failure
    type_id, entry, failure = _type_check(entity, type_registry)
    if failure is not None:
        return failure
    failure = _issuer_schema_failure(issuer_registry, opts.issuer_schema)
    if failure is not None:
        return failure
    failure = _issuer_failure(entity, entry, issuer_registry)
    if failure is not None:
        return failure
    failure = _validity_failure(entity)
    if failure is not None:
        return failure
    failure = _refs_failure(entity, entry)
    if failure is not None:
        return failure
    return {"admissible": True, "type": type_id}





def _entity_index(entities: list, issues: list) -> dict:
    by_digest = {}
    for entity in entities or []:
        digest = str((entity.get("subject") or {}).get("digest") or "")
        if not digest:
            issues.append({"code": REASON_TYPE_UNKNOWN, "message": "实体缺 subject.digest",
                           "fix": "补 subject.digest 或从组合集中移除"})
            continue
        if digest in by_digest:
            issues.append({"code": REASON_DUP_REF, "message": f"实体摘要重复：{digest}",
                           "fix": "同一摘要只能有一份实体"})
            continue
        by_digest[digest] = entity
    return by_digest


def _entity_edges(
    digest: str, entity: dict, entry: dict, by_digest: dict, issues: list
) -> list:
    edges = []
    for ref in entity.get("refs") or []:
        target_digest = str(ref.get("digest") or "")
        target = by_digest.get(target_digest)
        if target is None:
            issues.append({"code": REASON_REF_UNRESOLVED,
                           "message": f"{digest} 引用了未提供的实体：{target_digest}",
                           "fix": "组合集必须包含被引实体，或删该 ref"})
            continue
        target_type = str(target.get("type") or "")
        if target_type not in (entry.get("compose_with") or []):
            issues.append({"code": REASON_COMPOSE,
                           "message": f"{entry.get('id')} 不允许组合 {target_type}",
                           "fix": "在类型注册表显式声明该组合边，或不要组合"})
            continue
        edges.append(target_digest)
    return edges


def _adjacency(by_digest: dict, type_registry: dict, issues: list) -> dict:
    adjacency: dict = {}
    for digest, entity in by_digest.items():
        type_id = str(entity.get("type") or "")
        entry = _type_entry(type_registry, type_id)
        if entry is None:
            issues.append({"code": REASON_TYPE_UNKNOWN, "message": f"实体类型未注册：{type_id}",
                           "fix": "先在 nf-type-registry/1 注册该类型"})
            continue
        adjacency[digest] = _entity_edges(digest, entity, entry, by_digest, issues)
    return adjacency


def _cycle_reason(adjacency: dict, limit: int) -> str:
    state: dict = {}

    def walk(node: str, depth: int) -> str:
        if depth > limit:
            return REASON_DEPTH
        state[node] = 1
        for child in adjacency.get(node) or []:
            if state.get(child) == 1:
                return REASON_CYCLE
            if state.get(child) is None:
                found = walk(child, depth + 1)
                if found:
                    return found
        state[node] = 2
        return ""

    for node in adjacency:
        if state.get(node) is None:
            reason = walk(node, 1)
            if reason:
                return reason
    return ""


def composition_check(entities: list, type_registry: dict, type_schema: dict | None = None,
                      max_depth: int = MAX_COMPOSE_DEPTH, root: str = ".") -> dict:
    """组合体检：ref 必须可解析到给定实体；类型对必须在 compose_with 内；深度有界、无环。"""
    issues, _stats = validate_type_registry(type_registry, type_schema, root)
    if issues:
        return {"ok": False, "issues": [{"code": REASON_TYPE_REGISTRY, "message": issues[0],
                                         "fix": "先修类型注册表"}]}
    by_digest = _entity_index(entities, issues)
    adjacency = _adjacency(by_digest, type_registry, issues)
    limit = max(1, min(int(max_depth), 256))
    reason = _cycle_reason(adjacency, limit)
    if reason:
        issues.append({"code": reason, "message": f"组合图问题：{reason}",
                       "fix": "组合关系必须是有向无环图且深度有界"})
    return {"ok": not issues, "issues": issues, "entities": len(by_digest)}
