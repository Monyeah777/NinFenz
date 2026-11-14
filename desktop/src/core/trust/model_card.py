"""nf-model-card/1 模型卡与 AI 证据绑定（FR-A4-03；claim #19）。

为什么需要它：AI 产出的证据若只写「某模型说的」，模型一换/评测协议一改，旧证据就失去了
可比性与可追溯性。本模块把 AI 证据绑定到**模型卡摘要**：

    evidence(entity).refs[card] 的 digest == digest_of(bound_card)

判定规则（fail-closed）：
- 卡必须过冻结 schema，且 pinned 语义为真（pre_registered / score_forbidden 必须 true）；
- AI 证据必须引用卡（CARD-REF-MISSING），ref digest 必须等于所给卡摘要（CARD-REF-MISMATCH）；
- 与「当前卡」比较：模型摘要变了 → MODEL-REPLACED（旧证据失效）；
  同模型但评测协议变了 → EVAL-PROTOCOL-CHANGED（旧证据失效）；
  同模型同协议、仅元数据变化 → 仍有效，但回报 CARD-REISSUED 警告。

边界：本模块不判定模型好坏、不跑评测；评测协议本身的预注册与禁 score 由 eval_harness 负责，
模型卡只承载其摘要并强制 pinned 字段为真。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import canonical as tc

GUIDE = "修复指引："
SCHEMA = "nf-model-card/1"
SCHEMA_REL = "protocol/trust/model-card.schema.json"
AI_EVIDENCE_TYPE = "ai-evidence"
REASON_CARD_INVALID = "CARD-INVALID"
REASON_TYPE_MISMATCH = "TYPE-MISMATCH"
REASON_CARD_REF_MISSING = "CARD-REF-MISSING"
REASON_CARD_REF_MISMATCH = "CARD-REF-MISMATCH"
REASON_MODEL_REPLACED = "MODEL-REPLACED"
REASON_EVAL_CHANGED = "EVAL-PROTOCOL-CHANGED"
REASON_CURRENT_INVALID = "CURRENT-CARD-INVALID"


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 model card schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 schema.const）")
    return doc


def load_card(path: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺模型卡：{path}（{GUIDE}传存在且 schema 正确的 JSON）")
    return json_doc.load(target, dict, what="model card")


def validate_card(card: Any, schema: dict | None = None, root: str = ".") -> list:
    """结构 + pinned 语义校验；返回问题清单（空 = 合法）。"""
    check_schema = schema if schema is not None else load_schema(root)
    issues = json_schema.json_schema_check(card, check_schema)
    if issues:
        return issues
    protocol = card.get("eval_protocol") or {}
    if protocol.get("pre_registered") is not True:
        issues.append(f"eval_protocol.pre_registered 必须为 true（{GUIDE}先预注册评测协议）")
    if protocol.get("score_forbidden") is not True:
        issues.append(f"eval_protocol.score_forbidden 必须为 true（{GUIDE}评分不得写回运行时）")
    return issues


def card_digest(card: dict) -> str:
    """模型卡的规范摘要（绑定标识；同一卡任意两次结果一致）。"""
    return tc.digest_of(card)


def _card_refs(entity: dict) -> list:
    return [ref for ref in (entity.get("refs") or [])
            if isinstance(ref, dict) and str(ref.get("kind")) == "card"]


def check_binding(entity: Any, bound_card: dict, current_card: dict | None = None,
                  schema: dict | None = None, expected_type: str = AI_EVIDENCE_TYPE,
                  root: str = ".") -> dict:
    """AI 证据 ↔ 模型卡绑定判定。返回 {ok, reason?, warning?, bound_digest?}。"""
    check_schema = schema if schema is not None else load_schema(root)
    issues = validate_card(bound_card, check_schema)
    if issues:
        return {"ok": False, "reason": REASON_CARD_INVALID, "detail": issues[0]}
    if not isinstance(entity, dict):
        return {"ok": False, "reason": REASON_TYPE_MISMATCH}
    if str(entity.get("type") or "") != expected_type:
        return {"ok": False, "reason": REASON_TYPE_MISMATCH}
    refs = _card_refs(entity)
    if not refs:
        return {"ok": False, "reason": REASON_CARD_REF_MISSING}
    bound = card_digest(bound_card)
    if not any(str(ref.get("digest")) == bound for ref in refs):
        return {"ok": False, "reason": REASON_CARD_REF_MISMATCH}
    result = {"ok": True, "bound_digest": bound}
    if current_card is not None:
        current_issues = validate_card(current_card, check_schema)
        if current_issues:
            return {"ok": False, "reason": REASON_CURRENT_INVALID,
                    "detail": current_issues[0]}
        current = card_digest(current_card)
        if current != bound:
            if current_card.get("model_digest") != bound_card.get("model_digest"):
                return {"ok": False, "reason": REASON_MODEL_REPLACED,
                        "detail": "当前卡 model_digest 与被绑卡不同"}
            bound_protocol = (bound_card.get("eval_protocol") or {}).get("protocol_digest")
            current_protocol = (current_card.get("eval_protocol") or {}).get("protocol_digest")
            if bound_protocol != current_protocol:
                return {"ok": False, "reason": REASON_EVAL_CHANGED,
                        "detail": "同模型但评测协议摘要已变"}
            result["warning"] = "CARD-REISSUED"
    return result
