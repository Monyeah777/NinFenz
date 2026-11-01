# -*- coding: utf-8 -*-
"""core.gate_cache 回归：内容键稳定、verify 抓缺件/变更、memo 命中与失效。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_cache as gc  # noqa: E402


class KeyTest(unittest.TestCase):
    def test_same_inputs_same_key_and_root_isolated(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for tmp in (a, b):
                (Path(tmp) / "x.md").write_text("hello", encoding="utf-8")
            k1 = gc.key_for(a, "e1", ["x.md"], code_files=())
            k2 = gc.key_for(a, "e1", ["x.md"], code_files=())
            k3 = gc.key_for(b, "e1", ["x.md"], code_files=())
            self.assertEqual(k1, k2)
            self.assertNotEqual(k1, k3, "不同根不得共用键（防串味）")

    def test_content_change_changes_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("v1", encoding="utf-8")
            k1 = gc.key_for(tmp, "e1", ["x.md"], code_files=())
            p.write_text("v2", encoding="utf-8")
            k2 = gc.key_for(tmp, "e1", ["x.md"], code_files=())
            self.assertNotEqual(k1, k2)


class VerifyTest(unittest.TestCase):
    def test_missing_input_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = {"reads": {"gone.md": "abc"}, "code": {}}
            ok, why = gc.verify(tmp, entry)
            self.assertFalse(ok)
            self.assertTrue(any("缺席" in w for w in why), why)

    def test_changed_input_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("v1", encoding="utf-8")
            entry = {"reads": {"x.md": gc.file_digest(p)}, "code": {}}
            ok, _why = gc.verify(tmp, entry)
            self.assertTrue(ok)
            p.write_text("v2", encoding="utf-8")
            ok2, why2 = gc.verify(tmp, entry)
            self.assertFalse(ok2)
            self.assertTrue(any("已变" in w for w in why2), why2)


class MemoTest(unittest.TestCase):
    def setUp(self):
        gc.clear()

    def test_miss_then_hit_and_missing_input_forces_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "x.md").write_text("v1", encoding="utf-8")
            calls = []

            def impl():
                calls.append(1)
                return {"n": len(calls)}

            ckey = gc.key_for(tmp, "e1", ["x.md"], code_files=())
            v1, hit1 = gc.memo("t", ckey, impl, root=tmp, reads=["x.md"], code_files=())
            v2, hit2 = gc.memo("t", ckey, impl, root=tmp, reads=["x.md"], code_files=())
            self.assertFalse(hit1)
            self.assertTrue(hit2)
            self.assertEqual(v1, v2)

            (Path(tmp) / "x.md").unlink()          # Tup：缺失即失效
            v3, hit3 = gc.memo("t", ckey, impl, root=tmp, reads=["x.md"], code_files=())
            self.assertFalse(hit3, "输入缺席后仍命中＝stale")
            self.assertNotEqual(v3, v1)


if __name__ == "__main__":
    unittest.main()
