"""AI 证据链（WP-40，G4）：模型卡 / 上下文血缘 / 人类复核 三件绑定与拒收。

纪律（PR-07 延伸 / §13A L4）：
- AI 类交付必须有：模型卡（含**预注册评测引用**）+ 血缘（绑卡摘要、链连续）+ 人类复核 approve；
- 缺失/未签/未批 → `PENDING`/拒收，不冒充通过；eval_protocol 摘要必须等于仓内
  `protocol/eval_validity.json` 的实时摘要（评测协议一改，旧证据即失效）；
- 签名信封验签由 check46/trust human_review 覆盖，本件只判结构/绑定/状态；
- 样例件 `results/ai/*.json` 由 `write_sample()` 确定性生成（固定 issued_at/reviewed_at），
  测试断言 committed == 实时重算。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from core import iso8601
from core import json_schema
from core.trust import context_lineage as tcl
from core.trust import model_card as tmc

SCHEMA = "nf-ai-evidence/1"
REL = "protocol/ai_evidence.json"
EVAL_REL = "protocol/eval_validity.json"
ISSUED_AT = "2026-11-15T00:00:00Z"
REVIEWED_AT = "2026-11-15T00:05:00Z"
GUIDE = "修复指引："
STATES = ("PENDING", "APPROVED", "REJECTED", "ESCALATED", "INVALID")


class AIEvidenceError(Exception):
    """AI 证据拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "AI-EVIDENCE-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise AIEvidenceError("缺 %s（修复指引：补 AI 证据链登记）" % REL,
                              code="AI-CARD-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AIEvidenceError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise AIEvidenceError("registry schema 必须 %s" % SCHEMA)
    return doc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _eval_digest(root: str) -> str:
    path = Path(root) / EVAL_REL
    if not path.is_file():
        raise AIEvidenceError("缺 %s（修复指引：先落评测协议）" % EVAL_REL,
                              code="AI-EVAL-DIGEST-MISMATCH")
    return _sha(path.read_bytes())


def build_sample(root: str = ".") -> Dict[str, Any]:
    """确定性样例：模型卡 + 血缘 + 复核（固定时间戳，不读时钟）。"""
    model_digest = _sha(b"nf:model:sample:g4-v1")
    card = {"schema": "nf-model-card/1", "model_id": "nf.sample.model",
            "model_digest": model_digest, "provider": "local-sample",
            "eval_protocol": {"protocol_id": "eval-validity",
                              "protocol_digest": _eval_digest(root),
                              "pre_registered": True, "score_forbidden": True},
            "issued_at": ISSUED_AT,
            "notes": "G4 WP-40 sample：用于证据链绑定判据，不代表真实模型能力"}
    card_dig = tmc.card_digest(card)
    lineage = tcl.build_lineage(tmc.identity_digest(card),
                                [("system", b"nf-sample-system"),
                                 ("user", b"nf-sample-user")])
    review = {"schema": "nf-human-review/1", "subject_kind": "card",
              "subject_digest": card_dig, "decision": "approve",
              "reviewer": {"issuer_id": "nf:local:reviewer",
                           "keyid": "nf:local:reviewer:ed25519-2026", "kind": "human"},
              "rationale": "sample 证据链绑定复核（approve）", "reviewed_at": REVIEWED_AT}
    return {"card": card, "lineage": lineage, "review": review}


def _write(root: str, rel: str, doc: Dict[str, Any]) -> None:
    from core import atomic_write
    atomic_write.write_text(Path(root) / rel,
                            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_sample(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    arts = reg.get("artifacts") or {}
    doc = build_sample(root)
    _write(root, arts["model_card"]["rel"], doc["card"])
    _write(root, arts["lineage"]["rel"], doc["lineage"])
    _write(root, arts["human_review"]["rel"], doc["review"])
    return doc


def load_sample(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    arts = reg.get("artifacts") or {}
    out = {}
    for key in ("model_card", "lineage", "human_review"):
        path = Path(root) / arts[key]["rel"]
        if not path.is_file():
            raise AIEvidenceError("缺 %s（修复指引：跑 write_sample 生成）" % arts[key]["rel"],
                                  code="AI-CARD-MISSING")
        out[key] = json.loads(path.read_text(encoding="utf-8"))
    return {"card": out["model_card"], "lineage": out["lineage"],
            "review": out["human_review"]}


def _artifact_schema_issues(root: str, reg: Dict[str, Any], docs) -> List[str]:
    out: List[str] = []
    arts = reg.get("artifacts") or {}
    for key, doc in docs:
        schema = json.loads((Path(root) / arts[key]["schema_rel"]).read_text(encoding="utf-8"))
        for item in json_schema.json_schema_check(doc, schema)[:3]:
            out.append("%s schema：%s" % (key, item))
    return out


def _protocol_binding_issues(root: str, card: Any) -> List[str]:
    out: List[str] = []
    got = str(((card.get("eval_protocol") or {}).get("protocol_digest")))
    if got != _eval_digest(root):
        out.append("eval_protocol.protocol_digest 与 %s 实时摘要不一致"
                   "（修复指引：协议变更后重签模型卡）" % EVAL_REL)
    if str((card.get("eval_protocol") or {}).get("protocol_id")) != "eval-validity":
        out.append("eval_protocol.protocol_id 必须 eval-validity")
    return out


def _lineage_issues(lineage: Any, card: Any) -> List[str]:
    out: List[str] = []
    if str(lineage.get("model_card_digest")) != tmc.identity_digest(card):
        out.append("lineage.model_card_digest 与模型身份摘要不一致（修复指引：重建血缘）")
    l_result = tcl.verify_lineage(lineage, card)
    for item in (l_result.get("issues") or [])[:3]:
        out.append("血缘：%s" % item.get("message"))
    return out


def _review_issues(review: Any, card_dig: str) -> List[str]:
    out: List[str] = []
    if str(review.get("subject_kind")) != "card":
        out.append("复核 subject_kind 必须 card")
    if str(review.get("subject_digest")) != card_dig:
        out.append("复核 subject_digest 与模型卡摘要不一致（修复指引：重签复核）")
    if str((review.get("reviewer") or {}).get("kind")) != "human":
        out.append("复核 reviewer.kind 必须 human")
    decision = str(review.get("decision"))
    if decision != "approve":
        out.append("复核 decision=%s（未 approve 的 AI 证据不得交付）" % decision)
    if not iso8601.is_iso_instant(str(review.get("reviewed_at"))):
        out.append("复核 reviewed_at 必须是 ISO-8601 UTC")
    return out


def check_ai_evidence(card: Any, lineage: Any, review: Any, root: str = ".") -> List[str]:
    """三件结构与绑定判据（返回 issues；空=APPROVED 可交付）。"""
    reg = load_registry(root)
    docs = (("model_card", card), ("lineage", lineage), ("human_review", review))
    issues: List[str] = _artifact_schema_issues(root, reg, docs)
    if issues:
        return issues
    card_dig = tmc.card_digest(card)
    issues += _protocol_binding_issues(root, card)
    issues += _lineage_issues(lineage, card)
    issues += _review_issues(review, card_dig)
    return issues


def state(card: Any, lineage: Any, review: Any, root: str = ".") -> str:
    """→ PENDING/APPROVED/REJECTED/ESCALATED/INVALID（缺失永不等于通过）。"""
    if not card:
        return "PENDING"
    if not review:
        return "PENDING"
    decision = str((review or {}).get("decision"))
    if decision == "reject":
        return "REJECTED"
    if decision == "escalate":
        return "ESCALATED"
    issues = check_ai_evidence(card, lineage, review, root)
    if issues:
        return "INVALID"
    return "APPROVED"


def check(root: str = ".") -> List[str]:
    """已入仓样例：committed == 实时重算 + 三件通过（空=绿）。"""
    issues: List[str] = []
    reg = load_registry(root)
    live = build_sample(root)
    committed = load_sample(root)
    arts = reg.get("artifacts") or {}
    for key, rel in (("card", arts["model_card"]["rel"]),
                     ("lineage", arts["lineage"]["rel"]),
                     ("review", arts["human_review"]["rel"])):
        text = json.dumps(committed[key], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        live_text = json.dumps(live[key], ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if text != live_text:
            issues.append("%s 与实时重算不一致（修复指引：跑 write_sample 重生成）" % rel)
    issues += check_ai_evidence(committed["card"], committed["lineage"],
                                committed["review"], root)
    if state(committed["card"], committed["lineage"], committed["review"], root) != "APPROVED":
        issues.append("AI 证据链状态非 APPROVED")
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不作保证" not in boundary:
        issues.append("claims_boundary 必须写明模型能力/质量不作保证")
    return issues
