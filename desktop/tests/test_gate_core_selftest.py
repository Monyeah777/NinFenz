"""A 桶证据内核自检（批 1）：gate_engine / gate_inproc / gate_labels。

不新增 check 号：这些用例由 check12（unittest 矩阵）覆盖，把「最值钱但未入门禁」的模块
接进持续回归。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_engine as ge  # noqa: E402
from core import gate_inproc as gi  # noqa: E402
from core import gate_labels as gl  # noqa: E402


class GateEngineSelfTest(unittest.TestCase):
    def test_registry_nonempty_and_key_unique_per_check(self):
        ge.build_registry()
        self.assertGreater(len(ge.REGISTRY), 10)
        specs = list(ge.REGISTRY.values())[:3]
        keys = {ge.content_key(s, ROOT) for s in specs}
        self.assertEqual(len(specs), len(keys), "不同 check 的 memo 键必须不同")

    def test_unknown_check_is_explicit(self):
        ge.build_registry()
        self.assertNotIn(999, ge.REGISTRY)


class GateInprocSelfTest(unittest.TestCase):
    def test_extract_and_run_heredoc(self):
        text = (ROOT / "verify.sh").read_text(encoding="utf-8")
        got = gi.extract_heredoc(text, 35)
        self.assertIsNotNone(got)
        src, logname = got
        self.assertIn("import", src)
        self.assertTrue(logname.endswith(".log"))
        code, _out = gi.run_inproc("raise SystemExit('boom')\n", ROOT, "nf_selftest")
        self.assertEqual(1, code, "非整数 SystemExit 必须归一为 1，不得崩")


class GateLabelsSelfTest(unittest.TestCase):
    def test_labels_are_structured(self):
        text = (ROOT / "verify.sh").read_text(encoding="utf-8")
        labels = gl.parse_labels(text, 33)
        self.assertTrue(labels.pass_lines, "check33 必须能抽到成功路径文案")
        self.assertTrue(gl.check_body(text, 33))
        self.assertIn("33", gl.banner(text, 33))
