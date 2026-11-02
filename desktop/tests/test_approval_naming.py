#!/usr/bin/env python3
"""批准记录命名（审计 W7：protocol/approvals/*.json.json 双扩展名）。"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import approval  # noqa: E402


class ApprovalNamingTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"NF_APPROVERS": "tester"})
    def test_subject_cannot_escape_repository_root(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "repo"
            root.mkdir()
            secret = Path(parent) / "secret.md"
            secret.write_text("do not touch", encoding="utf-8")
            with self.assertRaises(ValueError):
                approval.approve(str(root), "../secret.md", "tester")
            self.assertFalse((root / "protocol" / "approvals").exists())

    @mock.patch.dict(os.environ, {"NF_APPROVERS": "tester"})
    def test_json_subject_gets_single_extension(self):
        """主体以 .json 结尾时，记录名只带一个 .json（此前拼成 xxx.json.json）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "protocol").mkdir()
            (root / "protocol" / "conformance_report.json").write_text("{}", encoding="utf-8")
            rel = approval.approve(str(root), "protocol/conformance_report.json", "tester")
        self.assertEqual("protocol/approvals/protocol__conformance_report.json", rel)
        self.assertFalse(rel.endswith(".json.json"), "又拼出双扩展名")

    @mock.patch.dict(os.environ, {"NF_APPROVERS": "tester"})
    def test_non_json_subject_keeps_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc.md").write_text("x", encoding="utf-8")
            rel = approval.approve(str(root), "doc.md", "tester")
        self.assertEqual("protocol/approvals/doc.md.json", rel)

    def test_empty_approvers_env_fails_closed(self):
        """E13：`NF_APPROVERS=""` 曾被当成「不限制」→ 任意人可批准。现须拒绝。"""
        import os
        old = os.environ.get("NF_APPROVERS")
        os.environ["NF_APPROVERS"] = ""
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "doc.md").write_text("x", encoding="utf-8")
                with self.assertRaises(ValueError):
                    approval.approve(str(root), "doc.md", "attacker")
        finally:
            if old is None:
                os.environ.pop("NF_APPROVERS", None)
            else:
                os.environ["NF_APPROVERS"] = old

    def test_repo_has_no_double_extension_approvals(self):
        d = ROOT / approval.DIR_REL
        if not d.is_dir():
            self.skipTest("无 protocol/approvals 目录")
        bad = [p.name for p in d.glob("*.json.json")]
        self.assertEqual([], bad, "批准记录仍有双扩展名：%s" % bad)


if __name__ == "__main__":
    unittest.main()
