# -*- coding: utf-8 -*-
"""core.gate_faces 回归：静态面 / 读面归一 / 三源对账 + 变异自证。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_faces as gf  # noqa: E402


class StaticFaceTest(unittest.TestCase):
    def test_extracts_imports_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "m.py"
            p.write_text("import os\nfrom core import schema_lint\n"
                         "X = 'protocol/LAYERS.json'\nY = '03_管线库/**/*.md'\n"
                         "Z = 'http://x/y'\n", encoding="utf-8")
            got = gf.static_face(str(p))
            self.assertIn("os", got["imports"])
            self.assertIn("core.schema_lint", got["imports"])
            self.assertIn("protocol/LAYERS.json", got["paths"])
            self.assertIn("03_管线库/**/*.md", got["paths"])
            self.assertNotIn("http://x/y", got["paths"])


class CoveredTest(unittest.TestCase):
    def test_prefix_and_glob(self):
        self.assertTrue(gf.covered("desktop/src/core/a.py", ["desktop/src/core"]))
        self.assertTrue(gf.covered("desktop/src/core/a.py", ["desktop/src/**/*.py"]))
        self.assertFalse(gf.covered("scripts/nf.py", ["desktop/src/core"]))


class RelFaceTest(unittest.TestCase):
    def test_memo_key_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            inner = Path(tmp) / "a" / "b.md"
            inner.parent.mkdir(parents=True, exist_ok=True)
            inner.write_text("x", encoding="utf-8")
            got = gf.rel_face(tmp, ["b:" + str(inner), "t:" + str(inner),
                                    str(Path(tmp).parent / "outside.md")])
            self.assertEqual(["a/b.md"], got)


class ReconcileTest(unittest.TestCase):
    """变异自证：三条对账规则各抓一例；干净集不误报。"""

    def _audit(self, declared_reads, static=None, observed=None):
        with tempfile.TemporaryDirectory() as tmp:
            man = Path(tmp) / "protocol"
            man.mkdir(parents=True, exist_ok=True)
            (man / "gate_experts.json").write_text(
                '{"schema": "nf-gate-experts/1", "experts": ['
                '{"id": "e1", "reads": %s}]}' % declared_reads, encoding="utf-8")
            return gf.audit(str(tmp), observed=observed, static=static)

    def test_clean(self):
        issues, stats = self._audit('["docs"]', static={"e1": ["docs/a.md"]},
                                    observed={"e1": ["docs/a.md"]})
        self.assertEqual([], issues)
        self.assertEqual(1, stats["experts"])

    def test_static_not_declared(self):
        issues, _ = self._audit('["docs"]', static={"e1": ["protocol/LAYERS.json"]})
        self.assertTrue(any("静态面未声明" in i for i in issues), issues)

    def test_observed_not_declared(self):
        issues, _ = self._audit('["docs"]', observed={"e1": ["scripts/nf.py"]})
        self.assertTrue(any("观测面未声明" in i for i in issues), issues)

    def test_declared_not_observed(self):
        issues, _ = self._audit('["docs/x.md"]', observed={"e1": ["docs/a.md"]})
        self.assertTrue(any("声明未观测到" in i for i in issues), issues)

    def test_missing_manifest_is_warn_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, stats = gf.audit(tmp)
            self.assertEqual([], issues)
            self.assertTrue(stats["warns"], stats)


if __name__ == "__main__":
    unittest.main()
