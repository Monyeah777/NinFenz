"""verify 判定报告的四个证据面分片（对外只经 core.trust.verify 门面导入）。"""

from __future__ import annotations

from pathlib import Path

from core import json_doc
from core.trust import anchor as ta
from core.trust import human_review as hrev
from core.trust import public_anchor as pua
from core.trust import signature as tsig


def _dsse_schema(root: str):
    try:
        return json_doc.load(
            Path(root) / "protocol/trust/dsse.schema.json", dict, what="dsse schema")
    except (OSError, ValueError):
        return None


def anchor_section(anchor, subject_digest: str, policy: dict, verifiers, root: str) -> dict:
    if anchor is None:
        return {"facts": None, "issues": [], "checks": [{
            "id": "A2-anchor-facts", "ok": False,
            "detail": "未提供 nf-anchor/1；T2 及以上只报缺项，不冒充等级"}]}
    merged = ta.verify_anchor_set(anchor, subject_digest, policy,
                                  verifiers, root=root)
    issues = merged["issues"]
    checks = [
        {"id": "A2-anchor-facts", "ok": not issues,
         "detail": "anchor 事实：" + "；".join(
             f"{k}={v}" for k, v in sorted(merged["facts"].items()))},
        {"id": "A2-anchor-details", "ok": not issues,
         "detail": "；".join(f"{d['kind']}:{d['status']}"
                            for d in merged["details"]) or "无锚"},
    ]
    return {"facts": merged["facts"], "issues": issues, "checks": checks}


def signature_section(
    head_signature, subject_digest: str, registry, material, now, root: str
) -> dict:
    if head_signature is None:
        return {"facts": None, "issues": [], "checks": [{
            "id": "A1-head-signature", "ok": False,
            "detail": "未提供链头签名；T1 及以上只报缺项，不冒充等级"}]}
    if not registry or not isinstance(material, dict):
        return {"facts": None, "issues": [], "checks": [{
            "id": "A1-head-signature", "ok": False,
            "detail": "给了签名信封但缺 registry/material，签名事实记 none"}]}
    envelope_schema = _dsse_schema(root)
    verified = tsig.verify_head(
        head_signature,
        'bundle',
        subject_digest,
        registry,
        material,
        opts=tsig.VerifyHeadOptions(schema_envelope=envelope_schema, now=now, root=root),
    )
    if verified.get("ok"):
        return {"facts": {"signature": "ok"}, "issues": [], "checks": [{
            "id": "A1-head-signature", "ok": True,
            "detail": "链头签名有效：signers=" + ",".join(
                verified.get("signers") or [])}]}
    if verified.get("reason") in ("KEY-UNKNOWN", "VERIFIER-MISSING"):
        return {"facts": None, "issues": [], "checks": [{
            "id": "A1-head-signature", "ok": False,
            "detail": "签名无法判定：" + str(verified.get("reason"))}]}
    reason = str(verified.get("reason") or "SIGNATURE-INVALID")
    return {
        "facts": {"signature": "invalid"},
        "issues": [{
            "code": reason, "message": "链头签名校验失败",
            "fix": "重签链头并确认 issuer registry 生命周期（吊销/过期/轮换）"}],
        "checks": [{
            "id": "A1-head-signature", "ok": False,
            "detail": "链头签名失败：" + reason}],
    }


def public_section(
    public_anchor, verifier, log_id: str, subject_digest: str, root: str
) -> dict:
    if public_anchor is None:
        return {"facts": None, "issues": [], "checks": [{
            "id": "A5-public-anchor", "ok": False,
            "detail": "未提供公共锚（T4 只报缺项，不冒充已锚）"}]}
    resolved = pua.verify_public_anchor(
        public_anchor,
        verifier,
        log_id,
        subject_digest,
        opts=pua.PublicAnchorOptions(root=root),
    )
    if resolved.get("ok"):
        return {"facts": {"public_anchor": "ok"}, "issues": [], "checks": [{
            "id": "A5-public-anchor", "ok": True,
            "detail": f"public anchor ok：log={resolved.get('log_id')} "
                      f"tree={resolved.get('tree_size')}"}]}
    return {
        "facts": {"public_anchor": "invalid"},
        "issues": [{"code": str(resolved.get("reason") or "PUBLIC-ANCHOR-INVALID"),
                    "message": "公共锚校验失败",
                    "fix": "核对 pinned log id/公钥、inclusion proof 与目标摘要"}],
        "checks": [{"id": "A5-public-anchor", "ok": False,
                    "detail": str(resolved.get("reason"))}],
    }


def review_section(
    human_review, subject_digest: str, registry, material, now, root: str
) -> dict:
    if human_review is None or not registry or not isinstance(material, dict):
        return {"issues": [], "checks": [{
            "id": "A4-human-review", "ok": False,
            "detail": "human review state=PENDING"
                      "（未提供复核记录；PENDING 不等于通过）"}]}
    envelope_schema = _dsse_schema(root)
    reviewed = hrev.verify_review(
        human_review,
        'bundle',
        subject_digest,
        registry,
        material,
        opts=hrev.ReviewVerifyOptions(schema_envelope=envelope_schema, now=now, root=root),
    )
    review_state = hrev.review_state(reviewed)
    review_detail = f"human review state={review_state}"
    if reviewed.get("reason"):
        review_detail += f"（{reviewed.get('reason')}）"
    checks = [{"id": "A4-human-review",
               "ok": review_state == hrev.STATE_APPROVED,
               "detail": review_detail}]
    if review_state in (hrev.STATE_REJECTED, hrev.STATE_ESCALATED, hrev.STATE_INVALID):
        issues = [{"code": str(reviewed.get("reason") or "REVIEW-INVALID"),
                   "message": f"人类复核未通过（state={review_state}）",
                   "fix": "重走复核并签 approve，或不要附上被拒记录"}]
    else:
        issues = []
    return {"issues": issues, "checks": checks}
