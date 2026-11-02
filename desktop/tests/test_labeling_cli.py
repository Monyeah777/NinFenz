"""nf labeling 子命令的 subprocess 回归（走 scripts/nf.py 真 CLI）。

作者：impl（DSH agent）· 2026-11-02
运行：cd <repo> && python3 -m unittest desktop.tests.test_labeling_cli -v

只测「NF 侧接线」：`nf labeling <子命令>` 能跑到 core.labeling.cli、退出码与
关键输出正确；判定逻辑本身由 test_labeling_core 与原型测试覆盖。
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, sm  # noqa: E402

NF = str(ROOT / "scripts" / "nf.py")
PY = sys.executable


def run_nf(*args, timeout=300):
    """跑 `python3 scripts/nf.py ...`，返回 CompletedProcess。"""
    return subprocess.run(
        [PY, NF, *args], cwd=str(ROOT), capture_output=True,
        text=True, timeout=timeout)


class LabelingCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.png = str(self.dir / "a.png")
        metadata.make_png(self.png)
        self.keys = sm.sm2_keygen()
        self.meta_path = str(self.dir / "meta.json")
        Path(self.meta_path).write_text(
            json.dumps({"Label": 1, "ContentProducer": "1" * 27,
                        "ProduceID": "AI-CLI-1"}, ensure_ascii=False),
            encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _sign(self):
        r = run_nf("labeling", "sign", self.png, "--meta", self.meta_path,
                   "--priv", self.keys["private"], "--png-text")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_help_lists_six_subcommands(self):
        r = run_nf("labeling", "--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("check", "sign", "verify", "keygen", "selfcheck"):
            self.assertIn(name, r.stdout)

    def test_selfcheck(self):
        r = run_nf("labeling", "selfcheck")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("自检结果：PASS", r.stdout)

    def test_info(self):
        r = run_nf("labeling", "info")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("GB 45438", r.stdout)

    def test_keygen_writes_json(self):
        out = str(self.dir / "keys.json")
        r = run_nf("labeling", "keygen", "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        self.assertEqual(len(data["private"]), 64)
        self.assertEqual(len(data["public"]), 128)

    def test_sign_then_verify(self):
        self._sign()
        r = run_nf("labeling", "verify", self.png)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_sign_then_check_json(self):
        self._sign()
        r = run_nf("labeling", "check", self.png, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report["container"], "png")
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue({"A", "B", "C", "D", "E"} <= set(
            report["sections"]))

    def test_check_text_without_metadata_fails(self):
        txt = self.dir / "a.txt"
        txt.write_text("标题\n本内容由 AI 生成。\n", encoding="utf-8")
        r = run_nf("labeling", "check", str(txt))
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stdout)

    def test_check_missing_file_rc2(self):
        r = run_nf("labeling", "check", str(self.dir / "nope.png"))
        self.assertEqual(r.returncode, 2)

    def test_verify_wrong_pub_fails(self):
        self._sign()
        other = sm.sm2_keygen()["public"]
        r = run_nf("labeling", "verify", self.png, "--pub", other)
        self.assertEqual(r.returncode, 1)

    def test_unknown_subcommand_rc2(self):
        r = run_nf("labeling", "no-such-cmd")
        self.assertEqual(r.returncode, 2)

    def test_no_args_rc2(self):
        r = run_nf("labeling")
        self.assertEqual(r.returncode, 2)

    def test_thin_launcher_selfcheck(self):
        launcher = str(ROOT / "scripts" / "nf_labeling.py")
        r = subprocess.run([PY, launcher, "selfcheck"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("自检结果：PASS", r.stdout)


if __name__ == "__main__":
    unittest.main()
