#!/usr/bin/env python3
"""Trust Fabric 裁决登记契约（WP-04）：六条裁决与冻结工件互相绑定。

为什么有它：本仓的决策正文按 ADR-0000 留私有档案，公开仓只承载**可校验登记投影**
（protocol/adr/registry.json）。因此「裁决存在」不够——必须证明每条裁决都指向真实、
在场的 schema/向量/实现，且没有决策实体件混进公开仓。

判据：
1. 注册表过 core.adr 校验（字段/同主题唯一/supersedes 无环）与 reconcile（evidence 在场）；
2. ADR-005…010 六条 trust 裁决齐备，topic 唯一，decision 含该裁决的关键语义词；
3. 裁决 ↔ 冻结工件双向绑定：DSSE schema、claim bundle schema、anchor schema、entity/policy
   schema、verify schema 的 no_scoring 恒真、trust_vectors 的 pae/merkle/entity/level 族；
4. 发布边界：decisions/ 无真实决策件、docs/adr/ 不存在（决策正文不进公开仓）；
5. 变异自证：删裁决/清空 falsifier/改坏 evidence/复制 current topic/改丢语义词/
   注入决策实体件/删向量族，判据都必须红。
"""
import copy
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "protocol" / "adr" / "registry.json"
VECTORS = ROOT / "results" / "trust" / "trust_vectors.json"

#: ADR id → (topic, decision 必含语义词, 被绑定的工件)
EXPECTED = {
    "ADR-005": ("trust-dsse", ("PAE", "DSSE", "字节"), "protocol/trust/dsse.schema.json"),
    "ADR-006": ("trust-bundle", ("RFC 6962", "bundle_id", "0x00"),
                "protocol/trust/claim-bundle.schema.json"),
    "ADR-007": ("trust-time", ("RFC 3161", "本地时钟"), "protocol/trust/anchor.schema.json"),
    "ADR-008": ("trust-witness", ("witness", "T3"), "protocol/trust/anchor.schema.json"),
    "ADR-009": ("trust-types", ("fail-closed", "issuer"), "protocol/trust/entity.schema.json"),
    "ADR-010": ("trust-noscore", ("no_scoring", "评分"), "protocol/trust/verify.schema.json"),
}
TRUST_IDS = tuple(EXPECTED)
DECISION_DOC = re.compile(r"^ADR-(\d{4})-.+\.md$")


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def publish_violations(paths) -> list:
    """公开仓不得出现的决策实体件（ADR-0000 政策：真实件进私有 Plan 仓）。"""
    out = []
    for rel in paths:
        posix = rel.replace("\\", "/")
        if posix.startswith("docs/adr/"):
            out.append(posix)
            continue
        match = DECISION_DOC.match(posix.rsplit("/", 1)[-1]) if "/" in posix else None
        if match and posix.startswith("decisions/"):
            number = match.group(1)
            if number != "0000" and not number.startswith("9"):
                out.append(posix)
    return sorted(out)


def trust_adr_issues(doc) -> list:
    issues = []
    adrs = {a.get("id"): a for a in doc.get("adrs") or [] if isinstance(a, dict)}
    for adr_id, (topic, words, artifact) in EXPECTED.items():
        item = adrs.get(adr_id)
        if item is None:
            issues.append(f"缺 trust 裁决：{adr_id}")
            continue
        if item.get("status") != "current":
            issues.append(f"{adr_id} 状态不是 current")
        if item.get("topic") != topic:
            issues.append(f"{adr_id} topic 不符：{item.get('topic')}")
        decision = str(item.get("decision") or "")
        for word in words:
            if word not in decision:
                issues.append(f"{adr_id} 的 decision 缺语义词：{word}")
        if len(str(item.get("falsifier") or "").strip()) < 10:
            issues.append(f"{adr_id} 的 falsifier 过短（须可证伪）")
        evidence = item.get("evidence") or []
        if not evidence:
            issues.append(f"{adr_id} 缺 evidence")
        for rel in evidence:
            if not (ROOT / str(rel)).exists():
                issues.append(f"{adr_id} 的 evidence 不在场：{rel}")
        if artifact not in [str(rel) for rel in evidence]:
            issues.append(f"{adr_id} 未把绑定工件列入 evidence：{artifact}")
    return issues


def binding_issues(vectors) -> list:
    """裁决语义必须能在冻结工件里找到对应面。"""
    issues = []
    families = vectors.get("families") or {}
    for need in ("pae", "merkle", "entity", "level"):
        if families.get(need, 0) < 1:
            issues.append(f"向量集缺族 {need}（裁决绑定失效）")
    rules = vectors.get("rules") or {}
    if "0x00" not in str(rules.get("merkle", "")):
        issues.append("向量规则未写 RFC 6962 叶前缀 0x00")
    if "DSSEv1" not in str(rules.get("pae", "")):
        issues.append("向量规则未写 DSSEv1")
    dsse = _json("protocol/trust/dsse.schema.json")
    if dsse["properties"]["signatures"]["minItems"] != 1:
        issues.append("DSSE schema 未要求至少 1 签名")
    bundle = _json("protocol/trust/claim-bundle.schema.json")
    if "bundle_id" not in bundle["required"]:
        issues.append("claim bundle 未把 bundle_id 列为必填")
    proof = bundle["properties"]["inclusion_proofs"]["items"]["properties"]["proof"]
    if proof.get("maxItems") != 64:
        issues.append("claim bundle 的 proof 深度上限不是 64")
    anchor = _json("protocol/trust/anchor.schema.json")
    if len(anchor["$defs"]["anchor"]["oneOf"]) != 4:
        issues.append("anchor schema 不是四类锚 oneOf")
    policy = _json("protocol/trust/policy.schema.json")
    if "issuers" not in policy["required"]:
        issues.append("policy schema 未要求 issuers")
    verify = _json("protocol/trust/verify.schema.json")
    if verify["properties"]["no_scoring"].get("const") is not True:
        issues.append("verify schema 的 no_scoring 不是恒真")
    return issues


class TrustAdrContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json("protocol/adr/registry.json")
        cls.vectors = _json("results/trust/trust_vectors.json")

    def test_registry_valid_and_evidence_present(self):
        import sys
        sys.path.insert(0, str(ROOT / "desktop" / "src"))
        from core import adr

        bundle = adr.load(str(ROOT))
        self.assertEqual([], adr.validate_adr(bundle["adr"]))
        self.assertEqual([], adr.reconcile(str(ROOT))["findings"])
        self.assertEqual([], trust_adr_issues(self.doc))

    def test_six_trust_adrs(self):
        ids = [a["id"] for a in self.doc["adrs"]]
        self.assertEqual(sorted(TRUST_IDS), sorted([i for i in ids if i in TRUST_IDS]))
        self.assertEqual(len(TRUST_IDS), len([a for a in self.doc["adrs"]
                                             if a["topic"].startswith("trust-")]))
        topics = [a["topic"] for a in self.doc["adrs"]]
        self.assertEqual(len(topics), len(set(topics)), "current topic 必须唯一")

    def test_decisions_bind_to_frozen_artifacts(self):
        self.assertEqual([], binding_issues(self.vectors))

    def test_publish_boundary(self):
        real = []
        decisions = ROOT / "decisions"
        if decisions.is_dir():
            real += [f"decisions/{p.name}" for p in decisions.glob("*.md")]
        if (ROOT / "docs" / "adr").exists():
            real.append("docs/adr/")
        self.assertEqual([], publish_violations(real), "公开仓出现决策实体件")
        self.assertEqual([], publish_violations(["decisions/ADR-0000-policy.md",
                                                 "decisions/ADR-9000-template.md"]))
        self.assertEqual(["decisions/ADR-0012-x.md", "docs/adr/0003-y.md"],
                         publish_violations(["decisions/ADR-0012-x.md",
                                             "docs/adr/0003-y.md"]))

    def test_contract_catches_mutations(self):
        dropped = copy.deepcopy(self.doc)
        dropped["adrs"] = [a for a in dropped["adrs"] if a["id"] != "ADR-007"]
        self.assertTrue(any("ADR-007" in i for i in trust_adr_issues(dropped)))

        no_falsifier = copy.deepcopy(self.doc)
        next(a for a in no_falsifier["adrs"] if a["id"] == "ADR-009")["falsifier"] = ""
        self.assertTrue(any("falsifier" in i for i in trust_adr_issues(no_falsifier)))

        bad_evidence = copy.deepcopy(self.doc)
        next(a for a in bad_evidence["adrs"] if a["id"] == "ADR-008")["evidence"] = [
            "desktop/src/core/nonexistent_xyz.py"]
        self.assertTrue(any("不在场" in i for i in trust_adr_issues(bad_evidence)))

        lost_word = copy.deepcopy(self.doc)
        next(a for a in lost_word["adrs"] if a["id"] == "ADR-005")["decision"] = "自定义信封"
        self.assertTrue(any("PAE" in i for i in trust_adr_issues(lost_word)))

        wrong_topic = copy.deepcopy(self.doc)
        next(a for a in wrong_topic["adrs"] if a["id"] == "ADR-006")["topic"] = "trust-dsse"
        self.assertTrue(any("两条 current" in i
                            for i in _validate(wrong_topic)))

        no_pae = copy.deepcopy(self.vectors)
        no_pae["vectors"] = [v for v in no_pae["vectors"] if v["family"] != "pae"]
        no_pae["families"] = {"canonical": 5, "domain": 4}
        self.assertTrue(any("pae" in i for i in binding_issues(no_pae)))


def _validate(doc) -> list:
    import sys
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
    from core import adr

    return adr.validate_adr(doc)


if __name__ == "__main__":
    unittest.main()
