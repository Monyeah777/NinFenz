"""拍屏水印第五轮探针判据：把「加大强度也救不回」写成可复算边界。

前四轮已证：关系嵌入扛 JPEG/缩放/裁剪，拍屏失败。本轮扫描 10 组配置（delta 24–48 /
块 8–16 / 中频与低频）后，判据要锁住三件事：
① 干净图在所有配置下都能读回（否则是探针自身坏了）；
② **没有任何配置能在拍屏链（0.9×+blur+q80）下读回** —— 若哪天有配置通过了，
   这条判据会红，逼迫重新表述结论（而不是悄悄改口）；
③ 可见性代价有界：PSNR 不得低于 30 dB（不能靠「糊成一片」换鲁棒）。
"""
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

import watermark_ecc_probe as probe  # noqa: E402


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：拍屏探针跳过（不冒充已验）")
class EccProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = probe.build_probe()

    def test_clean_always_round_trips(self):
        for row in self.doc["rows"]:
            self.assertTrue(row["clean_ok"], (row["delta"], row["block"], row["freq"]))

    def test_visibility_cost_is_bounded(self):
        for row in self.doc["rows"]:
            self.assertGreater(row["psnr_db"], 30.0, (row["delta"], row["block"]))

    def test_no_config_survives_screenshot(self):
        """负结果锁死：若某配置通过拍屏链，判据红——结论必须重写。"""
        self.assertFalse(self.doc["verdict"]["any_survives_screenshot"],
                         "出现可扛拍屏的配置，需重写结论与文档")
        for row in self.doc["rows"]:
            for radius, verdict in row["blur"].items():
                self.assertFalse(verdict["ok"], (row["delta"], row["block"], radius))
                self.assertGreaterEqual(verdict["ber"], 0.3,
                                        "BER 过低说明模糊链没生效")

    def test_reproducible(self):
        self.assertEqual(probe.render(self.doc), probe.render(probe.build_probe()))


if __name__ == "__main__":
    unittest.main()
