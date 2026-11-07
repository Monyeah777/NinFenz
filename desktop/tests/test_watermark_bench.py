"""水印鲁棒性基准判据：边界必须**实测**，不是形容词。

判据四类：
① 确定性：同一基准两次构建逐字节一致（否则数字不可复算）；
② 承诺面：无损重存与裁剪必须仍能逐字节读回（当前实现确实做得到）；
③ 边界面：有损变换（JPEG/缩放/噪声/拍屏）必须**记录为读不回**——写成断言，
   防止以后有人「顺手放宽」又把它说成抗得住；
④ 覆盖面：攻击条数 ≥12 且 id 唯一（防判据面被悄悄缩小）。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from PIL import Image  # noqa: F401
    HAVE_PIL = True
except ImportError:                                     # pragma: no cover
    HAVE_PIL = False

import watermark_bench as wb  # noqa: E402


@unittest.skipUnless(HAVE_PIL, "环境无 Pillow：水印基准跳过（不冒充已验）")
class BenchDeterminismTest(unittest.TestCase):
    def test_build_is_deterministic(self):
        a = wb.build_bench()
        b = wb.build_bench()
        self.assertEqual(wb.render(a), wb.render(b))

    def test_committed_results_match_rebuild(self):
        path = ROOT / wb.OUT_REL
        if not path.is_file():
            self.skipTest("基准结果尚未提交（先跑 --write）")
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(wb.render(recorded), wb.render(wb.build_bench()))


@unittest.skipUnless(HAVE_PIL, "环境无 Pillow：水印基准跳过（不冒充已验）")
class BenchCoverageTest(unittest.TestCase):
    def test_attack_matrix_is_wide_enough(self):
        doc = wb.build_bench()
        ids = [row["id"] for row in doc["attacks"]]
        self.assertGreaterEqual(len(ids), 12, "攻击矩阵过窄（判据面被缩小）")
        self.assertEqual(len(ids), len(set(ids)), "攻击 id 必须唯一")

    def test_every_attack_has_both_verdict_fields(self):
        doc = wb.build_bench()
        for row in doc["attacks"]:
            self.assertIn("ok", row)
            self.assertIn("ber", row)
            self.assertIn("payload_exact", row)

    def test_markdown_table_has_all_rows(self):
        doc = wb.build_bench()
        table = wb.table_md(doc)
        self.assertIn("攻击", table)
        for row in doc["attacks"]:
            self.assertIn(row["desc"], table)


@unittest.skipUnless(HAVE_PIL, "环境无 Pillow：水印基准跳过（不冒充已验）")
class PromiseAndBoundaryTest(unittest.TestCase):
    """把「承诺」与「边界」都写成断言：承诺成立、边界存在，两头都不能漂。"""

    @classmethod
    def setUpClass(cls):
        cls.doc = wb.build_bench()
        cls.rows = {row["id"]: row for row in cls.doc["attacks"]}

    def test_baseline_clean_embed_round_trips(self):
        self.assertTrue(self.doc["baseline"]["ok"])
        self.assertEqual(0.0, self.doc["baseline"]["ber"])

    def test_promise_lossless_and_crop(self):
        for aid in ("lossless_resave", "crop_10", "crop_25", "crop_50"):
            row = self.rows[aid]
            self.assertTrue(row["ok"], aid)
            self.assertTrue(row["payload_exact"], aid)
            self.assertEqual(0.0, row["ber"], aid)

    def test_boundary_jpeg_is_not_survived(self):
        for aid in ("jpeg_95", "jpeg_85", "jpeg_70", "jpeg_50"):
            self.assertFalse(self.rows[aid]["ok"], aid + " 竟然读回了——边界描述与实测不符")

    def test_boundary_scale_and_screenshot_are_not_survived(self):
        for aid in ("scale_0.5", "scale_0.75", "scale_1.5", "scale_2", "screenshot_sim"):
            self.assertFalse(self.rows[aid]["ok"], aid + " 竟然读回了")

    def test_boundary_tiny_noise_and_brightness_have_no_margin(self):
        """比文档更严的实测结论：LSB 连 σ=1 噪声、×1.05 亮度都扛不住（零余量）。"""
        for aid in ("noise_1", "noise_3", "bright_1.05"):
            self.assertFalse(self.rows[aid]["ok"], aid + " 竟然读回了——说明余量结论失效")


if __name__ == "__main__":
    unittest.main()
