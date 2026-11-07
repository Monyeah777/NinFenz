"""几何提示同步判据：用「标签里记录的尺寸」替代频谱模板做几何同步。

本轮要锁住两件事：
① **正结果**：记录尺寸 + 缩放反解 + 块偏移搜索，能把 0.85–1.25× 缩放、裁剪 10%、JPEG q=70 全部读回；
② **负结果**：周期模板的谱峰对缩放不变（peaks_moved 必须为 False），所以「频谱模板估缩放」这条路
   在数学上不成立——不许以后有人再把它写成「待实现」。
③ 剩余边界：拍屏模拟（0.9× + blur + q80）仍读不回——不假装解决。
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

import watermark_geometry_probe as probe  # noqa: E402


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：几何探针跳过（不冒充已验）")
class GeometryDeterminismTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(probe.render(probe.build_probe()),
                         probe.render(probe.build_probe()))

    def test_committed_results_match_rebuild(self):
        path = ROOT / probe.OUT_REL
        if not path.is_file():
            self.skipTest("探针结果尚未提交（先跑 --write）")
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(probe.render(recorded), probe.render(probe.build_probe()))


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：几何探针跳过（不冒充已验）")
class GeometryRecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = probe.build_probe()
        cls.rows = {row["id"]: row for row in cls.doc["attacks"]}

    def test_clean_round_trip(self):
        self.assertTrue(self.doc["clean"]["ok"])
        self.assertGreater(self.doc["clean"]["psnr_db"], 30.0)

    def test_scaling_is_recovered_with_exact_estimate(self):
        for aid, actual in (("scale_0.85", 0.85), ("scale_0.9", 0.9), ("scale_0.95", 0.95),
                            ("scale_1.1", 1.1), ("scale_1.25", 1.25)):
            row = self.rows[aid]
            self.assertTrue(row["ok"], aid)
            est = row["scale_est"][0]
            self.assertLess(abs(est - actual), 0.01, aid + " 缩放估计偏差过大")

    def test_crop_is_recovered(self):
        self.assertTrue(self.rows["crop_10"]["ok"], "裁剪 10% 应能靠补边+偏移搜索读回")

    def test_jpeg_is_recovered(self):
        self.assertTrue(self.rows["jpeg_70"]["ok"])

    def test_screenshot_is_still_a_boundary(self):
        """诚实边界：拍屏（缩放+模糊+JPEG）仍读不回，不冒充已解决。"""
        self.assertFalse(self.rows["screenshot_sim"]["ok"])

    def test_template_invariance_negative_result(self):
        """负结果锁死：周期模板谱峰不随缩放移动 → 频谱模板无法估缩放。"""
        block = self.doc["template_invariance"]
        self.assertFalse(block["peaks_moved"], "谱峰竟然移动了——数学结论要重写")
        self.assertIn("无法估缩放", block["note"])


if __name__ == "__main__":
    unittest.main()
