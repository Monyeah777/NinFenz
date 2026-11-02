"""域包 12 条细分规则机读化：编译稳定、字段抽取、覆盖统计。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import domain_rules as dr  # noqa: E402


class DomainRulesTest(unittest.TestCase):
    def test_build_is_stable_and_complete(self):
        a = dr.build_rules("大语言模型域包", str(ROOT))
        b = dr.build_rules("大语言模型域包", str(ROOT))
        self.assertEqual(12, len(a["rules"]))
        self.assertEqual(a["rule_digest"], b["rule_digest"], "规则表必须确定性")
        self.assertGreaterEqual(a["machine_fields"], 1)
        self.assertTrue(all(r["id"] and r["name"] for r in a["rules"]))

    def test_pack_asset_covers_all_rules(self):
        rules = dr.build_rules("大语言模型域包", str(ROOT))
        text = (ROOT / "community" / "大语言模型域包" / "assets" / "DOMAIN_SPEC.md").read_text(
            encoding="utf-8")
        cov = dr.coverage(text, rules)
        self.assertEqual(12, cov["names_hit"])
        self.assertGreaterEqual(cov["fields_hit"], 1)

    def test_unrelated_doc_low_coverage(self):
        rules = dr.build_rules("大语言模型域包", str(ROOT))
        cov = dr.coverage((ROOT / "docs" / "mcp.md").read_text(encoding="utf-8"), rules)
        self.assertLess(cov["names_hit"], 12)
