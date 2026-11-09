"""DCT 水印探针判据：**把探针结论也锁住**（否则下次调参就会悄悄漂）。

判据分三层：
① 确定性：同一探针两次构建逐字节一致，提交件可复算；
② 两条机制的实测边界：绝对量化 QIM 扛 q≥85 不扛 q≤70；关系嵌入扛 q≥70；
③ 代价与缺口：关系嵌入 PSNR 明显低于 QIM（鲁棒性不是白来的）；两条机制都不扛几何攻击
   （缩放/拍屏）——这说明下一阶段必须加**同步层**，而不是继续调嵌入参数。
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

import watermark_dct_probe as probe  # noqa: E402


def _rows(doc):
    return {item["method"]: {row["id"]: row for row in item["attacks"]}
            for item in doc["methods"]}


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：DCT 探针跳过（不冒充已验）")
class ProbeDeterminismTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        self.assertEqual(probe.render(probe.build_probe()),
                         probe.render(probe.build_probe()))

    def test_committed_results_match_rebuild(self):
        path = ROOT / probe.OUT_REL
        if not path.is_file():
            self.skipTest("探针结果尚未提交（先跑 --write）")
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(probe.render(recorded), probe.render(probe.build_probe()))


@unittest.skipUnless(HAVE_DEPS, "缺 Pillow/numpy：DCT 探针跳过（不冒充已验）")
class MechanismBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = probe.build_probe()
        cls.rows = _rows(cls.doc)

    def test_both_methods_round_trip_clean(self):
        for item in self.doc["methods"]:
            self.assertTrue(item["clean"]["ok"], item["method"])
            self.assertTrue(item["clean"]["payload_exact"], item["method"])

    def test_absolute_qim_boundary(self):
        qim = self.rows["qim"]
        for aid in ("jpeg_95", "jpeg_85", "noise_1"):
            self.assertTrue(qim[aid]["ok"], aid)
        for aid in ("jpeg_70", "jpeg_50"):
            self.assertFalse(qim[aid]["ok"],
                             aid + " 竟然读回——QIM 边界描述与实测不符")

    def test_relationship_embedding_holds_to_q70(self):
        rel = self.rows["rel"]
        for aid in ("jpeg_95", "jpeg_85", "jpeg_70", "jpeg_50", "noise_1"):
            self.assertTrue(rel[aid]["ok"], aid + " 例外")

    def test_relationship_costs_visibility(self):
        psnr = {item["method"]: item["clean"]["psnr_db"] for item in self.doc["methods"]}
        self.assertGreater(psnr["qim"], 40, "QIM 可见性应 >40 dB")
        self.assertLess(psnr["rel"], psnr["qim"] - 3,
                        "关系嵌入应明显更可见（鲁棒性不是白来的）")
        self.assertGreater(psnr["rel"], 30, "关系嵌入不该烂到 30 dB 以下")

    def test_geometry_is_not_solved_by_embedding(self):
        for method, rows in self.rows.items():
            for aid in ("scale_0.9", "screenshot_sim"):
                self.assertFalse(rows[aid]["ok"],
                                 method + " " + aid + " 竟然读回——说明同步层还没做，判据要重述")


if __name__ == "__main__":
    unittest.main()
