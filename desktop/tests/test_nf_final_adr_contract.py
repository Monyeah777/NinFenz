#!/usr/bin/env python3
"""NF-Final §16.2 仲裁登记契约（WP-04）：12 条裁决 ↔ 机器投影/真源工件互相绑定。

为什么有它：按 ADR-0000，决策正文不进公开仓；公开面只承载可校验登记投影
（protocol/adr/registry.json，nf-adr/1）。所以「登记了」不够——必须证明：
1. 注册表过 core.adr 校验（字段/同主题唯一/supersedes 无环）与 reconcile（evidence 在场）；
2. 方案 §16.2 的 ADR-0001…ADR-0012 在注册表里一条不少、一条不多（plan_ref 一对一），
   ADR-0008 由既有 ADR-010（trust-noscore）覆盖；
3. 每条新裁决有 current 状态、唯一 topic、可证伪 falsifier、≥2 个在场 evidence；
4. 发布边界：decisions/ 无真实决策件、docs/adr/ 不存在（决策正文留私有 Plan 仓）；
5. 变异自证：删裁决/清空 falsifier/改坏 evidence/丢语义词/复制 current topic/丢 plan_ref，
   判据都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "protocol" / "adr" / "registry.json"

#: 方案 ADR → 注册表 ADR（顺序即方案 §16.2 顺序）
PLAN_MAP = {
    "ADR-0001": "ADR-011",
    "ADR-0002": "ADR-012",
    "ADR-0003": "ADR-013",
    "ADR-0004": "ADR-014",
    "ADR-0005": "ADR-015",
    "ADR-0006": "ADR-016",
    "ADR-0007": "ADR-017",
    "ADR-0008": "ADR-010",  # 既有 trust-noscore，不重复登记
    "ADR-0009": "ADR-018",
    "ADR-0010": "ADR-019",
    "ADR-0011": "ADR-020",
    "ADR-0012": "ADR-021",
}

#: 注册表 ADR → (topic, decision 必含语义词)
EXPECTED = {
    "ADR-011": ("plane-independence", ("MUST NOT import", "边界对象")),
    "ADR-012": ("wiki-projection", ("投影", "第二真源", "禁止手改")),
    "ADR-013": ("spec-driven", ("无 spec", "槽位", "fail-closed")),
    "ADR-014": ("agent-adapter", ("adapter", "可替换", "架构中心")),
    "ADR-015": ("ecosystem-reuse", ("in-toto", "Sigstore", "RFC 3161", "不自造")),
    "ADR-016": ("policy-adapter", ("OPA", "Cedar", "不自造")),
    "ADR-017": ("ai-bom-standard", ("CycloneDX", "SPDX", "模型卡")),
    "ADR-018": ("governance-attachment", ("none", "observe", "require", "默认")),
    "ADR-019": ("generated-immutable", ("生成物", "禁止手改", "真源")),
    "ADR-020": ("agent-portability", ("同一 spec", "可移植", "一等验收")),
    "ADR-021": ("self-audit-delivery", ("自扫描", "P0", "Gate")),
}


def _json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _validate(doc):
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
    from core import adr

    return adr.validate_adr(doc)


def publish_violations(paths):
    """公开仓不得出现的决策实体件（ADR-0000：真实件进私有 Plan 仓）。"""
    out = []
    for rel in paths:
        posix = rel.replace("\\", "/")
        if posix.startswith("docs/adr/"):
            out.append(posix)
            continue
        if not posix.startswith("decisions/"):
            continue
        name = posix.rsplit("/", 1)[-1]
        if not name.startswith("ADR-"):
            continue
        number = name[len("ADR-"):].split("-", 1)[0]
        if number not in ("0000",) and not number.startswith("9"):
            out.append(posix)
    return sorted(out)


def plan_adr_issues(doc):
    """12 条方案的 plan_ref 覆盖与一对一。"""
    issues = []
    by_id = {a.get("id"): a for a in doc.get("adrs") or [] if isinstance(a, dict)}
    refs = {a.get("plan_ref"): a.get("id") for a in doc.get("adrs") or []
            if isinstance(a, dict) and a.get("plan_ref")}
    for plan_id, reg_id in PLAN_MAP.items():
        if plan_id not in refs:
            issues.append(f"缺 plan_ref：{plan_id}")
            continue
        if refs[plan_id] != reg_id:
            issues.append(f"{plan_id} 的 plan_ref 指向错误裁决：{refs[plan_id]}≠{reg_id}")
        if reg_id not in by_id:
            issues.append(f"{plan_id} 的注册裁决不在场：{reg_id}")
    extra = sorted(set(refs) - set(PLAN_MAP))
    if extra:
        issues.append(f"存在方案外的 plan_ref：{extra}")
    if len(refs) != len(PLAN_MAP):
        issues.append(f"plan_ref 数量不对：{len(refs)}≠{len(PLAN_MAP)}")
    return issues


def adr_issues(doc):
    """11 条新裁决的字段/语义词/证据判据。"""
    issues = []
    by_id = {a.get("id"): a for a in doc.get("adrs") or [] if isinstance(a, dict)}
    for adr_id, (topic, words) in EXPECTED.items():
        item = by_id.get(adr_id)
        if item is None:
            issues.append(f"缺裁决：{adr_id}")
            continue
        if item.get("status") != "current":
            issues.append(f"{adr_id} 状态不是 current")
        if item.get("topic") != topic:
            issues.append(f"{adr_id} topic 不符：{item.get('topic')}≠{topic}")
        decision = str(item.get("decision") or "")
        for word in words:
            if word not in decision:
                issues.append(f"{adr_id} 的 decision 缺语义词：{word}")
        if len(str(item.get("falsifier") or "").strip()) < 10:
            issues.append(f"{adr_id} 的 falsifier 过短（须可证伪）")
        evidence = item.get("evidence") or []
        if len(evidence) < 2:
            issues.append(f"{adr_id} 的 evidence 少于 2 件")
        for rel in evidence:
            if not (ROOT / str(rel)).exists():
                issues.append(f"{adr_id} 的 evidence 不在场：{rel}")
        if not item.get("plan_ref"):
            issues.append(f"{adr_id} 缺 plan_ref")
    topics = [a.get("topic") for a in doc.get("adrs") or [] if isinstance(a, dict)
              and a.get("status") == "current"]
    if len(topics) != len(set(topics)):
        issues.append("current topic 必须唯一")
    return issues


class NfFinalAdrContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json("protocol/adr/registry.json")

    def test_registry_valid_and_evidence_present(self):
        bundle = _load_bundle()
        self.assertEqual([], _validate(bundle["adr"]))
        self.assertEqual([], _reconcile_findings())
        self.assertEqual([], adr_issues(self.doc))
        self.assertEqual([], plan_adr_issues(self.doc))

    def test_plan_adr_0008_covered_by_existing_trust_noscore(self):
        adr010 = next(a for a in self.doc["adrs"] if a["id"] == "ADR-010")
        self.assertEqual("trust-noscore", adr010["topic"])
        self.assertIn("no_scoring", adr010["decision"])
        self.assertEqual("ADR-0008", adr010.get("plan_ref"))

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
        dropped["adrs"] = [a for a in dropped["adrs"] if a["id"] != "ADR-011"]
        self.assertTrue(any("ADR-011" in i for i in adr_issues(dropped)))
        self.assertTrue(any("ADR-0001" in i for i in plan_adr_issues(dropped)))

        no_falsifier = copy.deepcopy(self.doc)
        next(a for a in no_falsifier["adrs"] if a["id"] == "ADR-013")["falsifier"] = ""
        self.assertTrue(any("falsifier" in i for i in adr_issues(no_falsifier)))

        bad_evidence = copy.deepcopy(self.doc)
        next(a for a in bad_evidence["adrs"] if a["id"] == "ADR-015")["evidence"] = [
            "desktop/src/core/nonexistent_zzz.py"]
        self.assertTrue(any("不在场" in i for i in adr_issues(bad_evidence)))

        lost_word = copy.deepcopy(self.doc)
        next(a for a in lost_word["adrs"] if a["id"] == "ADR-012")["decision"] = "wiki 很重要"
        self.assertTrue(any("语义词" in i for i in adr_issues(lost_word)))

        dup_topic = copy.deepcopy(self.doc)
        next(a for a in dup_topic["adrs"] if a["id"] == "ADR-014")["topic"] = "spec-driven"
        self.assertTrue(any("topic" in i for i in adr_issues(dup_topic)))
        self.assertTrue(any("两条 current" in i for i in _validate(dup_topic)))

        wrong_ref = copy.deepcopy(self.doc)
        next(a for a in wrong_ref["adrs"] if a["id"] == "ADR-019")["plan_ref"] = "ADR-0001"
        self.assertTrue(any("ADR-0010" in i for i in plan_adr_issues(wrong_ref)))


def _load_bundle():
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
    from core import adr

    return adr.load(str(ROOT))


def _reconcile_findings():
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
    from core import adr

    return adr.reconcile(str(ROOT))["findings"]


if __name__ == "__main__":
    unittest.main()
