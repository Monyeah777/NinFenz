"""nf-human-review/1 人类复核记录（FR-A4-05；claim #13 的证据面）。

为什么需要它：runtime_executor 的状态机只能证明「流程走没走」，证不了「谁签的字、现在还
算不算数」。本模块把复核记录做成**可独立验签的证据**：

    statement = nf-human-review/1（subject_kind/digest + decision + reviewer{kind:human}）
    envelope  = DSSE(statement)，keyid ∈ issuer registry

判定：签名与 registry 生命周期（keys.verify_envelope）→ reviewer 必须是 human kind →
decision 必须是 approve。缺失记录 = PENDING，**永远不得读成通过**；reject/escalate 是
合法签名但结论不是批准。

边界：本模块不改变 T 等级（复核是独立证据面）；是否「必须有复核」由策略/流程决定，报告
里显式给出 PENDING/APPROVED/REJECTED/ESCALATED/INVALID 状态，调用方不得把 PENDING 当通过。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import dsse
from core.trust import keys as tk

GUIDE = "修复指引："
SCHEMA = "nf-human-review/1"
SCHEMA_REL = "protocol/trust/human-review.schema.json"
PAYLOAD_TYPE = "application/vnd.nf.human-review+json"
SUBJECT_KINDS = ("bundle", "claim", "card", "event", "evidence")
DECISIONS = ("approve", "reject", "escalate")
STATE_PENDING = "PENDING"
STATE_APPROVED = "APPROVED"
STATE_REJECTED = "REJECTED"
STATE_ESCALATED = "ESCALATED"
STATE_INVALID = "INVALID"
REASON_NOT_APPROVED = "REVIEW-NOT-APPROVED"
REASON_NOT_HUMAN = "REVIEWER-NOT-HUMAN"
REASON_INVALID = "REVIEW-INVALID"
REASON_SUBJECT = "REVIEW-SUBJECT-MISMATCH"


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 human review schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 schema.const）")
    return doc


def build_statement(subject_kind: str, subject_digest: str, decision: str,
                    issuer_id: str, keyid: str, rationale: str, reviewed_at: str,
                    schema: dict | None = None, root: str = ".") -> dict:
    if subject_kind not in SUBJECT_KINDS:
        raise ValueError(f"subject_kind 越界：{subject_kind!r}（{GUIDE}取 {SUBJECT_KINDS}）")
    if decision not in DECISIONS:
        raise ValueError(f"decision 越界：{decision!r}（{GUIDE}取 {DECISIONS}）")
    statement = {"schema": SCHEMA, "subject_kind": subject_kind,
                 "subject_digest": subject_digest, "decision": decision,
                 "reviewer": {"issuer_id": issuer_id, "keyid": keyid, "kind": "human"},
                 "rationale": rationale, "reviewed_at": reviewed_at}
    check_schema = schema if schema is not None else load_schema(root)
    problems = json_schema.json_schema_check(statement, check_schema)
    if problems:
        raise ValueError(f"复核语句结构不合 {SCHEMA}：{problems[0]}（{GUIDE}按冻结 schema 修）")
    return statement


def sign_review(statement: dict, signers: list) -> dict:
    """把复核语句签成 nf-dsse/1 信封（payloadType 固定）。"""
    from core.trust import canonical as tc
    return dsse.sign_envelope(PAYLOAD_TYPE, tc.canonical_bytes(statement), signers)


def review_state(result: dict | None) -> str:
    """缺失/无效/拒绝都必须显式成状态；None = PENDING（永不等于通过）。"""
    if result is None:
        return STATE_PENDING
    if not result.get("ok") and result.get("reason") == REASON_NOT_APPROVED:
        return STATE_REJECTED if result.get("decision") == "reject" else STATE_ESCALATED
    if not result.get("ok"):
        return STATE_INVALID
    return STATE_APPROVED


def verify_review(envelope: Any, expected_kind: str, expected_digest: str,
                  registry: dict, material: dict,
                  schema_envelope: dict | None = None,
                  schema_statement: dict | None = None,
                  now: str | None = None, root: str = ".") -> dict:
    """验复核信封：DSSE + registry 生命周期 + reviewer human kind + 对象绑定 + decision。"""
    if not isinstance(envelope, dict):
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_INVALID}
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_INVALID,
                "detail": "payloadType 不符"}
    try:
        payload = dsse._b64d(envelope.get("payload"))
        statement = json_doc.loads(payload.decode("utf-8"), dict, what="human review")
    except (UnicodeDecodeError, ValueError) as exc:
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_INVALID,
                "detail": str(exc)}
    check_schema = schema_statement if schema_statement is not None else load_schema(root)
    problems = json_schema.json_schema_check(statement, check_schema)
    if problems:
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_INVALID,
                "detail": problems[0]}
    if statement.get("subject_kind") != expected_kind:
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_SUBJECT}
    if statement.get("subject_digest") != expected_digest:
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_SUBJECT}
    reviewer = statement.get("reviewer") or {}
    issuer_id = str(reviewer.get("issuer_id") or "")
    resolved = tk.resolve_issuer(registry, issuer_id)
    if not resolved.get("ok"):
        return {"ok": False, "state": STATE_INVALID, "reason": "ISSUER-UNKNOWN"}
    if str((resolved.get("issuer") or {}).get("kind")) != "human":
        return {"ok": False, "state": STATE_INVALID, "reason": REASON_NOT_HUMAN}
    verified = tk.verify_envelope(envelope, registry, material, schema_envelope, now=now)
    if not verified.get("valid"):
        return {"ok": False, "state": STATE_INVALID,
                "reason": verified.get("reason", REASON_INVALID),
                "detail": verified.get("detail", "")}
    base = {"state": STATE_APPROVED, "decision": statement.get("decision"),
            "reviewer": issuer_id, "keyid": reviewer.get("keyid"),
            "subject_kind": statement.get("subject_kind"),
            "subject_digest": statement.get("subject_digest"),
            "signers": verified.get("signers") or []}
    if statement.get("decision") != "approve":
        base.update(ok=False, reason=REASON_NOT_APPROVED,
                    state=(STATE_REJECTED if statement.get("decision") == "reject"
                           else STATE_ESCALATED))
        return base
    base["ok"] = True
    return base
