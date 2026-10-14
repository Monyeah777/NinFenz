#!/usr/bin/env python3
"""`nf audit rebind` 单测：机械重绑 + 理由落档 + 幂等 + 拒空理由（check 的 check）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import audit as au  # noqa: E402


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scene(root: Path, subject_sha: str, body: str = "正文\n") -> Path:
    (root / "target.txt").write_text("x\n", encoding="utf-8", newline="\n")
    d = root / "results" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "a1.md"
    p.write_text("---\nid: AUD-9001\ndate: 2026-01-01\nscope: 测试\nverdict: pass\n"
                 "auditor: t\nsubjects:\n  - target.txt:%s\n---\n%s" % (subject_sha, body),
                 encoding="utf-8", newline="\n")
    return p


class RebindTest(unittest.TestCase):
    def test_drift_is_rebound_and_note_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _scene(r, "0" * 64)
            issues, st = au.rebind(str(r), note="被审对象随本波改动")
            self.assertEqual([], issues, issues)
            self.assertEqual(1, st["rechained"])
            self.assertEqual(1, st["subjects"])
            text = p.read_text(encoding="utf-8")
            self.assertIn("target.txt:%s" % _sha("x\n"), text)
            self.assertIn("> 重审（", text)
            self.assertIn("被审对象随本波改动", text)
            self.assertNotIn("0" * 64, text)

    def test_same_note_is_not_appended_twice(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            _scene(r, "0" * 64)
            au.rebind(str(r), note="同一理由")
            first = (r / "results/audit/a1.md").read_text(encoding="utf-8")
            (r / "target.txt").write_text("y\n", encoding="utf-8", newline="\n")
            issues, st = au.rebind(str(r), note="同一理由")
            self.assertEqual([], issues, issues)
            self.assertEqual(1, st["rechained"])
            second = (r / "results/audit/a1.md").read_text(encoding="utf-8")
            self.assertEqual(1, second.count("同一理由"), "同一理由不许追加两次")
            self.assertNotEqual(first, second)

    def test_no_drift_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            _scene(r, _sha("x\n"))
            issues, st = au.rebind(str(r), note="对象没变")
            self.assertEqual([], issues, issues)
            self.assertEqual(0, st["rechained"])
            self.assertNotIn("> 重审（", (r / "results/audit/a1.md").read_text(encoding="utf-8"))

    def test_empty_note_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _scene(r, "0" * 64)
            issues, st = au.rebind(str(r), note="   ")
            self.assertEqual(1, len(issues), issues)
            self.assertIn("理由为空", issues[0])
            self.assertIn("0" * 64, p.read_text(encoding="utf-8"))   # 拒绝即不写盘

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            p = _scene(r, "0" * 64)
            before = p.read_text(encoding="utf-8")
            issues, st = au.rebind(str(r), note="只看不写", dry_run=True)
            self.assertEqual([], issues, issues)
            self.assertEqual(1, st["rechained"])
            self.assertEqual(before, p.read_text(encoding="utf-8"))

    def test_legacy_record_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            d1 = r / "results" / "audit"
            d1.mkdir(parents=True, exist_ok=True)
            (d1 / "old.md").write_text("没有审计头的存量件\n", encoding="utf-8", newline="\n")
            issues, st = au.rebind(str(r), note="存量件不重绑")
            self.assertEqual([], issues, issues)
            self.assertEqual(0, st["rechained"])
            self.assertEqual(1, st["skipped"])


if __name__ == "__main__":
    unittest.main()
