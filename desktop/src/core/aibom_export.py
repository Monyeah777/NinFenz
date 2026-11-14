"""AIBOM / Model Card 导出（WP-41，G4）：CycloneDX AI-BOM + SPDX 风格清单。

纪律：
- 从 AI 证据链（`core.ai_evidence` 三件）导出，**只做清单**，不声称认证/合规；
- **确定性**：serialNumber/documentNamespace 由模型身份摘要派生，created/issued_at 用固定
  样例时间（不读时钟）；同输入逐字节一致；
- **闭合**：组件 hash == 模型卡 model_digest；properties 含 eval digest / lineage head /
  review decision+subject；引用与 results/ai 三件一致；
- **无秘密**：导出串扫描私钥/令牌/密码形状；
- 不引第三方运行时（纯标准库；CycloneDX/SPDX 只作字段口径）。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from core import ai_evidence as ae

SCHEMA = "nf-aibom/1"
REL = "protocol/aibom.json"
CDX_REL = "results/ai/aibom.cdx.json"
SPDX_REL = "results/ai/aibom.spdx.json"
FIXED_TIME = "2026-11-15T00:00:00Z"
GUIDE = "修复指引："
SECRET_PATTERNS = (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}",
    r"ghp_[A-Za-z0-9]{20,}", r"(?i)\bpassword\s*[:=]\s*\S+",
    r"(?i)\btoken\s*[:=]\s*[A-Za-z0-9._\-]{16,}",
)


class AIBOMError(Exception):
    """导出拒绝（消息含修复指引）。"""

    def __init__(self, message: str, code: str = "AIBOM-INVALID") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_registry(root: str = ".") -> Dict[str, Any]:
    path = Path(root) / REL
    if not path.is_file():
        raise AIBOMError("缺 %s（修复指引：补 AIBOM 导出登记）" % REL, code="REGISTRY-MISSING")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AIBOMError("%s 不可解析：%s（修复指引：修 JSON）" % (REL, exc)) from exc
    if str(doc.get("schema")) != SCHEMA:
        raise AIBOMError("registry schema 必须 %s" % SCHEMA)
    return doc


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _uuid_like(seed: str) -> str:
    h = _sha(seed)
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def build(root: str = ".") -> Dict[str, Any]:
    """→ {cdx, spdx}；同输入逐字节确定。"""
    reg = load_registry(root)
    sample = ae.load_sample(root)
    card, lineage, review = sample["card"], sample["lineage"], sample["review"]
    model_digest = str(card["model_digest"])
    eval_digest = str((card.get("eval_protocol") or {}).get("protocol_digest"))
    head = str(lineage.get("head"))
    decision = str(review.get("decision"))
    subject = str(review.get("subject_digest"))
    serial = "urn:uuid:" + _uuid_like("nf-aibom:" + str(
        (card.get("eval_protocol") or {}).get("protocol_digest")) + model_digest)
    cdx = {
        "bomFormat": "CycloneDX", "specVersion": str(reg["exports"]["cyclonedx"]["spec_version"]),
        "serialNumber": serial, "version": 1,
        "metadata": {"timestamp": FIXED_TIME,
                     "tools": [{"vendor": "ninfenz", "name": "nf-aibom", "version": "1"}],
                     "component": {"type": "machine-learning-model",
                                   "bom-ref": "nf:model:" + model_digest[:12],
                                   "name": str(card.get("model_id")),
                                   "version": "1", "supplier": {"name": str(card.get("provider"))},
                                   "hashes": [{"alg": "SHA-256", "content": model_digest}]}},
        "components": [{"type": "data", "bom-ref": "nf:context:" + head[:12],
                        "name": "context-lineage", "version": "1",
                        "hashes": [{"alg": "SHA-256", "content": head}]}],
        "properties": [
            {"name": "nf:model_digest", "value": model_digest},
            {"name": "nf:eval_protocol_digest", "value": eval_digest},
            {"name": "nf:lineage_head", "value": head},
            {"name": "nf:lineage_digest", "value": str(lineage.get("lineage_digest"))},
            {"name": "nf:human_review_decision", "value": decision},
            {"name": "nf:human_review_subject_digest", "value": subject},
            {"name": "nf:human_review_reviewer", "value": str(
                (review.get("reviewer") or {}).get("issuer_id"))},
        ],
    }
    ns = "urn:nf:aibom:" + _uuid_like("nf-spdx:" + model_digest + eval_digest + head)
    spdx = {
        "spdxVersion": str(reg["exports"]["spdx"]["spec_version"]),
        "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
        "name": "nf-aibom-" + model_digest[:12], "documentNamespace": ns,
        "creationInfo": {"created": FIXED_TIME, "creators": ["Tool: nf-aibom-1"]},
        "packages": [{"name": str(card.get("model_id")), "SPDXID": "SPDXRef-Package-model",
                      "versionInfo": "1", "downloadLocation": "NOASSERTION",
                      "checksums": [{"algorithm": "SHA256", "checksumValue": model_digest}],
                      "supplier": "Organization: " + str(card.get("provider"))}],
        "relationships": [{"spdxElementId": "SPDXRef-DOCUMENT",
                           "relationshipType": "DESCRIBES",
                           "relatedSpdxElement": "SPDXRef-Package-model"}],
    }
    return {"cdx": cdx, "spdx": spdx}


def render(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write(root: str = ".") -> Dict[str, Any]:
    from core import atomic_write
    doc = build(root)
    atomic_write.write_text(Path(root) / CDX_REL, render(doc["cdx"]))
    atomic_write.write_text(Path(root) / SPDX_REL, render(doc["spdx"]))
    return doc


def _secret_hits(text: str) -> List[str]:
    hits = []
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            hits.append(pattern)
    return hits


def check(root: str = ".") -> List[str]:
    """导出件判据：必填/哈希/属性闭合/无秘密/committed==live。"""
    issues: List[str] = []
    reg = load_registry(root)
    for rel in (CDX_REL, SPDX_REL):
        if not (Path(root) / rel).is_file():
            issues.append("缺导出件 %s（修复指引：跑 write() 重生成）" % rel)
    if issues:
        return issues
    try:
        cdx = json.loads((Path(root) / CDX_REL).read_text(encoding="utf-8"))
        spdx = json.loads((Path(root) / SPDX_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["导出件不可解析：%s（修复指引：重生成）" % exc]
    live = build(root)
    if render(cdx) != render(live["cdx"]):
        issues.append("CycloneDX 导出与实时重算不一致（修复指引：重跑 write）")
    if render(spdx) != render(live["spdx"]):
        issues.append("SPDX 导出与实时重算不一致（修复指引：重跑 write）")
    for key in reg["exports"]["cyclonedx"]["required"]:
        if key not in cdx:
            issues.append("CycloneDX 缺必填：%s" % key)
    for key in reg["exports"]["spdx"]["required"]:
        if key not in spdx:
            issues.append("SPDX 缺必填：%s" % key)
    sample = ae.load_sample(root)
    card, lineage, review = sample["card"], sample["lineage"], sample["review"]
    hashes = [h.get("content") for h in
              ((cdx.get("metadata") or {}).get("component") or {}).get("hashes") or []]
    if str(card.get("model_digest")) not in hashes:
        issues.append("CycloneDX 组件 hash 与模型卡 model_digest 不一致")
    props = {str(p.get("name")): str(p.get("value")) for p in cdx.get("properties") or []}
    for name in reg.get("properties_required") or []:
        if name not in props:
            issues.append("CycloneDX properties 缺 %s" % name)
    if props.get("nf:eval_protocol_digest") != str((card.get("eval_protocol") or {}).get(
            "protocol_digest")):
        issues.append("properties.eval_protocol_digest 与模型卡不一致")
    if props.get("nf:lineage_head") != str(lineage.get("head")):
        issues.append("properties.lineage_head 与血缘不一致")
    if props.get("nf:human_review_subject_digest") != str(review.get("subject_digest")):
        issues.append("properties.review subject 与复核不一致")
    checksums = [c.get("checksumValue") for c in
                 ((spdx.get("packages") or [{}])[0]).get("checksums") or []]
    if str(card.get("model_digest")) not in checksums:
        issues.append("SPDX checksum 与模型卡不一致")
    rels = spdx.get("relationships") or []
    if not any(r.get("relationshipType") == "DESCRIBES" for r in rels):
        issues.append("SPDX 缺 DESCRIBES 关系")
    for text, label in ((render(cdx), "CycloneDX"), (render(spdx), "SPDX")):
        hits = _secret_hits(text)
        if hits:
            issues.append("%s 导出含秘密形状：%s（修复指引：移除敏感字段）" % (label, hits[:2]))
    boundary = " ".join(str(x) for x in reg.get("claims_boundary") or [])
    if "不声称" not in boundary:
        issues.append("claims_boundary 必须写明不声称认证/合规")
    return issues
