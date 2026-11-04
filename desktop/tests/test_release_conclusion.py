"""发布结论复跑器（scripts/release_conclusion.py）单测——纯函数判据 + dry-run 集成。

与 nf release（发布编排：冻结链次序）分工不同：本件判「冻结后能不能发布」。真正的分片执行要
10+ 分钟，不适合常驻单测；但**闸门逻辑**（脏树拒绝、分片汇总、计划生成）是这套东西的判据
所在，必须常驻可验——尤其脏树闸门：我自己踩过「在改到一半的树上跑分片拿到一堆假红」。
"""
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "release_conclusion.py"


def _load():
    spec = importlib.util.spec_from_file_location("nf_release_conclusion", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPureLogic(unittest.TestCase):
    def setUp(self):
        self.gate = _load()

    def test_porcelain_lines_ignores_blanks(self):
        self.assertEqual([], self.gate.porcelain_lines(""))
        self.assertEqual([], self.gate.porcelain_lines("\n  \n"))
        self.assertEqual([" M a.py", "?? b.txt"],
                         self.gate.porcelain_lines(" M a.py\n\n?? b.txt\n"))

    def test_dirty_guard_allows_clean(self):
        self.assertEqual("", self.gate.dirty_guard([], False))

    def test_dirty_guard_refuses_dirty(self):
        msg = self.gate.dirty_guard([" M a.py"], False)
        self.assertIn("工作树不干净", msg)
        self.assertIn("修复指引", msg)
        self.assertIn("--allow-dirty", msg)

    def test_dirty_guard_allow_flag(self):
        self.assertEqual("", self.gate.dirty_guard([" M a.py"], True))

    def test_aggregate_all_pass(self):
        res = self.gate.aggregate([{"shard": "0/2", "rc": 0, "wall": 10.0},
                                   {"shard": "1/2", "rc": 0, "wall": 12.5}])
        self.assertTrue(res["ok"])
        self.assertEqual(res["total"], 2)
        self.assertEqual(res["failed"], [])
        self.assertEqual(res["wall"], 22.5)

    def test_aggregate_one_fail(self):
        res = self.gate.aggregate([{"shard": "0/2", "rc": 0},
                                   {"shard": "1/2", "rc": 1}])
        self.assertFalse(res["ok"])
        self.assertEqual(res["failed"], [{"shard": "1/2", "rc": 1}])

    def test_aggregate_empty_is_not_ok(self):
        self.assertFalse(self.gate.aggregate([])["ok"])


class TestDryRun(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--dry-run", *args],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_dry_run_prints_plan(self):
        proc = self._run("--shards", "2")
        self.assertIn(proc.returncode, (0, 2))
        doc = json.loads(proc.stdout)
        self.assertTrue(doc["dry_run"])
        self.assertEqual(doc["plan"]["shards"], 2)
        self.assertEqual(doc["plan"]["concurrency"], 1, "缺省并发必须是 1（单机并发有争用）")
        steps = doc["plan"]["steps"]
        self.assertEqual(steps[0], "git status --porcelain")
        joined = " ".join(steps)
        self.assertIn("--shard 0/2", joined)
        self.assertIn("--shard 1/2", joined)

    def test_jobs_sets_concurrency_not_partitions(self):
        """分区与并发是两件事：--jobs 只改同时跑几片，不改切片数（判据面不变）。"""
        proc = self._run("--shards", "4", "--jobs", "2")
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["plan"]["shards"], 4)
        self.assertEqual(doc["plan"]["concurrency"], 2)

    def test_default_is_eight_partitions_serial(self):
        proc = self._run()
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["plan"]["shards"], 8, "单片跑全量会暴露套件级顺序敏感性")
        self.assertEqual(doc["plan"]["concurrency"], 1)

    def test_dry_run_allow_dirty_reports_no_block(self):
        proc = self._run("--jobs", "1", "--allow-dirty")
        self.assertEqual(0, proc.returncode)
        self.assertEqual("", json.loads(proc.stdout)["blocked"])


class TestDirtyRefusal(unittest.TestCase):
    def test_refuses_when_repo_dirty(self):
        """真仓若脏，非 dry-run 必须 rc=2 且一行测试都不跑（拒绝在中间态上出结论）。"""
        gate = _load()
        if not gate._git_status():
            self.skipTest("工作树干净，无法复现脏树分支（纯函数判据已覆盖）")
        proc = subprocess.run([sys.executable, str(SCRIPT), "--jobs", "1"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        self.assertEqual(2, proc.returncode)
        self.assertIn("工作树不干净", proc.stderr)


if __name__ == "__main__":
    unittest.main()
