"""nf-entity/1 类型化实体：结构校验 + 类型注册表/准入（FR-A4-01 / FR-A4-02）。

冻结依据：ADR-009 与向量集 entity 族；结构定义在 protocol/trust/entity.schema.json。
判定顺序（fail-closed，顺序固定）：
1. 结构：实体必须过实体 schema（未知字段/缺必填/格式错 → SCHEMA-INVALID）；
2. issuer：issuer 必须在 policy.issuers 内（不在册 → ISSUER-UNKNOWN）；
3. 类型：entity.type 必须在该 issuer 的 types 内（未授权 → TYPE-NOT-ALLOWED）。
未知一律拒绝；不做「猜类型」或「按名字前缀放行」。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema

GUIDE = "修复指引："
ENTITY_SCHEMA_REL = "protocol/trust/entity.schema.json"
REASON_SCHEMA = "SCHEMA-INVALID"
REASON_ISSUER = "ISSUER-UNKNOWN"
REASON_TYPE = "TYPE-NOT-ALLOWED"
REASON_POLICY = "POLICY-INVALID"


def load_schema(root: str = ".", rel: str = ENTITY_SCHEMA_REL) -> dict:
    """读冻结的实体 schema（缺件/坏 JSON 直接抛，不静默降级）。"""
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺实体 schema：{rel}（{GUIDE}先落 protocol/trust/entity.schema.json）")
    doc = json_doc.load(path, dict, what=rel)
    if str((doc.get("properties") or {}).get("schema", {}).get("const")) != "nf-entity/1":
        raise ValueError(f"{rel} 不是 nf-entity/1 定义（{GUIDE}核对 schema.const）")
    return doc


def validate_entity(entity: Any, schema: dict | None = None) -> list:
    """结构校验：返回问题清单（空 = 结构合法）。消息带修复指引。"""
    if schema is None:
        raise ValueError(f"缺 schema（{GUIDE}传入 load_schema 的返回值，避免隐式读盘）")
    return json_schema.json_schema_check(entity, schema)


def resolve_issuer(policy: Any, issuer_id: str) -> dict | None:
    """在策略里解析 issuer；策略形状不对返回 None（由调用方判 POLICY-INVALID）。"""
    if not isinstance(policy, dict):
        return None
    issuers = policy.get("issuers")
    if not isinstance(issuers, list):
        return None
    for item in issuers:
        if isinstance(item, dict) and str(item.get("id") or "") == str(issuer_id or ""):
            return item
    return None


def _policy_shape_ok(policy: Any) -> bool:
    if not isinstance(policy, dict):
        return False
    issuers = policy.get("issuers")
    return isinstance(issuers, list) and all(
        isinstance(item, dict) and str(item.get("id") or "") for item in issuers)


def admissibility(entity: Any, policy: Any, schema: dict | None = None) -> dict:
    """准入判定：通过 = {"admissible": True}；拒绝 = {"admissible": False, "reason": 码}。"""
    if schema is None:
        raise ValueError(f"缺 schema（{GUIDE}传入 load_schema 的返回值）")
    if not _policy_shape_ok(policy):
        return {"admissible": False, "reason": REASON_POLICY}
    if validate_entity(entity, schema):
        return {"admissible": False, "reason": REASON_SCHEMA}
    issuer = resolve_issuer(policy, str(entity.get("issuer") or ""))
    if issuer is None:
        return {"admissible": False, "reason": REASON_ISSUER}
    types = issuer.get("types")
    if not isinstance(types, list) or entity.get("type") not in types:
        return {"admissible": False, "reason": REASON_TYPE}
    return {"admissible": True}



# ---------------------------------------------------------------------------
# G3：类型注册表 + 组合准入（nf-type-registry/1；ADR-009 的类型面）
# ---------------------------------------------------------------------------
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


def validate_type_registry(doc: Any, schema: dict | None = None,
                           root: str = ".") -> tuple:
    """类型注册表体检 → (issues, stats)。结构 + 语义（唯一/目标存在/无自环/无环/max_refs）。"""
    issues: list = []
    stats = {"types": 0, "edges": 0}
    check_schema = schema if schema is not None else load_type_schema(root)
    problems = json_schema.json_schema_check(doc, check_schema)
    if problems:
        return ([f"schema：{problems[0]}"], stats)
    types: dict = {}
    for index, item in enumerate(doc.get("types") or []):
        tid = str(item.get("id") or "")
        if tid in types:
            issues.append(f"types[{index}] id 重复：{tid}（{GUIDE}类型 id 全表唯一）")
        types[tid] = item
        stats["types"] += 1
        stats["edges"] += len(item.get("compose_with") or [])
    for tid, item in types.items():
        for target in item.get("compose_with") or []:
            if target == tid:
                issues.append(f"{tid} 的 compose_with 含自环（{GUIDE}组合图必须无环）")
            elif target not in types:
                issues.append(f"{tid} 的 compose_with 指向不存在类型：{target}"
                              f"（{GUIDE}先注册目标类型或删该边）")
        refs = item.get("allowed_ref_kinds")
        for kind in refs or []:
            if kind not in REF_KINDS:
                issues.append(f"{tid} 的 allowed_ref_kinds 越界：{kind!r}"
                              f"（{GUIDE}取 {REF_KINDS}）")
        if refs is not None and not refs:
            issues.append(f"{tid} 的 allowed_ref_kinds 为空（{GUIDE}至少 1 种引用类别）")
        max_refs = item.get("max_refs")
        if max_refs is not None and (int(max_refs) < 0 or int(max_refs) > 1024):
            issues.append(f"{tid} 的 max_refs 越界：{max_refs}")
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


def typed_admissibility(entity: Any, type_registry: dict, policy: Any,
                        issuer_registry: dict, schema: dict | None = None,
                        type_schema: dict | None = None,
                        issuer_schema: dict | None = None,
                        root: str = ".") -> dict:
    """类型化准入：在既有 issuer/type 准入之上叠加类型注册表 + issuer registry 规则。

    顺序固定（fail-closed）：结构 → policy/issuer/type → 类型注册表有效 → issuer 注册 →
    type 存在 → issuer kind 授权 → issuer 显式授权 → 有效期窗 → refs（数量/类别/重复/自引）。
    """
    from core.trust import keys as tk
    if schema is None:
        schema = load_schema(root)
    base = admissibility(entity, policy, schema)
    if not base.get("admissible"):
        return base
    issues, _stats = validate_type_registry(type_registry, type_schema, root)
    if issues:
        return {"admissible": False, "reason": REASON_TYPE_REGISTRY,
                "detail": issues[0]}
    type_id = str(entity.get("type") or "")
    entry = _type_entry(type_registry, type_id)
    if entry is None:
        return {"admissible": False, "reason": REASON_TYPE_UNKNOWN}
    issuer_id = str(entity.get("issuer") or "")
    if issuer_schema is not None:
        problems = json_schema.json_schema_check(issuer_registry, issuer_schema)
        if problems:
            return {"admissible": False, "reason": REASON_TYPE_REGISTRY,
                    "detail": problems[0]}
    kind = _issuer_kind(issuer_registry, issuer_id)
    if not kind:
        return {"admissible": False, "reason": REASON_ISSUER_NOT_REGISTERED}
    if kind not in (entry.get("allowed_issuer_kinds") or []):
        return {"admissible": False, "reason": REASON_ISSUER_KIND}
    allowed_issuers = entry.get("allowed_issuers")
    if allowed_issuers and issuer_id not in allowed_issuers:
        return {"admissible": False, "reason": REASON_ISSUER_NOT_AUTHORED}
    validity = entity.get("validity") or {}
    if (isinstance(validity, dict) and validity.get("not_before")
            and validity.get("not_after")
            and str(validity["not_before"]) > str(validity["not_after"])):
        return {"admissible": False, "reason": REASON_VALIDITY}
    refs = entity.get("refs") or []
    max_refs = entry.get("max_refs")
    if max_refs is not None and len(refs) > int(max_refs):
        return {"admissible": False, "reason": REASON_REFS_TOO_MANY}
    seen = set()
    subject_digest = str((entity.get("subject") or {}).get("digest") or "")
    allowed_kinds = entry.get("allowed_ref_kinds")
    for ref in refs:
        ref_kind = str(ref.get("kind") or "")
        ref_digest = str(ref.get("digest") or "")
        if allowed_kinds is not None and ref_kind not in allowed_kinds:
            return {"admissible": False, "reason": REASON_REF_KIND}
        if ref_digest == subject_digest:
            return {"admissible": False, "reason": REASON_SELF_REF}
        if ref_digest in seen:
            return {"admissible": False, "reason": REASON_DUP_REF}
        seen.add(ref_digest)
    del tk
    return {"admissible": True, "type": type_id}


def composition_check(entities: list, type_registry: dict, type_schema: dict | None = None,
                      max_depth: int = MAX_COMPOSE_DEPTH, root: str = ".") -> dict:
    """组合体检：ref 必须可解析到给定实体；类型对必须在 compose_with 内；深度有界、无环。"""
    issues, _stats = validate_type_registry(type_registry, type_schema, root)
    if issues:
        return {"ok": False, "issues": [{"code": REASON_TYPE_REGISTRY, "message": issues[0],
                                         "fix": "先修类型注册表"}]}
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
    adjacency: dict = {}
    for digest, entity in by_digest.items():
        type_id = str(entity.get("type") or "")
        entry = _type_entry(type_registry, type_id)
        if entry is None:
            issues.append({"code": REASON_TYPE_UNKNOWN, "message": f"实体类型未注册：{type_id}",
                           "fix": "先在 nf-type-registry/1 注册该类型"})
            continue
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
                               "message": f"{type_id} 不允许组合 {target_type}",
                               "fix": "在类型注册表显式声明该组合边，或不要组合"})
                continue
            adjacency.setdefault(digest, []).append(target_digest)
    limit = max(1, min(int(max_depth), 256))
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
                issues.append({"code": reason, "message": f"组合图问题：{reason}",
                               "fix": "组合关系必须是有向无环图且深度有界"})
                break
    return {"ok": not issues, "issues": issues, "entities": len(by_digest)}
