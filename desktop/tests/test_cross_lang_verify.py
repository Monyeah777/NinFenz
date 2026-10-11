# -*- coding: utf-8 -*-
"""P-C2 仲裁判据：规范为权威、多数票只作定位线索（含 SPEC-GAP 分支）。"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("clv", str(ROOT / "scripts" / "cross_lang_verify.py"))
clv = importlib.util.module_from_spec(_SPEC)
sys.modules["clv"] = clv
_SPEC.loader.exec_module(clv)


def _vectors(pairs):
    """pairs: {(id, lang): status} → verify 形状的 rows。"""
    rows = {}
    for (vid, lang), st in pairs.items():
        rows.setdefault(vid, {"id": vid, "langs": {}})
        rows[vid]["langs"][lang] = {"status": st}
    return [rows[k] for k in sorted(rows)]


class ArbitrateTest(unittest.TestCase):
    def test_all_agree(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "PASS"}))
        self.assertEqual("PASS", got["outcome"])

    def test_single_deviation_is_suspect(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "FAIL",
                                      ("v", "csharp"): "PASS"}))
        self.assertEqual("FAIL", got["outcome"])
        self.assertEqual(["v/rust"], got["suspects"])
        self.assertIn("线索", got["clue"])

    def test_majority_deviation_is_spec_gap_not_verdict(self):
        got = clv.arbitrate(_vectors({("v", "python"): "FAIL", ("v", "rust"): "FAIL",
                                      ("v", "csharp"): "PASS"}))
        self.assertEqual("SPEC-GAP", got["outcome"])
        self.assertIn("不得", got["clue"])

    def test_all_unknown_makes_no_claim(self):
        got = clv.arbitrate(_vectors({("v", "rust"): "UNKNOWN", ("v", "csharp"): "UNKNOWN"}))
        self.assertEqual("UNKNOWN", got["outcome"])
        self.assertIn("不下结论", got["clue"])

    def test_single_available_pass_is_pass_not_unknown(self):
        got = clv.arbitrate(_vectors({("v", "python"): "PASS", ("v", "rust"): "UNKNOWN"}))
        self.assertEqual("PASS", got["outcome"])


class RealVectorTest(unittest.TestCase):
    def test_repo_vector_arbitrates(self):
        doc = clv.json.loads(
            (ROOT / "protocol/generated/test_vectors/jcs_basic.json").read_text(encoding="utf-8"))
        rep = clv.verify(doc, root=str(ROOT))
        self.assertEqual("PASS", rep["arbitration"]["outcome"], rep["arbitration"])
        self.assertEqual("UNKNOWN", rep["verdict"], "工具链缺席时整体仍须 UNKNOWN")


if __name__ == "__main__":
    unittest.main()
