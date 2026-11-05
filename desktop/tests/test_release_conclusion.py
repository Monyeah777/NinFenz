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


class TestPayloadGuard(unittest.TestCase):
    """npm payload 与 HEAD 的耦合闸门（前置判据：不通过就不该跑 30 分钟）。"""

    def setUp(self):
        self.gate = _load()

    def test_no_manifest_is_not_blocking(self):
        self.assertEqual("", self.gate.payload_drift_guard(None, "abc123"))

    def test_matching_commit_passes(self):
        self.assertEqual("", self.gate.payload_drift_guard(
            {"source_commit": "abc123def456"}, "abc123def4567890"))

    def test_mismatch_blocks_with_fix_command(self):
        msg = self.gate.payload_drift_guard({"source_commit": "deadbeefdead"},
                                            "cafebabecafe0000")
        self.assertIn("npm payload 与 HEAD 不一致", msg)
        self.assertIn("stage-payload.mjs", msg)

    def test_missing_commit_field_passes(self):
        self.assertEqual("", self.gate.payload_drift_guard({}, "abc123"))

    def test_bad_manifest_is_treated_as_absent(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payload-manifest.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertIsNone(self.gate.read_payload_manifest(p))
            p.write_text("[1,2]", encoding="utf-8")
            self.assertIsNone(self.gate.read_payload_manifest(p))
            p.write_text('{"source_commit": "abc"}', encoding="utf-8")
            self.assertEqual("abc", self.gate.read_payload_manifest(p)["source_commit"])


class TestSupplyChain(unittest.TestCase):
    """供应链核对进 gate（G5）：数字来源不一致就不该产出「可发布」。"""

    def setUp(self):
        self.gate = _load()

    def test_all_clean_no_issues(self):
        rows = [{"id": "site_numbers", "rc": 0}, {"id": "llms_projection", "rc": 0}]
        self.assertEqual([], self.gate.supply_chain_issues(rows))

    def test_failure_becomes_issue_with_tail(self):
        rows = [{"id": "site_numbers", "rc": 1,
                 "tail": ["✗ 站点 npm 件数与 payload 清单不一致：3011（清单 3012）"]}]
        issues = self.gate.supply_chain_issues(rows)
        self.assertEqual(1, len(issues))
        self.assertIn("site_numbers", issues[0])
        self.assertIn("不一致", issues[0])

    def test_skipped_steps_are_not_issues(self):
        rows = [{"id": "site_numbers", "rc": 0, "skipped": True}]
        self.assertEqual([], self.gate.supply_chain_issues(rows))

    def test_declared_steps_cover_both_faces(self):
        ids = [s[0] for s in self.gate.SUPPLY_STEPS]
        self.assertEqual(["site_numbers", "llms_projection"], ids)


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
        """--allow-dirty 放行脏树；但 payload 与 HEAD 脱节时仍按前置不满足退出（rc=2）。

        判据只钉「脏树不阻断」这件事——payload 是否新鲜取决于提交历史，不是测试能假设的。
        """
        proc = self._run("--jobs", "1", "--allow-dirty")
        doc = json.loads(proc.stdout)
        self.assertEqual("", doc["blocked"])
        if doc.get("payload_blocked"):
            self.assertEqual(2, proc.returncode)
        else:
            self.assertEqual(0, proc.returncode)


class TestOnlyPreflight(unittest.TestCase):
    def test_preflight_runs_supply_chain_without_shards(self):
        """前置面可在几秒内单跑（脏树也允许）：这是「我到底该不该花 29 分钟」的判断入口。"""
        proc = subprocess.run([sys.executable, str(SCRIPT), "--only-preflight", "--allow-dirty",
                               "--json"], cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        # 前置面含「生成物新鲜度」与「payload 对 HEAD」——都依赖树/提交状态（可能合理地不满足），
        # 故这里只钉**结构**与 rc 一致性；「干净树上必须全过」由 test_freshness_check 钉。
        if proc.returncode == 2:
            doc = json.loads(proc.stdout)
            self.assertFalse(doc["ok"])
            self.assertIn("payload_blocked", doc)
            return
        doc = json.loads(proc.stdout)
        self.assertEqual(2, len(doc["supply_chain"]))
        self.assertIn("freshness", doc)
        if proc.returncode == 0:
            self.assertTrue(doc["ok"])
            self.assertEqual([], doc["issues"])
        else:
            self.assertEqual(1, proc.returncode)
            self.assertIn("生成物", json.dumps(doc, ensure_ascii=False))


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


class TestHeadMoveGuard(unittest.TestCase):
    """并发会话下「跑动中的树」必须判无效：green/red 都得绑定同一个 HEAD。"""

    def setUp(self):
        self.gate = _load()

    def test_same_head_passes(self):
        self.assertEqual("", self.gate.head_move_guard("abc123", "abc123"))

    def test_moved_head_invalidates(self):
        msg = self.gate.head_move_guard("abc123def456", "999888777666")
        self.assertIn("HEAD", msg)
        self.assertIn("无效", msg)
        self.assertIn("abc123def456"[:12], msg)

    def test_missing_head_is_not_a_failure(self):
        self.assertEqual("", self.gate.head_move_guard("", "abc"))
        self.assertEqual("", self.gate.head_move_guard("abc", ""))


if __name__ == "__main__":
    unittest.main()
