"""红证据登记判据：可复算、可核、棘轮只减不增（第 153 轮）。

依据（第 149/151/152 轮）：389 个测试模块里只有 20 个能拿出「会红」的硬证据。
本件把口子焊住：登记表必须与现场一致，且 `without_evidence` 不许变大。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import judge_red_evidence as jr  # noqa: E402

#: 第 153 轮冻结的「无硬证据」模块数（只减不增；`naming` 只是代理指标，不算证据）。
#: 149 = 本件自身也落进 none（登记表的判据模块自己没被变异探针收录——如实计入，不豁免）。
FROZEN_WITHOUT_EVIDENCE = 149


class JudgeRedEvidenceTest(unittest.TestCase):
    def test_collect_is_deterministic(self):
        first = jr.collect(ROOT)
        second = jr.collect(ROOT)
        self.assertEqual("nf-judge-red-evidence/1", first["schema"])
        self.assertEqual(first, second, "两次扫描必须一致")
        self.assertEqual(first["modules"], len(first["entries"]))
        self.assertGreater(first["modules"], 300, "模块太少（判据可能已失效）")

    def test_committed_registry_is_fresh(self):
        path = ROOT / jr.OUT_REL
        self.assertTrue(path.is_file(), "缺登记表：先跑 scripts/judge_red_evidence.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(jr.render(jr.collect(ROOT)), jr.render(committed),
                         "登记表已陈旧，重跑 --write")

    def test_without_evidence_does_not_grow(self):
        """棘轮：无硬证据的模块数只减不增（允许新增模块暂时落进 none，但总数不许涨）。"""
        doc = jr.collect(ROOT)
        self.assertLessEqual(doc["without_evidence"], FROZEN_WITHOUT_EVIDENCE,
                             "无硬证据模块变多了（修复指引：给新模块补一条真会红的判据，"
                             "或把已有的拒绝型用例登记进 gate_probe）")

    def test_naming_is_not_counted_as_evidence(self):
        """口径自证：`naming` 档的模块不得出现在硬证据计数里。"""
        doc = jr.collect(ROOT)
        naming = [e for e in doc["entries"] if e["source"] == "naming"]
        hard = [e for e in doc["entries"] if e["source"] in ("negative_case", "mutation")]
        self.assertEqual(doc["with_evidence"], len(hard))
        self.assertEqual(doc["suspect"], len(naming))
        self.assertTrue(naming, "一个 naming 都没有（关键词口径可能失效）")


if __name__ == "__main__":
    unittest.main()
