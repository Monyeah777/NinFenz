"""生成物新鲜度前置检查（scripts/freshness_check.py）判据。

为什么要有它：这条判据的价值是「把过期在秒级暴露」，而不是等 25 分钟的分片。
所以判据本身就是它自己：干净树上必须全过；聚合口径必须能把任何一项过期变成 rc=1。
"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "freshness_check.py"


def _mod():
    spec = importlib.util.spec_from_file_location("nf_freshness", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAggregate(unittest.TestCase):
    def setUp(self):
        self.m = _mod()

    def test_all_clean(self):
        rows = [{"id": "a", "desc": "x", "fix": "f", "issues": []}]
        res = self.m.aggregate(rows)
        self.assertTrue(res["ok"])
        self.assertEqual(1, res["checked"])
        self.assertEqual([], res["issues"])

    def test_one_stale_fails(self):
        rows = [{"id": "a", "desc": "x", "fix": "f", "issues": []},
                {"id": "b", "desc": "y", "fix": "nf layers --write", "issues": ["过期"]}]
        res = self.m.aggregate(rows)
        self.assertFalse(res["ok"])
        self.assertEqual("b", res["issues"][0]["id"])
        self.assertEqual("nf layers --write", res["issues"][0]["fix"])

    def test_issue_list_is_capped(self):
        rows = [{"id": "a", "desc": "x", "fix": "f", "issues": [str(i) for i in range(20)]}]
        self.assertEqual(6, len(self.m.aggregate(rows)["issues"][0]["issues"]))


class TestWiring(unittest.TestCase):
    def test_every_check_has_a_runner_and_fix(self):
        m = _mod()
        ids = [row[0] for row in m.CHECKS]
        self.assertEqual(sorted(ids), sorted(m.RUNNERS))
        for _cid, desc, fix in m.CHECKS:
            self.assertTrue(desc)
            self.assertTrue(fix, "每项必须给出修复命令")

    def test_only_filter(self):
        m = _mod()
        rows = m.collect(str(ROOT), only=("role_coordinates",))
        self.assertEqual(1, len(rows))
        self.assertEqual("role_coordinates", rows[0]["id"])


class TestCli(unittest.TestCase):
    def test_clean_tree_passes(self):
        """干净树上四项全过（过期时该红——这正是它的判据）。"""
        proc = subprocess.run([sys.executable, str(SCRIPT), "--json"], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        self.assertEqual(0, proc.returncode, proc.stdout[-600:] + proc.stderr[-400:])
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["ok"])
        self.assertEqual(4, doc["checked"])

    def test_only_mode_is_cheap_and_parseable(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--only", "role_coordinates",
                               "--json"], cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertIn(proc.returncode, (0, 1))
        self.assertEqual(1, json.loads(proc.stdout)["checked"])


if __name__ == "__main__":
    unittest.main()
