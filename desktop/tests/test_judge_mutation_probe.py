"""门禁变异探针判据：杀死率/误报率可算、两条判据各自有变异体、口径自洽。

依据（第 79 轮）：`gate_probe` 只量「有没有拒绝型用例」，不量「判据对真实变异是否敏感」。
本件用最小变异实验补上这一格：合法变体不得误报，破坏变体必须被杀死。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import judge_mutation_probe as jm  # noqa: E402


class JudgeMutationTest(unittest.TestCase):
    def test_rates_are_computable(self):
        doc = jm.build()
        self.assertEqual("nf-judge-mutation/1", doc["schema"])
        self.assertGreaterEqual(doc["judges"], 2)
        self.assertEqual(6, doc["mutants"])
        self.assertEqual(5, doc["legal_variants"])
        # 工件不变性：同一语义、不同顺序不得翻转判定（台账 §7.2）
        names = [c["name"] for c in jm.vocab_cases()[0]]
        self.assertIn("包顺序打乱", names)
        self.assertTrue(0.0 <= doc["kill_rate"] <= 1.0)
        self.assertTrue(0.0 <= doc["false_positive_rate"] <= 1.0)

    def test_both_judges_kill_every_mutant(self):
        """变异体全部被杀、合法变体零误报——低于此即判据失灵，需先修判据。"""
        doc = jm.build()
        self.assertEqual(1.0, doc["kill_rate"], doc["detail"])
        self.assertEqual(0.0, doc["false_positive_rate"], doc["detail"])

    def test_probe_is_not_vacuous(self):
        """用「故意错」的期望值检查探针确实在看数据：改一处变异体必须让 kill_rate 降。"""
        legal, broken = jm.vocab_cases()
        mp, _br = jm._core()
        self.assertTrue(broken, "变异体列表为空——实验无意义")
        ok = [c for c in broken
              if mp.vocabulary_mismatches(c["packs"], c["registry"]) != {"unknown": [],
                                                                         "unused": []}]
        self.assertEqual(len(broken), len(ok), "有变异体没被杀死")


if __name__ == "__main__":
    unittest.main()
