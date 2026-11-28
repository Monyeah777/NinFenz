"""AIGC/标注证据（WP-43，G4）：AI 生成内容的机器可读标识与绑定。

纪律：
- 来自 AI 生成/辅助的交付产物**必须带标识**（`nf-aigc-label/1`）——无标识不默认 human；
- 标识绑定：`generator.model_digest` == 模型卡摘要；`subject_digest` == 被标注产物 SHA-256；
  `provenance_refs` 全部在场且限于 AI 证据面；`label=human` 需复核 approve；
- `labeled_at` 固定样例时间（不读时钟），样例 committed == 实时重算；
- 只做仓库内证据面，**不声称符合外部内容标识法规/标准**。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

SCHEMA = "nf-aigc-labeling/1"
REL = "protocol/aigc_labeling.json"
LABEL_SCHEMA = "nf-aigc-label/1"
LABELED_AT = "2026-11-15T00:00:00Z"
SUBJECT = "results/delivery/wiki-module-M06/artifact.md"
CARD_REL = "results/ai/model-card.json"
REVIEW_REL = "results/ai/human-review.json"
GUIDE = "修复指引："
LABELS = ("ai-generated", "ai-assisted", "human")
SUBJECT_KINDS = ("delivery-artifact", "wiki-page", "model-card")
ALLOWED_REF_PREFIXES = ("results/ai/", "protocol/ai_evidence.json")


class LabelError(Exception):
    """标注拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "AIGC-LABEL-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise LabelError("缺 %s（修复指引：补 AIGC 标注登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LabelError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise LabelError("registry schema 必须 %s" % SCHEMA)
    return doc


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_sample(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    card = json.loads((Path(root) / CARD_REL).read_text(encoding="utf-8"))
    rel = str((reg.get("label_artifact") or {}).get("rel") or "results/ai/aigc-label.json")
    subject_path = Path(root) / SUBJECT
    if not subject_path.is_file():
        raise LabelError("缺被标注产物 %s（修复指引：先跑 WP-23 交付包）" % SUBJECT,
                         code="SUBJECT-MISSING")
    return {"schema": LABEL_SCHEMA, "subject_kind": "delivery-artifact",
            "subject_digest": _sha_file(subject_path),
            "label": "ai-assisted",
            "generator": {"model_id": str(card.get("model_id")),
                          "model_digest": str(card.get("model_digest"))},
            "provenance_refs": [CARD_REL, REVIEW_REL],
            "labeled_at": LABELED_AT, "label_rel": rel,
            "note": "sample 标注：AI 辅助生成，绑定模型卡与复核证据"}


def write_sample(root: str = ".") -> Dict[str, Any]:
    from core import atomic_write
    doc = build_sample(root)
    rel = str(doc.pop("label_rel"))
    atomic_write.write_text(Path(root) / rel,
                            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return doc


def load_sample(root: str = ".") -> Dict[str, Any]:
    reg = load_registry(root)
    rel = str((reg.get("label_artifact") or {}).get("rel"))
    path = Path(root) / rel
    if not path.is_file():
        raise LabelError("缺 %s（修复指引：跑 write_sample）" % rel, code="LABEL-MISSING")
    return json.loads(path.read_text(encoding="utf-8"))


def _label_header_issues(reg: Dict[str, Any], label: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    if str(label.get("schema")) != LABEL_SCHEMA:
        issues.append("schema 必须 %s" % LABEL_SCHEMA)
    kind = str(label.get("subject_kind"))
    if kind not in (reg.get("subject_kinds") or SUBJECT_KINDS):
        issues.append("subject_kind 非法：%s" % kind)
    tag = str(label.get("label"))
    if tag not in (reg.get("label_vocabulary") or LABELS):
        issues.append("label 不在词表：%s（未标注不默认 human）" % tag)
    for key in (reg.get("label_artifact") or {}).get("required") or []:
        if not label.get(key):
            issues.append("缺必填字段：%s" % key)
    return issues


def _generator_issues(root: str, label: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    card_path = Path(root) / CARD_REL
    if not card_path.is_file():
        issues.append("缺模型卡（修复指引：先跑 WP-40 write_sample）")
    else:
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if str((label.get("generator") or {}).get("model_digest")) != str(card.get("model_digest")):
            issues.append("generator.model_digest 与模型卡不一致（修复指引：重签标识）")
        if str((label.get("generator") or {}).get("model_id")) != str(card.get("model_id")):
            issues.append("generator.model_id 与模型卡不一致")
    return issues


def _subject_issues(root: str, label: Dict[str, Any]) -> List[str]:
    subject = Path(root) / SUBJECT
    if not subject.is_file():
        return []
    if str(label.get("subject_digest")) != _sha_file(subject):
        return ["subject_digest 与被标注产物摘要不一致（修复指引：重算并重签）"]
    return []


def _ref_issues(root: str, label: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    refs = label.get("provenance_refs") or []
    if not refs:
        issues.append("provenance_refs 不能为空")
    for ref in refs:
        ref = str(ref)
        if not ref.startswith(ALLOWED_REF_PREFIXES):
            issues.append("provenance_ref 越界（只允许 results/ai/* 或 protocol/ai_evidence.json）：%s" % ref)
        if not (Path(root) / ref).is_file():
            issues.append("provenance_ref 不在场：%s" % ref)
    return issues


def _human_label_issues(root: str, tag: str) -> List[str]:
    if tag != "human":
        return []
    review_path = Path(root) / REVIEW_REL
    if not review_path.is_file():
        return ["label=human 但缺复核记录"]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if str(review.get("decision")) != "approve":
        return ["label=human 但复核未 approve"]
    return []


def _labeled_at_issues(label: Dict[str, Any]) -> List[str]:
    if not str(label.get("labeled_at") or "").endswith("Z"):
        return ["labeled_at 必须是 UTC（ISO-8601 Z）"]
    return []


def _claims_boundary_issues(reg: Dict[str, Any]) -> List[str]:
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不声称" not in boundary:
        return ["claims_boundary 必须写明不声称外部法规兼容"]
    return []


def check_label(label: Any, root: str = ".") -> List[str]:
    """单张标识的闭合判据（schema/词表/绑定/引用/复核）。"""
    reg = load_registry(root)
    if not isinstance(label, dict):
        return ["标识不是对象"]
    tag = str(label.get("label"))
    issues: List[str] = _label_header_issues(reg, label)
    issues += _generator_issues(root, label)
    issues += _subject_issues(root, label)
    issues += _ref_issues(root, label)
    issues += _human_label_issues(root, tag)
    issues += _labeled_at_issues(label)
    issues += _claims_boundary_issues(reg)
    return issues


def check(root: str = ".") -> List[str]:
    issues: List[str] = []
    reg = load_registry(root)
    rel = str((reg.get("label_artifact") or {}).get("rel"))
    committed = load_sample(root)
    live = build_sample(root)
    live.pop("label_rel", None)
    if json.dumps(committed, ensure_ascii=False, indent=2, sort_keys=True) + "\n" != \
            json.dumps(live, ensure_ascii=False, indent=2, sort_keys=True) + "\n":
        issues.append("%s 与实时重算不一致（修复指引：跑 write_sample 重生成）" % rel)
    issues += check_label(committed, root)
    return issues
