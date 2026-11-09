"""提交前自查（fast lane）判据：名单不得腐烂、红要能红、不新增检查。

依据（第 51 轮）：快照每轮红 3–5 片的根因是「新增模块/命令/解析后没人跑横向门禁」。
`scripts/precheck.py` 只是**按名单跑既有测试**，所以判据只盯两件事：
① 名单里每个模块都真实存在（防改名后静默跳过）；② 它真的会在红时返回非零（不空转）。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "precheck.py"
sys.path.insert(0, str(ROOT / "scripts"))
import precheck as pc  # noqa: E402


class PrecheckTest(unittest.TestCase):
    def test_every_listed_module_exists(self):
        self.assertGreaterEqual(len(pc.GATES), 10, "快车道闸门太少（判据可能失效）")
        for _gate_id, module in list(pc.GATES) + list(pc.SLOW_GATES):
            # 支持「模块」与「模块.类.方法」两种写法：按段回退找到真实文件
            parts = module.split(".")
            found = any((ROOT / "/".join(parts[:i])).with_suffix(".py").is_file()
                        for i in range(len(parts), 0, -1))
            self.assertTrue(found, "名单里的模块不存在：" + module)

    def test_gate_ids_are_unique(self):
        ids = [g for g, _m in list(pc.GATES) + list(pc.SLOW_GATES)]
        self.assertEqual(len(ids), len(set(ids)), f"闸门 id 重复：{ids}")

    def test_script_runs_and_reports_schema(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(ROOT), timeout=1800)
        import json
        doc = json.loads(proc.stdout)
        self.assertEqual("nf-precheck/1", doc["schema"])
        self.assertEqual(len(pc.GATES), doc["gates"])
        self.assertEqual(0 if doc["ok"] else 1, proc.returncode)


if __name__ == "__main__":
    unittest.main()
