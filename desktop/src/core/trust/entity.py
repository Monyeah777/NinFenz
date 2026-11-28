"""nf-entity/1 类型化实体：结构校验 + 类型注册表/准入（FR-A4-01 / FR-A4-02）。

冻结依据：ADR-009 与向量集 entity 族；结构定义在 protocol/trust/entity.schema.json。
判定顺序（fail-closed，顺序固定）：
1. 结构：实体必须过实体 schema（未知字段/缺必填/格式错 → SCHEMA-INVALID）；
2. issuer：issuer 必须在 policy.issuers 内（不在册 → ISSUER-UNKNOWN）；
3. 类型：entity.type 必须在该 issuer 的 types 内（未授权 → TYPE-NOT-ALLOWED）。
未知一律拒绝；不做「猜类型」或「按名字前缀放行」。
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _base_admissible(entity: Any, policy: Any, schema: dict | None, root: str):
    if schema is None:
        schema = load_schema(root)
    base = admissibility(entity, policy, schema)
    if not base.get("admissible"):
        return base
    return None


# 类型注册表 / 组合准入实现分片：本门面按原模块面显式再导出（API 不变）。
from core.trust._entity_types import (  # noqa: E402
    ISSUER_KINDS,
    MAX_COMPOSE_DEPTH,
    REF_KINDS,
    REASON_COMPOSE,
    REASON_CYCLE,
    REASON_DEPTH,
    REASON_DUP_REF,
    REASON_ISSUER_KIND,
    REASON_ISSUER_NOT_AUTHORED,
    REASON_ISSUER_NOT_REGISTERED,
    REASON_REF_KIND,
    REASON_REF_UNRESOLVED,
    REASON_REFS_TOO_MANY,
    REASON_SELF_REF,
    REASON_TYPE_REGISTRY,
    REASON_TYPE_UNKNOWN,
    REASON_VALIDITY,
    TYPE_REGISTRY_SCHEMA,
    TYPE_REGISTRY_SCHEMA_REL,
    AdmissibilityOptions,
    composition_check,
    load_type_registry,
    load_type_schema,
    typed_admissibility,
    validate_type_registry,
)
