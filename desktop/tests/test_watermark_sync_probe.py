"""同步层探针判据：把「网格同步能做什么、不能做什么」锁成断言。

上一轮探针证明关系嵌入扛 JPEG；本轮加同步字 + 网格搜索，判据要证明：
① 干净图与 JPEG 下同步正常、payload 可读回；
② 整数比放大（1.25×）能对齐——说明同步机制本身在工作；
③ **非整数重采样（0.85/0.9/1.1×）、裁剪、拍屏对齐不上**（对齐分封顶 ~64–69%），
   即「固定 8×8 块网格 + 搜索」这条路不够，v1 必须换内容同步（SIFT/特征点）或频谱模板。
④ 确定性 / 可复算。
这条 ③ 是负结果，但它是**可复算的负结果**——比「再试试」有用。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401
    HAVE_DEPS = True
except ImportError:                                     # pragma: no cover
    HAVE_DEPS = False

import watermark_sync_probe as probe  # noqa: E402


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：同步探针跳过（不冒充已验）")
class SyncProbeDeterminismTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(probe.render(probe.build_probe()),
                         probe.render(probe.build_probe()))

    def test_committed_results_match_rebuild(self):
        path = ROOT / probe.OUT_REL
        if not path.is_file():
            self.skipTest("探针结果尚未提交（先跑 --write）")
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(probe.render(recorded), probe.render(probe.build_probe()))


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：同步探针跳过（不冒充已验）")
class SyncCapabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = probe.build_probe()
        cls.rows = {row["id"]: row for row in cls.doc["attacks"]}

    def test_clean_and_jpeg_round_trip(self):
        self.assertTrue(self.doc["clean"]["ok"])
        self.assertGreaterEqual(self.doc["clean"]["sync_score"], 120)
        self.assertTrue(self.rows["jpeg_70"]["ok"])
        self.assertGreaterEqual(self.rows["jpeg_70"]["sync_score"], 120)

    def test_upscale_is_recovered(self):
        row = self.rows["scale_1.25"]
        self.assertTrue(row["ok"], "整数比放大应能对齐")
        self.assertEqual(1.25, row["recovered_scale"])

    def test_non_integer_resample_is_not_recovered(self):
        """负结果判据：非整数重采样对不齐（防止把「没做」写成「已解决」）。"""
        for aid in ("scale_0.85", "scale_0.9", "scale_1.1", "screenshot_sim"):
            row = self.rows[aid]
            self.assertFalse(row["ok"], aid + " 竟然对齐了——结论要重述")
            self.assertFalse(row["aligned"], aid)
            self.assertLess(row["sync_score"], 110, aid + " 对齐分不该接近满分")

    def test_crop_is_not_recovered(self):
        row = self.rows["crop_10"]
        self.assertFalse(row["ok"])
        self.assertLess(row["sync_score"], 110)

    def test_conclusion_is_recorded(self):
        conclusion = self.doc["conclusion"]
        self.assertIn("next", conclusion)
        self.assertIn("内容同步", conclusion["downscale_and_crop"])


if __name__ == "__main__":
    unittest.main()
