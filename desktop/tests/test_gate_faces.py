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
                '{"id": "e1", "reads": %s, "skip_safety": "SAFE"}]}'
                % declared_reads, encoding="utf-8")
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


class ManifestSchemaTest(unittest.TestCase):
    """W-03.3 声明面契约：形状违例如实报，合规不误报（fail-closed）。"""

    def test_valid(self):
        doc = {"schema": "nf-gate-experts/1",
               "experts": [{"id": "e1", "reads": ["docs"], "skip_safety": "UNSAFE"}]}
        self.assertEqual([], gf.validate_manifest(doc))

    def test_wrong_schema(self):
        issues = gf.validate_manifest({"schema": "x", "experts": []})
        self.assertTrue(any("schema" in i for i in issues), issues)

    def test_missing_reads_and_bad_level(self):
        issues = gf.validate_manifest(
            {"schema": "nf-gate-experts/1", "experts": [{"id": "e1"}]})
        self.assertTrue(any("reads" in i for i in issues), issues)
        self.assertTrue(any("skip_safety" in i for i in issues), issues)

    def test_empty_is_violation(self):
        self.assertTrue(gf.validate_manifest({}))


class SkipSafetyTest(unittest.TestCase):
    """W-04：效应面 → skip_safety 推导（变异自证：四类非确定面各自判 UNSAFE）。"""

    def test_unsafe_markers(self):
        cases = [("import subprocess", "proc"), ("import socket", "net"),
                 ("import os\nX = os.environ['A']", "env"),
                 ("import time\ntime.time()", "time")]
        for snippet, kind in cases:
            level, why = gf.classify_source(snippet)
            self.assertEqual("UNSAFE", level, (snippet, why))
            self.assertTrue(any(w.startswith(kind + ":") for w in why), (snippet, why))

    def test_conditional_on_fs_probe(self):
        level, why = gf.classify_source("import os\nos.path.exists('x')")
        self.assertEqual("CONDITIONAL", level, why)

    def test_safe_plain(self):
        level, why = gf.classify_source("X = 1\n")
        self.assertEqual("SAFE", level, why)

    def test_derive_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "protocol").mkdir(parents=True, exist_ok=True)
            (Path(tmp) / "m.py").write_text("import socket\n", encoding="utf-8")
            (Path(tmp) / "protocol" / "gate_experts.json").write_text(
                '{"schema": "nf-gate-experts/1", "experts": ['
                '{"id": "e1", "reads": [], "skip_safety": "SAFE", "module": "m.py"}]}',
                encoding="utf-8")
            issues, stats = gf.audit(tmp)
            self.assertTrue(any("声明级别与推导不符" in i for i in issues), issues)
            self.assertEqual("UNSAFE", stats["facts"]["e1"]["derived_skip_safety"])

    def test_no_source_does_not_guess(self):
        level, why = gf.derive_skip_safety(".", {"id": "no-such-module"})
        self.assertIsNone(level)
        self.assertTrue(why)


class CompressFaceTest(unittest.TestCase):
    """M2：声明面由观测面生成（压缩成 glob，宁可过覆盖不可漏）。"""

    def test_compress_groups_by_prefix_and_ext(self):
        got = gf.compress_face(["scripts/a.py", "scripts/b.py", "docs/x.md"])
        self.assertIn("scripts/**/*.py", got)
        self.assertIn("docs/**/*.md", got)

    def test_derive_reads_covers_every_observed_path(self):
        observed = ["scripts/a.py", "scripts/b.py", "protocol/x.json"]
        reads = gf.derive_reads(".", observed)
        for rel in observed:
            self.assertTrue(gf.covered(rel, reads), (rel, reads))


if __name__ == "__main__":
    unittest.main()
