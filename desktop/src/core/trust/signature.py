"""链头/卡/事件签名接口（nf-chain-head/1；FR-A3-01/A3-02 的组合面）。

为什么需要它：DSSE 是信封、issuer registry 是资格、anchor 是外部见证——但「到底签的是
什么对象」需要一层语句绑定：subject_kind + subject_digest。本模块把三者串成一条生产路径：

    statement = {"schema":"nf-chain-head/1","subject_kind":...,"subject_digest":...}
    envelope  = DSSE(sign(statement), keyid ∈ registry)
    verify    = registry 生命周期 + DSSE 签名 + 语句绑定（kind/digest 必须与调用方期望一致）

边界：本模块不生成私钥、不做时间戳（那是 anchor）；issued_at 由调用方显式给，缺省不填
（不隐式取墙钟——判定可复算是硬约束）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core import json_doc, json_schema
from core.trust import dsse
from core.trust import keys as tk

GUIDE = "修复指引："
SCHEMA = "nf-chain-head/1"
SCHEMA_REL = "protocol/trust/chain-head.schema.json"
PAYLOAD_TYPE = "application/vnd.nf.chain-head+json"
KINDS = ("bundle", "process-chain", "card", "event")


def load_schema(root: str = ".", rel: str = SCHEMA_REL) -> dict:
    path = Path(root) / rel
    if not path.is_file():
        raise ValueError(f"缺 chain-head schema：{rel}（{GUIDE}先落 protocol/trust 定义）")
    doc = json_doc.load(path, dict, what=rel)
    const = str((doc.get("properties") or {}).get("schema", {}).get("const"))
    if const != SCHEMA:
        raise ValueError(f"{rel} 不是 {SCHEMA} 定义（{GUIDE}核对 properties.schema.const）")
    return doc


def build_statement(subject_kind: str, subject_digest: str,
                    issued_at: str = "", note: str = "",
                    schema: dict | None = None, root: str = ".") -> dict:
    """组装并自检签名语句；结构/绑定不过即抛（不产出半截语句）。"""
    if subject_kind not in KINDS:
        raise ValueError(f"subject_kind 越界：{subject_kind!r}（{GUIDE}取 {KINDS}）")
    if not _is_digest(subject_digest):
        raise ValueError(f"subject_digest 必须是 64 位小写 hex（{GUIDE}用 sha256 摘要）")
    statement = {"schema": SCHEMA, "subject_kind": subject_kind,
                 "subject_digest": subject_digest}
    if issued_at:
        statement["issued_at"] = issued_at
    if note:
        statement["note"] = note
    check_schema = schema if schema is not None else load_schema(root)
    problems = json_schema.json_schema_check(statement, check_schema)
    if problems:
        raise ValueError(f"语句结构不合 {SCHEMA}：{problems[0]}（{GUIDE}按冻结 schema 修）")
    return statement


def _is_digest(value: Any) -> bool:
    try:
        from core.trust.canonical import is_digest
        return bool(is_digest(value))
    except (TypeError, ValueError):
        return False


def statement_bytes(statement: dict) -> bytes:
    """语句的规范化字节（DSSE payload）；调用方必须先 build_statement 过结构。"""
    from core.trust import canonical as tc
    return tc.canonical_bytes(statement)


def sign_head(subject_kind: str, subject_digest: str, signers: list,
              issued_at: str = "", note: str = "",
              schema: dict | None = None, root: str = ".") -> dict:
    """签一条链头/卡/事件语句 → nf-dsse/1 信封（payloadType 固定）。"""
    statement = build_statement(subject_kind, subject_digest, issued_at, note,
                                schema, root)
    return dsse.sign_envelope(PAYLOAD_TYPE, statement_bytes(statement), signers)


def verify_head(envelope: Any, expected_kind: str, expected_digest: str,
                registry: dict, material: dict, schema_envelope: dict | None = None,
                schema_statement: dict | None = None, now: str | None = None,
                root: str = ".") -> dict:
    """验链头签名：registry 生命周期 + DSSE 签名 + 语句 kind/digest 绑定。

    返回 {ok, reason?, subject_kind?, subject_digest?, signers?, issuers?, statement?}。
    expected_kind/digest 必须由调用方给出（不信任载荷自述——否则「签了别的对象」也算过）。
    """
    if not isinstance(envelope, dict):
        return {"ok": False, "reason": "ENVELOPE-NOT-OBJECT"}
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        return {"ok": False, "reason": "PAYLOAD-TYPE-MISMATCH"}
    try:
        payload = dsse._b64d(envelope.get("payload"))
    except ValueError as exc:
        return {"ok": False, "reason": "PAYLOAD-B64-INVALID", "detail": str(exc)}
    try:
        statement = json_doc.loads(payload.decode("utf-8"), dict, what="chain-head payload")
    except (UnicodeDecodeError, ValueError) as exc:
        return {"ok": False, "reason": "STATEMENT-INVALID", "detail": str(exc)}
    check_schema = schema_statement if schema_statement is not None else load_schema(root)
    problems = json_schema.json_schema_check(statement, check_schema)
    if problems:
        return {"ok": False, "reason": "STATEMENT-SCHEMA-INVALID", "detail": problems[0]}
    if statement.get("subject_kind") != expected_kind:
        return {"ok": False, "reason": "SUBJECT-KIND-MISMATCH"}
    if statement.get("subject_digest") != expected_digest:
        return {"ok": False, "reason": "SUBJECT-DIGEST-MISMATCH"}
    verified = tk.verify_envelope(envelope, registry, material,
                                  schema_envelope, now=now)
    if not verified.get("valid"):
        return {"ok": False, "reason": verified.get("reason", "SIGNATURE-INVALID"),
                "detail": verified.get("detail", "")}
    return {"ok": True, "subject_kind": statement["subject_kind"],
            "subject_digest": statement["subject_digest"],
            "statement": statement, "signers": verified.get("signers") or [],
            "issuers": verified.get("issuers") or {},
            "retired": verified.get("retired") or []}
