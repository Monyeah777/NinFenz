#!/usr/bin/env python3
"""法务/许可/出口 + 开源治理契约（NF-Final WP-0C，P1 盲区 BL-07/BL-10）。

真源 = `protocol/legal.json`（`nf-legal/1`）；人读面 = `LEGAL.md` + `GOVERNANCE.md` +
`docs/legal/{TRADEMARK,CONTRACTS,EXPORT}.md`；审计入口 `scripts/legal_audit.py`。
判据：
1. 许可与仓内文本一致（SPDX=MIT / LICENSE 文本 / REUSE 聚合与投稿面 override / LicenseRef 文本）；
2. 第三方：NOTICE/生成器/requirements/SBOM 在场，NOTICE 有实际清单行；运行时零第三方由
   pyproject 与 npm package.json 机检；
3. 治理：贡献/行为准则/维护者/安全/支持/GOVERNANCE/CHANGELOG 与发布/废弃/SemVer/Scorecard 登记齐全；
4. 商标/署名：规则与非背书条款成文；合同四类模板登记且状态诚实；出口加密组件逐件在场；
5. 不越级：不提供法律意见、不声称合规/认证；方案假设（AGPL/双许可）与实际（MIT+LicenseRef）偏差显式登记；
6. 变异自证：改 SPDX/删治理件/缺合同类型/加密组件不在场/去掉法律意见否定/坏 REQUIREMENTS 路径，
   审计都必须红。
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import legal  # noqa: E402

REG = ROOT / "protocol" / "legal.json"
DOCS = {
    "LEGAL": ROOT / "LEGAL.md",
    "GOVERNANCE": ROOT / "GOVERNANCE.md",
    "TRADEMARK": ROOT / "docs" / "legal" / "TRADEMARK.md",
    "CONTRACTS": ROOT / "docs" / "legal" / "CONTRACTS.md",
    "EXPORT": ROOT / "docs" / "legal" / "EXPORT.md",
}
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class LegalContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _json(REG)
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_registry_valid_and_audit_clean(self):
        self.assertEqual([], legal.validate(self.doc, str(ROOT)))
        issues, facts = legal.audit(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual("MIT", facts["license"])
        self.assertEqual([], facts["runtime_deps"])
        self.assertIn(facts["npm_deps"], (None, {}))

    def test_license_matches_repo_text(self):
        lic = self.doc["license"]
        self.assertEqual("MIT", lic["spdx"])
        self.assertIn("MIT License", _text(ROOT / "LICENSE"))
        self.assertTrue((ROOT / lic["text"]).is_file())
        community = lic["community_license"]
        self.assertTrue(community["spdx"].startswith("LicenseRef-"))
        self.assertTrue((ROOT / community["text"]).is_file())
        self.assertEqual(3, len(legal._reuse_annotations(str(ROOT))),
                         "REUSE annotation 结构变化须同步判据")

    def test_plan_deviation_recorded(self):
        dev = self.doc["license"]["plan_deviation"]
        self.assertIn("AGPL", dev)
        self.assertIn("不虚构", dev)
        self.assertIn("AGPL", self.texts["LEGAL"])
        self.assertIn("偏差", self.texts["LEGAL"])

    def test_docs_present_and_cross_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        for contract in self.doc["contracts"]:
            self.assertIn(contract["id"], self.texts["CONTRACTS"])
        for keyword in ("服务", "试点", "保密", "数据处理"):
            self.assertIn(keyword, self.texts["CONTRACTS"])
        for rel in self.doc["export"]["crypto_components"]:
            self.assertIn(Path(rel).name, self.texts["EXPORT"], "加密组件未入文档：%s" % rel)
        for key in ("contributing", "code_of_conduct", "maintainers", "security",
                    "support", "changelog"):
            self.assertIn(Path(self.doc["oss_governance"]["files"][key]).name,
                          self.texts["GOVERNANCE"])
        self.assertIn("GOVERNANCE", self.texts["GOVERNANCE"])
        self.assertIn("不得", self.texts["TRADEMARK"])
        self.assertIn("legal_audit.py", self.texts["LEGAL"])

    def test_third_party_notice_and_governance(self):
        third = self.doc["third_party"]
        notice = _text(ROOT / third["notice"])
        self.assertGreaterEqual(
            sum(1 for line in notice.splitlines() if line.strip().startswith("| `")), 10,
            "NOTICE 清单行过少（生成器未跑？）")
        self.assertIn("请勿手改", notice)
        self.assertTrue((ROOT / third["generator"]).is_file())
        for rel in third["requirements"]:
            self.assertTrue((ROOT / rel).is_file(), "固定清单不在场：%s" % rel)
        self.assertTrue((ROOT / self.doc["oss_governance"]["scorecard"]["workflow"]).is_file())
        self.assertIn("CI-only", self.doc["oss_governance"]["scorecard"]["status"])

    def test_claims_boundary_and_no_overclaim(self):
        boundary = " ".join(self.doc["claims_boundary"])
        for word in ("不提供法律意见", "不声称合规"):
            self.assertIn(word, boundary)
        for key, text in self.texts.items():
            for line in text.splitlines():
                for word in ("不可抵赖", "认证"):
                    if word in line:
                        self.assertTrue(any(m in line for m in NEGATION),
                                        "%s 禁用词未在否定语境：%s" % (key, line.strip()))

    def test_contracts_templates(self):
        types = sorted(c["type"] for c in self.doc["contracts"])
        self.assertEqual(sorted(legal.CONTRACT_TYPES), types)
        for contract in self.doc["contracts"]:
            self.assertEqual("template-in-doc", contract["status"])
            self.assertTrue((ROOT / contract["path"]).is_file())

    def test_export_surface(self):
        exp = self.doc["export"]
        self.assertGreaterEqual(len(exp["crypto_components"]), 5)
        self.assertGreaterEqual(len(exp["review_trigger"]), 2)
        self.assertIn("不构成", exp["not_legal_advice"])

    def test_mutations_red(self):
        wrong_spdx = copy.deepcopy(self.doc)
        wrong_spdx["license"]["spdx"] = "AGPL-3.0-only"
        self.assertTrue(legal.validate(wrong_spdx, str(ROOT)), "SPDX 与文本不一致必须红")

        missing_governance = copy.deepcopy(self.doc)
        missing_governance["oss_governance"]["files"]["governance"] = "docs/nonexistent_zzz.md"
        self.assertTrue(legal.validate(missing_governance, str(ROOT)), "治理件不在场必须红")

        missing_contract = copy.deepcopy(self.doc)
        missing_contract["contracts"] = missing_contract["contracts"][:3]
        self.assertTrue(legal.validate(missing_contract, str(ROOT)), "缺合同类型必须红")

        bad_component = copy.deepcopy(self.doc)
        bad_component["export"]["crypto_components"] = ["desktop/src/core/nonexistent_zzz.py"]
        self.assertTrue(legal.validate(bad_component, str(ROOT)), "加密组件不在场必须红")

        no_legal_advice = copy.deepcopy(self.doc)
        no_legal_advice["claims_boundary"] = ["不声称合规"]
        self.assertTrue(legal.validate(no_legal_advice, str(ROOT)), "缺法律意见否定必须红")

        bad_requirements = copy.deepcopy(self.doc)
        bad_requirements["third_party"]["requirements"] = [".github/nonexistent.txt"]
        self.assertTrue(legal.validate(bad_requirements, str(ROOT)), "坏 REQUIREMENTS 路径必须红")

        bad_override = copy.deepcopy(self.doc)
        bad_override["license"]["community_license"]["scope"] = ["nowhere/**"]
        self.assertTrue(legal.validate(bad_override, str(ROOT)), "REUSE override 缺覆盖必须红")

        no_endorsement = copy.deepcopy(self.doc)
        no_endorsement["trademark"]["no_endorsement"] = "官方认证"
        self.assertTrue(legal.validate(no_endorsement, str(ROOT)), "缺非背书条款必须红")


if __name__ == "__main__":
    unittest.main()
