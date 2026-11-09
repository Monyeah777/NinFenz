"""core 引用面判据：未引用模块数只减不增（第 159 轮）。

依据（第 158 轮测量）：355 个 core 模块里 34 个没被任何测试文件按名字提到。
这是**代理指标**（粗粒度名字匹配），但足以当棘轮：新增 core 模块若没人提到，数量就会涨。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import core_judge_map as cm  # noqa: E402

#: 第 159 轮冻结的「未被测试提到」的 core 模块数（只减不增）
FROZEN_UNREFERENCED = 34


class CoreJudgeMapTest(unittest.TestCase):
    def test_collect_is_deterministic(self):
        first = cm.collect(ROOT)
        second = cm.collect(ROOT)
        self.assertEqual("nf-core-judge-map/1", first["schema"])
        self.assertEqual(first, second, "两次扫描必须一致")
        self.assertEqual(first["modules"], len(first["entries"]))
        self.assertGreater(first["modules"], 300, "core 模块太少（判据可能已失效）")

    def test_committed_map_is_fresh(self):
        path = ROOT / cm.OUT_REL
        self.assertTrue(path.is_file(), "缺映射件：先跑 scripts/core_judge_map.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(cm.render(cm.collect(ROOT)), cm.render(committed),
                         "core 引用面已陈旧，重跑 --write")

    def test_unreferenced_does_not_grow(self):
        doc = cm.collect(ROOT)
        self.assertLessEqual(doc["unreferenced"], FROZEN_UNREFERENCED,
                             "未引用的 core 模块变多了（修复指引：让某个测试提到新模块，"
                             "或把已有测试的覆盖写进提交说明）")

    def test_metric_is_name_level_and_says_so(self):
        """口径自证：判定只按名字出现，且 note 必须写明这是代理指标。"""
        doc = cm.collect(ROOT)
        self.assertIn("代理指标", doc["note"])
        self.assertNotIn("import", doc["note"], "note 不应暗示做了导入图分析")


if __name__ == "__main__":
    unittest.main()
