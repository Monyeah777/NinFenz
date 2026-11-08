"""发布结论复跑器（scripts/release_conclusion.py）单测——纯函数判据 + dry-run 集成。

与 nf release（发布编排：冻结链次序）分工不同：本件判「冻结后能不能发布」。真正的分片执行要
10+ 分钟，不适合常驻单测；但**闸门逻辑**（脏树拒绝、分片汇总、计划生成）是这套东西的判据
所在，必须常驻可验——尤其脏树闸门：我自己踩过「在改到一半的树上跑分片拿到一堆假红」。
"""
import importlib.util
import json
import os
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

    def test_lock_reclaim_rules(self):
        """锁抢断规则：空/死进程/超龄可抢；活进程未超龄绝不可抢（并发跑两份会互相清 worktree）。"""
        gate = self.gate
        self.assertTrue(gate.lock_should_reclaim(None, False, 0.0))
        self.assertTrue(gate.lock_should_reclaim({"pid": 1}, False, 60.0))
        self.assertTrue(gate.lock_should_reclaim({"pid": 1}, True, 4 * 3600.0))
        self.assertEqual("", gate.lock_should_reclaim({"pid": 1}, True, 60.0))

    def test_lock_acquire_refuses_when_held_and_releases(self):
        import tempfile
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # 持有者是**活着的**本进程：未超龄，别人（另一个 pid）必须被拒
            ok, why = gate.lock_acquire(base, "a" * 40, pid=os.getpid(), now=1000.0)
            self.assertTrue(ok, why)
            ok2, why2 = gate.lock_acquire(base, "b" * 40, pid=os.getpid() + 1,
                                          now=1060.0)
            self.assertFalse(ok2)
            self.assertIn("另一份全量快照正在跑", why2)
            gate.lock_release(base, pid=os.getpid())
            ok3, why3 = gate.lock_acquire(base, "c" * 40, pid=os.getpid(), now=1200.0)
            self.assertTrue(ok3, why3)
            # 别人的 pid 不能删我的锁
            gate.lock_release(base, pid=999999)
            self.assertTrue((base / gate.LOCK_NAME).is_file())
            gate.lock_release(base, pid=os.getpid())
            self.assertFalse((base / gate.LOCK_NAME).is_file())


    def test_lock_acquire_wait_times_out_on_live_holder(self):
        """活锁 + 短等待：等满就放弃（不无限等），并且不误删别人的锁。"""
        import tempfile
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            import time as _t
            gate.lock_acquire(base, "a" * 40, pid=os.getpid(), now=_t.time())
            ok, why = gate.lock_acquire_wait(base, "b" * 40, pid=os.getpid() + 1,
                                             wait_s=0.6, poll_s=0.2)
            self.assertFalse(ok)
            self.assertIn("另一份全量快照正在跑", why)
            self.assertTrue((base / gate.LOCK_NAME).is_file())

    def test_lock_acquire_wait_takes_over_dead_holder(self):
        """死进程的锁：等待路径下应当立刻接管（不用等满）。"""
        import tempfile
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gate.lock_acquire(base, "a" * 40, pid=999999, now=1000.0)
            ok, why = gate.lock_acquire_wait(base, "b" * 40, pid=os.getpid(),
                                             wait_s=5.0, poll_s=0.1)
            self.assertTrue(ok, why)




    def test_status_snapshot_reports_lock_and_latest(self):
        """现场体检：锁/运行目录/最近结论都能读出来，且优先报「与锁同 HEAD」的那份。"""
        import tempfile
        import time as _t
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gate.lock_acquire(base, "b" * 40, pid=os.getpid(), now=_t.time())
            run_old = base / ("nf-gate-snap-" + "a" * 12 + "-old")
            run_new = base / ("nf-gate-snap-" + "b" * 12 + "-new")
            run_old.mkdir()
            run_new.mkdir()
            (run_old / "gate.log").write_text(json.dumps({"ok": True, "wall_s": 1.0}),
                                               encoding="utf-8")
            status = gate.status_snapshot(base)
            self.assertEqual("nf-snapshot-status/1", status["schema"])
            self.assertTrue(status["running"])
            self.assertEqual("b" * 12, status["lock"]["head"][:12])
            self.assertIn("new", status["latest"]["run"], "应优先报与锁同 HEAD 的那份")
            gate.lock_release(base, pid=os.getpid())
            self.assertFalse(gate.status_snapshot(base)["running"])
    def test_max_wall_cap_is_declared_and_used(self):
        """墙钟上限：常量 5400 s 且在 CLI/内层等待处都用到（防挂死无限等）。"""
        gate = self.gate
        self.assertEqual(5400.0, float(gate.DEFAULT_MAX_WALL_S))
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("--max-wall-s", src)
        self.assertIn("wall_cap = float(getattr(args, \"max_wall_s\"", src)
        self.assertIn("快照墙钟超限", src)
        help_text = subprocess.run([str(sys.executable), str(SCRIPT), "--help"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace").stdout
        self.assertIn("--max-wall-s", help_text)
    def test_locked_run_exits_2_with_guidance(self):
        """集成：锁被占用时 --snapshot 必须退出码 2 并给 pid/HEAD/指引（不静默继续）。"""
        import tempfile
        import time as _t
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gate.lock_acquire(base, "a" * 40, pid=os.getpid(), now=_t.time())
            env = dict(os.environ)
            env["NF_SNAPSHOT_LOCK_DIR"] = tmp
            proc = subprocess.run([str(sys.executable), str(SCRIPT), "--snapshot", "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env, timeout=300, cwd=str(ROOT))
            self.assertEqual(2, proc.returncode, proc.stderr[-300:])
            self.assertIn("另一份全量快照正在跑", proc.stderr)
    def test_lock_force_takes_over(self):
        import tempfile
        gate = self.gate
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gate.lock_acquire(base, "a" * 40, pid=os.getpid(), now=1000.0)
            ok, why = gate.lock_acquire(base, "b" * 40, pid=os.getpid(), now=1010.0,
                                        force=True)
            self.assertTrue(ok, why)

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


class TestRatchets(unittest.TestCase):
    """静态棘轮（风格/度量/耦合/SAST）进前置面：这类红跑测试也变不绿，必须秒级拦。"""

    def setUp(self):
        self.gate = _load()

    def test_all_pass_no_issues(self):
        rows = [{"id": "style", "rc": 0}, {"id": "sast", "rc": 0}]
        self.assertEqual([], self.gate.ratchet_issues(rows))

    def test_failure_becomes_issue_with_tail(self):
        rows = [{"id": "style", "rc": 1,
                 "tail": ["新增风格命中 a.py · E501（修复指引：修掉）"]}]
        issues = self.gate.ratchet_issues(rows)
        self.assertEqual(1, len(issues))
        self.assertIn("style", issues[0])
        self.assertIn("E501", issues[0])

    def test_skipped_rows_are_not_issues(self):
        self.assertEqual([], self.gate.ratchet_issues(
            [{"id": "sast", "rc": 0, "skipped": True}]))

    def test_declared_steps_cover_four_ratchets(self):
        ids = [row[0] for row in self.gate.RATCHET_STEPS]
        self.assertEqual(["style", "code_metrics", "coupling", "sast"], ids)


class TestMidrunDriftGuard(unittest.TestCase):
    """分片途中树变动必须立刻停：否则 8 片落在不同 HEAD 上，红绿都不可信。"""

    def setUp(self):
        self.gate = _load()

    def test_stable_tree_passes(self):
        self.assertEqual("", self.gate.midrun_drift_guard("abc123", "abc123", []))

    def test_head_changed_stops(self):
        msg = self.gate.midrun_drift_guard("abc123def456", "999888777666", [])
        self.assertIn("HEAD", msg)
        self.assertIn("无效", msg)

    def test_dirty_tree_stops_with_example(self):
        msg = self.gate.midrun_drift_guard("abc", "abc", [" M protocol/x.json"])
        self.assertIn("工作树", msg)
        self.assertIn("protocol/x.json", msg)

    def test_missing_head_is_not_drift(self):
        self.assertEqual("", self.gate.midrun_drift_guard("", "", []))

    def test_allow_dirty_same_snapshot_is_not_drift(self):
        """--allow-dirty 起始就脏、途中没变：不能被误判成「途中出现改动」而停（2026-11-06 修）。"""
        initial = [" M protocol/x.json"]
        msg = self.gate.midrun_drift_guard("abc", "abc", [" M protocol/x.json"], initial)
        self.assertEqual("", msg)

    def test_allow_dirty_new_change_still_stops(self):
        initial = [" M protocol/x.json"]
        msg = self.gate.midrun_drift_guard("abc", "abc",
                                           [" M protocol/x.json", "?? new.py"], initial)
        self.assertIn("工作树", msg)

    def test_clean_start_becoming_dirty_stops(self):
        msg = self.gate.midrun_drift_guard("abc", "abc", [" M a.py"], [])
        self.assertIn("工作树", msg)


class TestSnapshotMode(unittest.TestCase):
    """快照门禁：结论钉在一个 SHA 上，与工作区（含并发会话）完全解耦。"""

    def setUp(self):
        self.gate = _load()

    def test_strip_snapshot_flag(self):
        argv = ["--shards", "4", "--snapshot", "--json"]
        self.assertEqual(["--shards", "4", "--json"], self.gate.strip_snapshot_flag(argv))

    def test_strip_keeps_other_flags(self):
        argv = ["--only-preflight", "--allow-dirty"]
        self.assertEqual(argv, self.gate.strip_snapshot_flag(argv))

    def test_snapshot_dir_name_carries_head(self):
        name = self.gate.snapshot_dir_name("0123456789abcdef")
        self.assertIn("0123456789ab", name)
        self.assertTrue(name.startswith("nf-gate-snap-"))

    def test_flag_is_advertised_in_help(self):
        proc = subprocess.run([sys.executable, str(SCRIPT), "--help"], cwd=str(ROOT),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        self.assertIn("--snapshot", proc.stdout)


class TestSnapshotLocation(unittest.TestCase):
    """快照落点必须在**与仓库同盘**的可写目录：$TEMP 落在满盘卷上会把门禁打成 ENOSPC。"""

    def setUp(self):
        self.gate = _load()

    def test_default_is_repo_local(self):
        base = self.gate.snapshot_base(ROOT)
        self.assertTrue(str(base).endswith("gate-snap"), base)
        self.assertIn(".worktrees", str(base).replace("\\", "/"))

    def test_override_relative_is_under_root(self):
        base = self.gate.snapshot_base(ROOT, ".worktrees/custom")
        self.assertEqual(ROOT / ".worktrees" / "custom", base)

    def test_override_absolute_wins(self):
        base = self.gate.snapshot_base(ROOT, "D:/elsewhere/snap")
        self.assertTrue(str(base).startswith("D:"))

    def test_free_space_probe_does_not_raise(self):
        self.assertGreater(self.gate._snapshot_free_bytes(ROOT), 0)


class TestBashIdentity(unittest.TestCase):
    """checks-only 之前先验 bash 身份：WSL 的 bash 会 rc=1 且**零输出**（被误读成判据红）。"""

    def setUp(self):
        self.gate = _load()

    def test_git_bash_flavours_pass(self):
        for text in ("Msys", "CYGWIN_NT-10.0", "MINGW64_NT-10.0", "msys"):
            self.assertEqual("", self.gate.bash_identity_ok(text), text)

    def test_wsl_is_rejected_with_guidance(self):
        msg = self.gate.bash_identity_ok("GNU/Linux")
        self.assertIn("git-bash", msg)
        self.assertIn("修复指引", msg)

    def test_empty_probe_is_rejected(self):
        self.assertIn("修复指引", self.gate.bash_identity_ok(""))


class TestSnapshotHygiene(unittest.TestCase):
    """陈旧快照必须清（几个就几百 MB，撞满盘会伪装成门禁红）：在跑的、这次用的都不许清。"""

    def setUp(self):
        self.gate = _load()

    def test_old_unregistered_is_stale(self):
        entries = [("/base/old", 1000.0)]
        self.assertEqual(["/base/old"],
                         self.gate.stale_snapshot_dirs(entries, set(), 1000.0 + 7 * 3600))

    def test_young_is_kept(self):
        entries = [("/base/new", 1000.0)]
        self.assertEqual([], self.gate.stale_snapshot_dirs(entries, set(), 1000.0 + 60))

    def test_live_worktree_is_never_pruned(self):
        entries = [("/base/live", 1000.0)]
        live = {os.path.abspath("/base/live")}
        self.assertEqual([], self.gate.stale_snapshot_dirs(entries, live, 1000.0 + 99 * 3600))

    def test_current_run_is_kept(self):
        entries = [("/base/mine", 1000.0)]
        self.assertEqual([], self.gate.stale_snapshot_dirs(
            entries, set(), 1000.0 + 99 * 3600, keep="/base/mine"))


class TestSnapshotIsolationPaths(unittest.TestCase):
    """快照内层的落点约束（两条实测教训）：临时目录/家目录都必须在主仓树之外。

    ① 同盘（否则满盘卷上测试自己 ENOSPC）；② 不进仓库树（否则 npm findRepoRoot 向上命中
    活树、不触发解包，test_payload_is_extracted_to_cache_and_runs 假红）。
    """

    def setUp(self):
        self.gate = _load()

    def test_temp_dir_is_on_same_drive_and_outside_repo(self):
        path = str(ROOT / ".worktrees" / "gate-snap" / "run-x" / "wt")
        tmp = self.gate.snapshot_temp_dir(path)
        self.assertEqual(os.path.splitdrive(os.path.abspath(path))[0],
                         os.path.splitdrive(tmp)[0], "必须与快照同盘")
        repo = os.path.abspath(str(ROOT))
        self.assertFalse(os.path.abspath(tmp).startswith(repo + os.sep),
                         "临时目录不能落在仓库树内")
        self.assertIn(".nf-gate-tmp", tmp)

    def test_home_dir_is_outside_worktree(self):
        path = str(ROOT / ".worktrees" / "gate-snap" / "run-y" / "wt")
        home = os.path.abspath(self.gate.snapshot_home_dir(path))
        self.assertFalse(home.startswith(os.path.abspath(path) + os.sep),
                         "NF_HOME 不能在 worktree 里（会被当成仓库件）")

    def test_log_path_lives_in_run_dir_not_worktree(self):
        path = str(ROOT / ".worktrees" / "gate-snap" / "run-z" / "wt")
        log = os.path.abspath(self.gate.snapshot_log_path(path))
        run_dir = os.path.dirname(os.path.abspath(path))
        self.assertEqual(run_dir, os.path.dirname(log))
        self.assertTrue(log.endswith("gate.log"))

    def test_payload_includes_verifier_digest(self):
        """自省层（第 97 轮）：结论必须记录产出它的验证器摘要（判定面脚本摘要）。"""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop" / "src"))
        from core import verifier_version as vv

        src = (Path(__file__).resolve().parents[2] / "scripts" / "release_conclusion.py"
               ).read_text(encoding="utf-8")
        self.assertIn('"verifier_digest": verifier', src,
                      "结论 payload 必须带 verifier_digest 字段")
        self.assertEqual(64, len(vv.digest(str(Path(__file__).resolve().parents[2]))
                                ["verifier_digest"]))

if __name__ == "__main__":
    unittest.main()
