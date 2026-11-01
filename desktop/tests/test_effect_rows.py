# -*- coding: utf-8 -*-
"""core.effect_rows 回归：效应行识别 / 级别合并 / 规则层差分一致 / fail-closed。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import effect_rows as er  # noqa: E402

CORE = ROOT / "desktop" / "src" / "core"


class RowsTest(unittest.TestCase):
    def test_kinds_detected_with_lines(self):
        src = "import socket\nimport subprocess\nimport os\nX = os.environ['A']\n"
        got = er.rows(src)
        kinds = {r["kind"] for r in got}
        self.assertEqual({"net", "proc", "env"}, kinds, got)
        self.assertTrue(all(r["line"] >= 1 for r in got), got)

    def test_method_face_is_fs_probe(self):
        got = er.rows("from pathlib import Path\np = Path('x')\np.exists()\n")
        self.assertIn("fs_probe", {r["kind"] for r in got}, got)

    def test_level_takes_strictest(self):
        self.assertEqual("SAFE", er.level(er.rows("X = 1\n")))
        self.assertEqual("CONDITIONAL", er.level(er.rows("import os\nos.path.exists('x')\n")))
        self.assertEqual("UNSAFE", er.level(er.rows("import os\nos.path.exists('x')\nimport socket\n")))

    def test_unparseable_is_fail_closed(self):
        self.assertEqual("UNSAFE", er.level(er.rows("def (: \n")))

    def test_deterministic(self):
        src = "import socket\nimport time\n"
        self.assertEqual(er.rows(src), er.rows(src))


class DifferentialTest(unittest.TestCase):
    """差分自证（P-A3 雏形）：直算与规则层实现**必须同结果**（全 core 语料）。"""

    def test_two_implementations_agree_on_core_corpus(self):
        files = sorted(CORE.glob("*.py"))
        self.assertGreater(len(files), 100, "语料太小，判据可能失效")
        diff = []
        for p in files:
            src = p.read_text(encoding="utf-8")
            a, b = er.level(er.rows(src)), er.level_via_rules(src)
            if a != b:
                diff.append((p.name, a, b))
        self.assertEqual([], diff, "两实现分歧：%s" % diff[:5])


if __name__ == "__main__":
    unittest.main()
