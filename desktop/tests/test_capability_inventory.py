"""能力清单判据：静态接口面可复算、可查、改了就红（第 139 轮）。

为什么需要：第 136/138 轮我两次断言「某工具没有某能力」都判错。根因是**凭记忆判断能力面**。
本判据保证 `results/ccos/capability_inventory.json` 与 `scripts/*.py` 的接口面一致，
让「这个脚本有哪些旗标/子命令」可以查而不是猜。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))
import capability_inventory as ci  # noqa: E402


class CapabilityInventoryTest(unittest.TestCase):
    def test_collect_is_deterministic_and_covers_all_scripts(self):
        first = ci.collect(ROOT)
        second = ci.collect(ROOT)
        self.assertEqual("nf-capability-inventory/1", first["schema"])
        self.assertEqual(first, second, "两次扫描必须一致")
        scripts = len(list((ROOT / "scripts").glob("*.py")))
        self.assertEqual(scripts, first["scripts"], "漏扫脚本")
        self.assertGreater(first["flags"], 300, "旗标太少（抽取可能失效）")

    def test_committed_inventory_is_fresh(self):
        path = ROOT / ci.OUT_REL
        self.assertTrue(path.is_file(), "缺清单：先跑 scripts/capability_inventory.py --write")
        committed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(ci.render(ci.collect(ROOT)), ci.render(committed),
                         "能力清单已陈旧，重跑 --write")

    def test_inventory_lists_known_flags(self):
        """抽样核对：sbom.py 的 --check、perf_budget.py 的 --record 必须在清单里。"""
        doc = json.loads((ROOT / ci.OUT_REL).read_text(encoding="utf-8"))
        by_path = {e["path"]: e for e in doc["entries"]}
        self.assertIn("--check", by_path["scripts/sbom.py"]["flags"])
        self.assertIn("--record", by_path["scripts/perf_budget.py"]["flags"])

    def test_scan_is_static(self):
        """变异自证：扫描函数只读源码文本，不执行——用一段带副作用的源码证明。"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.py"
            marker = Path(tmp) / "landed.txt"
            path.write_text('"""假脚本"""\nimport argparse\n'
                            'ap = argparse.ArgumentParser()\n'
                            'ap.add_argument("--x")\n'
                            f'open(r"{marker}", "w").write("ran")\n', encoding="utf-8")
            row = ci._scan_source(path)
            self.assertEqual(["--x"], row["flags"])
            self.assertEqual("假脚本", row["doc"])
            self.assertFalse(marker.exists(), "扫描执行了源码（应有副作用）")


if __name__ == "__main__":
    unittest.main()
