"""投稿日配额与 Gitee 防自动推 main 的安全回归。"""

from __future__ import annotations

import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import intake_quota as iq  # noqa: E402


class QuotaTest(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / "library").mkdir()
        (self.root / "library" / "intake.json").write_text(json.dumps({
            "submission": {"quota": {"per_author_per_day": 2, "global_per_day": 3}}
        }), encoding="utf-8")
        self.old = os.getcwd()
        os.chdir(self.root)
        iq.reset_quota_state()

    def tearDown(self):
        os.chdir(self.old)
        iq.reset_quota_state()
        self.td.cleanup()

    def _entry(self, name, author, generated=None):
        generated = generated or datetime.date.today().isoformat()
        (self.root / "library" / name).write_text(
            f"---\nauthor: {author}\ngenerated: {generated}\n---\n",
            encoding="utf-8",
        )

    def test_per_author_limit_rejects_third_submission(self):
        self._entry("NF-1.md", "alice")
        self._entry("NF-2.md", "alice")
        self.assertIn("2 条上限", iq.quota_denial("ALICE"))
        self.assertEqual("", iq.quota_denial("bob"))

    def test_global_limit_and_in_run_accounting(self):
        self._entry("NF-1.md", "alice")
        self._entry("NF-2.md", "bob")
        self._entry("NF-3.md", "carol")
        self.assertIn("全仓当日", iq.quota_denial("dave"))
        iq.reset_quota_state()
        (self.root / "library" / "NF-3.md").unlink()
        self.assertEqual("", iq.quota_denial("dave"))
        iq.record_quota("dave")
        self.assertIn("全仓当日", iq.quota_denial("erin"))

    def test_old_days_do_not_consume_quota(self):
        old = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        self._entry("NF-1.md", "alice", old)
        self.assertEqual("", iq.quota_denial("alice"))

    def test_invalid_quota_declaration_fails_to_conservative_default(self):
        (self.root / "library" / "intake.json").write_text(
            '{"submission":{"quota":{"per_author_per_day":0,"global_per_day":-1}}}',
            encoding="utf-8",
        )
        self.assertEqual((2, 20), iq.load_quota())


class GiteeWriteBoundaryTest(unittest.TestCase):
    def test_gitee_channel_is_author_only_and_never_auto_pushes_anonymous_input(self):
        doc = json.loads((ROOT / "library" / "intake.json").read_text(encoding="utf-8"))
        gitee = doc["channels"]["gitee"]
        self.assertEqual("author_only", gitee["mode"])
        self.assertIn("monyeah777", gitee["allowlist"])
        self.assertIn(gitee["index_label"],
                      (ROOT / "library" / "INDEX.md").read_text(encoding="utf-8"))

    def test_both_bots_wire_quota_before_write(self):
        for rel in (".github/scripts/gitee_ingest.py", ".github/scripts/library_ingest.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("quota_denial(", text)
            self.assertIn("record_quota(", text)


if __name__ == "__main__":
    unittest.main()
