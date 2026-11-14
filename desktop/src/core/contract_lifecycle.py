"""契约生命周期与义务（WP-30，G3）：nf-contract/1 状态义务 + 引用/消费策略。

为什么（方案 G3 WP-30）：contract schema 只有 status 字段，没有「不同状态各要什么证据/能否被
引用」的义务表——结果 draft 被当 active 用、retired 被静默引用都可能发生。本模块：
- 机读义务表 `protocol/contract_lifecycle.json`（states/义务/词表/义务→check 映射）；
- `check_contract(doc)` 按状态校验 nf-contract/1 已有字段（evidence/acceptance/constraints），
  不新增 schema 字段（schema additionalProperties=false）；
- `can_reference(status, new_reference)` 给出引用/消费策略（draft/retired=false，
  deprecated 只允许既有引用、禁止新增）；
- 义务必须可复算、错状态即红；不替代 WP-31 治理 verify / WP-32 附件模式。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_SCHEMA = "nf-contract-lifecycle/1"
REGISTRY_REL = "protocol/contract_lifecycle.json"
CONTRACT_SCHEMA_REL = "protocol/production/contract.schema.json"
GUIDE = "修复指引："


class LifecycleError(Exception):
    """义务/引用拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "LIFECYCLE-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REGISTRY_REL
    if not path.is_file():
        raise LifecycleError("缺 %s（修复指引：补登记状态义务表）" % REGISTRY_REL,
                             code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LifecycleError("%s 不可解析：%s（修复指引：修 JSON）" % (REGISTRY_REL, exc)) from exc
    if str(doc.get("schema")) != REGISTRY_SCHEMA:
        raise LifecycleError("registry schema 必须 %s" % REGISTRY_SCHEMA)
    return doc


def states(root: str = ".") -> Dict[str, Dict[str, Any]]:
    reg = load_registry(root)
    return {str(s.get("id")): s for s in reg.get("states") or [] if isinstance(s, dict)}


def can_reference(status: str, new_reference: bool = True, root: str = ".") -> bool:
    """引用/消费策略：draft/retired=false；deprecated 仅 existing-only（新引用=false）。"""
    table = states(root)
    state = table.get(str(status))
    if state is None:
        raise LifecycleError("未知契约状态：%r（修复指引：状态只允许 %s）"
                             % (status, "/".join(sorted(table))), code="STATUS-UNKNOWN")
    allowed = state.get("references_allowed")
    if allowed is True:
        return True
    if allowed == "existing-only":
        return not bool(new_reference)
    return False


def check_contract(doc: Dict[str, Any], root: str = ".") -> List[str]:
    """按状态义务校验 nf-contract/1（含 schema 校验）。返回 issues（不抛）。"""
    from core import json_schema
    issues: List[str] = []
    registry = load_registry(root)
    schema = json.loads((Path(root) / CONTRACT_SCHEMA_REL).read_text(encoding="utf-8"))
    for item in json_schema.json_schema_check(doc, schema)[:3]:
        issues.append("contract schema：%s" % item)
    table = {str(s.get("id")): s for s in registry.get("states") or []}
    status = str(doc.get("status"))
    state = table.get(status)
    if state is None:
        issues.append("契约状态 %r 不在状态词表（修复指引：draft/active/deprecated/retired）" % status)
        return issues
    evidence = doc.get("evidence") or []
    if len(evidence) < int(state.get("evidence_min") or 0):
        issues.append("%s 契约要求 evidence ≥%s（当前 %d；修复指引：补证据引用）"
                      % (status, state.get("evidence_min"), len(evidence)))
    if state.get("acceptance_required") and not (doc.get("acceptance") or []):
        issues.append("%s 契约要求 acceptance ≥1（修复指引：补验收引用）" % status)
    constraints = doc.get("constraints") or []
    if status in ("active", "deprecated", "retired"):
        for rule in constraints:
            if not str((rule or {}).get("rule") or "").strip():
                issues.append("constraint %s 缺 rule" % (rule or {}).get("id"))
    if status == "draft" and can_reference("draft", True, root):
        issues.append("draft 不应可被引用（registry 不一致）")
    return issues


def check_registry(root: str = ".") -> List[str]:
    """义务表自检：状态齐、词表一致、义务→check 映射非空、claims 边界。"""
    issues: List[str] = []
    reg = load_registry(root)
    table = {str(s.get("id")): s for s in reg.get("states") or []}
    vocab = [str(x) for x in reg.get("status_vocabulary") or []]
    if sorted(table) != sorted(vocab):
        issues.append("states 与 status_vocabulary 不一致：%s / %s"
                      % (sorted(table), sorted(vocab)))
    for need in ("draft", "active", "deprecated", "retired"):
        if need not in table:
            issues.append("缺状态义务：%s" % need)
    for sid, state in table.items():
        if not state.get("obligations"):
            issues.append("%s 缺 obligations" % sid)
        if "consumable" not in state:
            issues.append("%s 缺 consumable" % sid)
        if "references_allowed" not in state:
            issues.append("%s 缺 references_allowed" % sid)
    if not reg.get("obligation_checks"):
        issues.append("缺 obligation_checks（义务→check 映射）")
    if not any("不替代" in str(x) for x in reg.get("claims_boundary") or []):
        issues.append("claims_boundary 必须写明不替代治理 verify/附件模式")
    return issues
