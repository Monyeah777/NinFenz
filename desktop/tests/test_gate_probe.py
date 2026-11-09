"""门禁负向用例探针判据：比率可算、命名代理不空转、清单与数据一致。

依据（第 76 轮）：设计纪律「红不了的门禁等于没有门禁」，但仓库只有零星变异测试。
先量后改：探针按命名代理统计每个闸门里的拒绝型测试，只出比率与缺口清单，不做判定。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import gate_probe as gp  # noqa: E402


class GateProbeTest(unittest.TestCase):
    def test_ratio_is_computable_and_consistent(self):
        doc = gp.build()
        self.assertEqual("nf-gate-negative-tests/1", doc["schema"])
        self.assertGreaterEqual(doc["gates"], 15)
        covered = sum(1 for r in doc["rows"] if r["has_negative"])
        self.assertEqual(covered, doc["gates_with_negative"])
        self.assertAlmostEqual(covered / doc["gates"], doc["ratio"], places=6)
        self.assertEqual([r["id"] for r in doc["rows"] if not r["has_negative"]],
                         doc["missing"])

    def test_proxy_has_catch_power(self):
        """命名代理不空转：真实缺失闸门里必须有至少一条（否则代理失效）。"""
        doc = gp.build()
        self.assertTrue(doc["missing"], "所有闸门都有拒绝型用例——代理可能已失效，需复核")
        self.assertLess(doc["ratio"], 1.0)

    def test_negative_detector_recognises_known_names(self):
        self.assertEqual([], [n for n in ["test_happy_path"] if gp.NEGATIVE_HINTS
                                    and any(h in n for h in gp.NEGATIVE_HINTS)])
        hit = [n for n in ["test_bad_input_is_rejected"]
               if any(h in n.lower() for h in gp.NEGATIVE_HINTS)]
        self.assertEqual(["test_bad_input_is_rejected"], hit)


    def test_committed_result_is_fresh(self):
        """已提交结果必须与重算一致（闸门或命名变了却忘刷新即红）。"""
        import json
        path = ROOT / "results" / "ccos" / "gate_negative_tests.json"
        self.assertTrue(path.is_file(), "缺结果件：先跑 scripts/gate_probe.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(gp.build(), committed, "结果已陈旧，重跑 --write")


if __name__ == "__main__":
    unittest.main()
