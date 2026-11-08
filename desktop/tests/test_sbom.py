"""材料清单判据（SBOM 式）：清单可重算、可核、篡改必红。

依据（第 113 轮，供应链域 `sc.materials_products`）：清单必须与现场一致，
否则「这份交付由哪些输入构成」就还是一句声明。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import sbom as sbom_script  # noqa: E402
from core import sbom as sb  # noqa: E402


class SbomTest(unittest.TestCase):
    def test_collect_is_deterministic(self):
        first = sb.collect(ROOT)
        second = sb.collect(ROOT)
        self.assertEqual("nf-sbom/1", first["schema"])
        self.assertEqual(first, second, "两次收集必须完全一致")
        self.assertGreater(first["count"], 100, "材料太少（范围可能失效）")
        self.assertEqual(first["count"], len(first["materials"]))

    def test_committed_manifest_is_fresh(self):
        """已提交清单必须与重算一致（改了范围/文件而忘刷新即红）。"""
        path = ROOT / sbom_script.OUT_REL
        self.assertTrue(path.is_file(), "缺清单：先跑 scripts/sbom.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([], sb.verify(committed, ROOT), "清单与现场不一致")
        self.assertEqual(sbom_script.render(sb.collect(ROOT)),
                         path.read_text(encoding="utf-8"), "清单已陈旧，重跑 --write")

    def test_verify_catches_tampering(self):
        """变异测试：改摘要 / 删条目 / 改 count 三种篡改都必须报。"""
        manifest = sb.collect(ROOT)
        self.assertEqual([], sb.verify(manifest, ROOT))
        bad_hash = json.loads(json.dumps(manifest))
        bad_hash["materials"][0]["sha256"] = "0" * 64
        self.assertTrue(sb.verify(bad_hash, ROOT), "改条目摘要必须报")
        missing = json.loads(json.dumps(manifest))
        missing["materials"][0]["path"] = "does/not/exist_xyz.py"
        self.assertTrue(sb.verify(missing, ROOT), "材料不在场必须报")
        bad_count = json.loads(json.dumps(manifest))
        bad_count["count"] = int(manifest["count"]) + 1
        self.assertTrue(sb.verify(bad_count, ROOT), "count 篡改必须报")

    def test_empty_root_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError) as ctx:
            sb.collect(tmp)
        self.assertIn("修复指引", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
