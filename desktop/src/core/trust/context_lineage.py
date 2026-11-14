"""nf-context-lineage/1 上下文血缘（FR-A4-04；claim #34）：prompt/context 逐段绑定。

链式规则（与 nf-process/1 同构，起点为 64 个 0）：
    segment.digest = domain_digest("nf:context-lineage:v1:segment",
                                   canonical({seq, role, content_digest, prev}))
    head = 最后一段 digest；首段 prev = ZERO_DIGEST
    lineage_digest = domain_digest("nf:context-lineage:v1:lineage",
                                   canonical({model_card_digest, head, segment_count}))

检测面：上下文替换（content_digest 变 → 段摘要/后续 prev 全断）、前缀篡改、段重排、
跨会话复用（model_card_digest 或 prompt_context_digest 绑定不符）。只存摘要，不存原文。
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import canonical as tc
from core.trust import model_card as tmc

GUIDE = "修复指引："
SCHEMA = "nf-context-lineage/1"
SCHEMA_REL = "protocol/trust/context-lineage.schema.json"
ROLES = ("system", "user", "assistant", "tool")
ZERO_DIGEST = "0" * 64
TAG_SEGMENT = "nf:context-lineage:v1:segment"
TAG_LINEAGE = "nf:context-lineage:v1:lineage"
AI_EVIDENCE_TYPE = tmc.AI_EVIDENCE_TYPE
REASON_LINEAGE_INVALID = "LINEAGE-INVALID"
REASON_MODEL_CARD_MISMATCH = "MODEL-CARD-MISMATCH"
REASON_CONTEXT_DIGEST_MISMATCH = "CONTEXT-DIGEST-MISMATCH"
REASON_TYPE_MISMATCH = "TYPE-MISMATCH"
REASON_CARD_REF_MISSING = "CARD-REF-MISSING"
REASON_CONTEXT_REF_MISSING = "CONTEXT-REF-MISSING"
REASON_CARD_REF_MISMATCH = "CARD-REF-MISMATCH"
REASON_CONTEXT_REF_MISMATCH = "CONTEXT-REF-MISMATCH"


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 context lineage schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 schema.const）")
    return doc


def load_lineage(path: str) -> dict:
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"缺 context lineage：{path}（{GUIDE}传存在且 schema 正确的 JSON）")
    return json_doc.load(target, dict, what="context lineage")


def content_digest(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def segment_digest(seq: int, role: str, content_sha: str, prev: str) -> str:
    """单段摘要：seq/role/content_digest/prev 四者绑定。"""
    body = tc.canonical_bytes({"seq": int(seq), "role": str(role),
                               "content_digest": str(content_sha), "prev": str(prev)})
    return tc.domain_digest(TAG_SEGMENT, body)


def lineage_digest(model_card_digest: str, head: str, segment_count: int) -> str:
    """血缘摘要：模型卡 + 链头 + 段数绑定（跨会话复用/换卡即变）。"""
    body = tc.canonical_bytes({"model_card_digest": str(model_card_digest),
                               "head": str(head), "segment_count": int(segment_count)})
    return tc.domain_digest(TAG_LINEAGE, body)


def build_lineage(model_card_digest: str, contents: list) -> dict:
    """从 [(role, content_bytes)] 构建血缘；空/坏角色/坏模型卡摘要即抛。"""
    if not tmc_schema_digest_ok(model_card_digest):
        raise ValueError(f"model_card_digest 必须是 64 位小写 hex（{GUIDE}用 card_digest 计算）")
    if not isinstance(contents, list) or not contents:
        raise ValueError(f"context 至少 1 段（{GUIDE}空上下文没有血缘）")
    segments = []
    prev = ZERO_DIGEST
    for index, item in enumerate(contents):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError(f"context 段形状必须是 (role, bytes)（{GUIDE}检查输入）")
        role, data = item
        if role not in ROLES:
            raise ValueError(f"context role 越界：{role!r}（{GUIDE}取 {ROLES}）")
        sha = content_digest(data)
        digest = segment_digest(index + 1, role, sha, prev)
        segments.append({"seq": index + 1, "role": role, "content_digest": sha,
                         "prev": prev, "digest": digest})
        prev = digest
    head = segments[-1]["digest"]
    return {"schema": SCHEMA, "model_card_digest": model_card_digest,
            "segments": segments, "head": head,
            "lineage_digest": lineage_digest(model_card_digest, head, len(segments))}


def tmc_schema_digest_ok(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        ch in "0123456789abcdef" for ch in value)


def verify_lineage(lineage: Any, card: dict | None = None, schema: dict | None = None,
                   card_schema: dict | None = None, root: str = ".") -> dict:
    """核验血缘链 + 链头 + 模型卡绑定；返回 {ok, issues, head?, lineage_digest?}。"""
    issues: list = []
    if schema is None:
        schema = load_schema(root)
    problems = json_schema.json_schema_check(lineage, schema)
    if problems:
        return {"ok": False,
                "issues": [{"code": REASON_LINEAGE_INVALID, "message": problems[0],
                            "fix": "按 nf-context-lineage/1 修血缘件"}]}
    segments = lineage.get("segments") or []
    expected_prev = ZERO_DIGEST
    for index, seg in enumerate(segments):
        where = f"segments[{index}]"
        if int(seg.get("seq")) != index + 1:
            issues.append({"code": REASON_LINEAGE_INVALID, "message": f"{where} seq 不连续",
                           "fix": "seq 必须从 1 连续递增"})
        if seg.get("prev") != expected_prev:
            issues.append({"code": REASON_LINEAGE_INVALID,
                           "message": f"{where} prev 与上段 digest 不衔接",
                           "fix": "链式血缘被改/重排；按原文重建"})
        recomputed = segment_digest(seg.get("seq"), seg.get("role"),
                                    seg.get("content_digest"), seg.get("prev"))
        if recomputed != seg.get("digest"):
            issues.append({"code": REASON_LINEAGE_INVALID,
                           "message": f"{where} digest 与内容/前向绑定不符",
                           "fix": "内容或前向被改；按原文重建或拒绝该证据"})
        expected_prev = str(seg.get("digest"))
    if segments and lineage.get("head") != segments[-1].get("digest"):
        issues.append({"code": REASON_LINEAGE_INVALID, "message": "head 不等于末段 digest",
                       "fix": "重算 head"})
    digest = lineage_digest(lineage.get("model_card_digest"), lineage.get("head"),
                            len(segments))
    if digest != lineage.get("lineage_digest"):
        issues.append({"code": REASON_LINEAGE_INVALID, "message": "lineage_digest 不符",
                       "fix": "重算 lineage_digest（模型卡/链头/段数任一变化都会变）"})
    if card is not None:
        card_issues = tmc.validate_card(card, card_schema, root)
        if card_issues:
            issues.append({"code": REASON_MODEL_CARD_MISMATCH, "message": card_issues[0],
                           "fix": "先修模型卡"})
        else:
            if tmc.identity_digest(card) != lineage.get("model_card_digest"):
                issues.append({"code": REASON_MODEL_CARD_MISMATCH,
                               "message": "血缘绑定的模型身份（model_digest+评测协议）与所给卡不符",
                               "fix": "上下文属于另一模型/另一评测协议：视为跨会话复用，拒绝"})
            prompt = card.get("prompt_context_digest")
            if prompt and prompt != lineage.get("head"):
                issues.append({"code": REASON_CONTEXT_DIGEST_MISMATCH,
                               "message": "模型卡 prompt_context_digest 与血缘链头不符",
                               "fix": "模型卡须绑定同一上下文链头"})
    return {"ok": not issues, "issues": issues, "head": lineage.get("head"),
            "lineage_digest": digest}


def _refs(entity: dict, kind: str) -> list:
    return [ref for ref in (entity.get("refs") or [])
            if isinstance(ref, dict) and str(ref.get("kind")) == kind]


def check_context_binding(entity: Any, card: dict, lineage: dict,
                          schema: dict | None = None, card_schema: dict | None = None,
                          lineage_schema: dict | None = None,
                          expected_type: str = AI_EVIDENCE_TYPE,
                          root: str = ".") -> dict:
    """AI 证据 ↔ 模型卡 ↔ 上下文血缘 三方绑定。"""
    result = verify_lineage(lineage, card, lineage_schema, card_schema, root)
    if not result.get("ok"):
        issue = result["issues"][0]
        return {"ok": False, "reason": issue["code"], "detail": issue["message"]}
    if not isinstance(entity, dict) or str(entity.get("type")) != expected_type:
        return {"ok": False, "reason": REASON_TYPE_MISMATCH}
    card_refs = _refs(entity, "card")
    if not card_refs:
        return {"ok": False, "reason": REASON_CARD_REF_MISSING}
    card_sha = tmc.card_digest(card)
    if not any(str(ref.get("digest")) == card_sha for ref in card_refs):
        return {"ok": False, "reason": REASON_CARD_REF_MISMATCH}
    context_refs = _refs(entity, "context")
    if not context_refs:
        return {"ok": False, "reason": REASON_CONTEXT_REF_MISSING}
    if not any(str(ref.get("digest")) == result["lineage_digest"] for ref in context_refs):
        return {"ok": False, "reason": REASON_CONTEXT_REF_MISMATCH}
    return {"ok": True, "card_digest": card_sha,
            "lineage_digest": result["lineage_digest"], "head": result["head"]}
