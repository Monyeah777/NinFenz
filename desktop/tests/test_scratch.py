"""scratch 裁决点的边界契约（TDD）：每条都对应一个真实事故或一条防御性边界。

覆盖：优先级、不可写回退、仓内默认拒绝/显式放行、全不可用 fail-closed、
绝不回退 cwd、进程内记忆与重置、tempdir 改写、唯一目录、上下文清理、TTL GC。
"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import scratch  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        scratch.reset_cache()
        self._env = {k: os.environ.get(k) for k in (
            scratch.ENV_ROOT, scratch.ENV_ALLOW_REPO, scratch.ENV_TTL_HOURS,
            "NARRATIVE_FORGE_HOME", "TEMP", "TMP", "TMPDIR")}
        # 本仓测试环境的唯一可写区常常就在仓内（.rivet/tmp），故测试默认放行仓内候选；
        # "默认拒绝"那条用例会显式删掉这个开关。
        os.environ[scratch.ENV_ALLOW_REPO] = "1"

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        scratch.reset_cache()
        tempfile.tempdir = None

    def _tmpdir(self):
        d = tempfile.mkdtemp(prefix="nf_scratch_test_")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return Path(d)


class ResolveTest(_Base):
    def test_explicit_root_wins(self):
        d = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(d)
        self.assertEqual(scratch.resolve(), d)

    def test_unwritable_explicit_falls_through(self):
        bad = self._tmpdir() / "not_a_dir"
        bad.write_text("x", encoding="utf-8")
        good = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(bad)
        os.environ["NARRATIVE_FORGE_HOME"] = str(good)
        got = scratch.resolve()
        self.assertNotEqual(got, bad)
        self.assertTrue(got.is_dir())

    def test_repo_inside_candidate_rejected_by_default(self):
        os.environ.pop(scratch.ENV_ALLOW_REPO, None)
        inside = scratch._repo_root() / ".rivet" / "tmp"
        with (mock.patch.object(scratch, "_candidates", return_value=[inside]),
              self.assertRaises(scratch.ScratchUnavailable) as ctx):
            scratch.resolve()
        self.assertIn(scratch.ENV_ALLOW_REPO, str(ctx.exception))

    def test_repo_inside_allowed_with_explicit_opt_in(self):
        inside = scratch._repo_root() / ".rivet" / "tmp"
        os.environ[scratch.ENV_ALLOW_REPO] = "1"
        with mock.patch.object(scratch, "_candidates", return_value=[inside]):
            self.assertEqual(scratch.resolve(), inside)

    def test_all_candidates_unusable_fails_closed(self):
        bad = self._tmpdir() / "file"
        bad.write_text("x", encoding="utf-8")
        with (mock.patch.object(scratch, "_candidates", return_value=[bad]),
              self.assertRaises(scratch.ScratchUnavailable)):
            scratch.resolve()

    def test_never_falls_back_to_cwd(self):
        bad = self._tmpdir() / "file"
        bad.write_text("x", encoding="utf-8")
        old = os.getcwd()
        work = self._tmpdir()
        os.chdir(work)
        try:
            with (mock.patch.object(scratch, "_candidates", return_value=[bad]),
                  self.assertRaises(scratch.ScratchUnavailable)):
                scratch.resolve()
        finally:
            os.chdir(old)

    def test_resolution_is_memoized_and_reset_clears(self):
        d = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(d)
        first = scratch.resolve()
        os.environ[scratch.ENV_ROOT] = str(self._tmpdir())
        self.assertEqual(scratch.resolve(), first)
        scratch.reset_cache()
        self.assertNotEqual(scratch.resolve(), first)


class ProcessTempdirTest(_Base):
    def test_ensure_process_tempdir_rewrites_env_and_tempfile(self):
        d = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(d)
        got = scratch.ensure_process_tempdir()
        self.assertEqual(got, d)
        for key in ("TEMP", "TMP", "TMPDIR"):
            self.assertEqual(os.environ[key], str(d))
        self.assertEqual(tempfile.gettempdir(), str(d))
        self.assertEqual(tmpfile_dir(), str(d))


def tmpfile_dir():
    fd, p = tempfile.mkstemp()
    os.close(fd)
    os.unlink(p)
    return os.path.dirname(p)


class ScratchDirTest(_Base):
    def setUp(self):
        super().setUp()
        self.root = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(self.root)

    def test_new_dir_is_unique_and_exists(self):
        a = scratch.new_dir("nfx")
        b = scratch.new_dir("nfx")
        self.assertNotEqual(a, b)
        self.assertTrue(a.is_dir() and b.is_dir())
        self.assertTrue(a.parent == self.root)

    def test_scratch_dir_cleans_up_on_success(self):
        with scratch.scratch_dir("nfx") as d:
            (d / "payload.txt").write_text("x", encoding="utf-8")
            self.assertTrue(d.is_dir())
        self.assertFalse(d.exists())

    def test_scratch_dir_cleans_up_on_exception(self):
        holder = {}
        with (self.assertRaises(RuntimeError),
              scratch.scratch_dir("nfx") as d):
            holder["d"] = d
            raise RuntimeError("boom")
        self.assertFalse(holder["d"].exists())


class GcTest(_Base):
    def test_gc_removes_only_stale_prefixed_dirs(self):
        """S1（2026-10-22）：GC 只删 `nf-<12hex>` 目录；用户文件与其它条目绝不删。"""
        root = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(root)
        self.assertEqual(scratch.resolve(), root, "先收养空根（写 .nf-scratch 标记）")
        stale = root / "nf-abc123def456"
        fresh = root / "nf-0123456789ab"
        legacy = root / "nf-stale"
        other = root / "keep-me"
        keep = root / "keep.txt"
        for d in (stale, fresh, legacy, other):
            d.mkdir()
        keep.write_text("用户数据", encoding="utf-8")
        old = time.time() - 48 * 3600
        for p in (stale, legacy, other):
            os.utime(p, (old, old))
        result = scratch.gc()
        self.assertEqual(result["removed"], 1, result)
        self.assertFalse(stale.exists(), "matche nf-<12hex> 的过期目录必删")
        self.assertTrue(fresh.exists(), "未过期的 nf-<12hex> 目录保留")
        self.assertTrue(legacy.exists(), "不匹配 nf-<12hex> 的目录不归本模块管，绝不删")
        self.assertTrue(other.exists(), "非 nf* 目录不归本模块管，绝不删")
        self.assertTrue(keep.exists(), "S1：用户放的同级文件必须原样保留")
        self.assertGreaterEqual(result["skipped"], 4, result)

    def test_gc_skips_keep_txt_and_deletes_hex_dir(self):
        """工单验收形态：根下放 keep.txt + nf-abc123def456/ ⇒ GC 后 keep.txt 在、目录被删。"""
        root = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(root)
        self.assertEqual(scratch.resolve(), root, "先收养空根（写 .nf-scratch 标记）")
        keep = root / "keep.txt"
        keep.write_text("不要删我", encoding="utf-8")
        target = root / "nf-abc123def456"
        target.mkdir()
        old = time.time() - 48 * 3600
        os.utime(target, (old, old))
        result = scratch.gc()
        self.assertEqual(result["removed"], 1, result)
        self.assertFalse(target.exists())
        self.assertTrue(keep.exists(), "S1：keep.txt 必须还在")
        self.assertEqual(keep.read_text(encoding="utf-8"), "不要删我")

    def test_gc_refuses_root_without_marker(self):
        """S1：缺 `.nf-scratch` 根标记 ⇒ 拒绝 GC（防 NF_SCRATCH 指到别人的目录）。"""
        root = self._tmpdir()
        os.environ[scratch.ENV_ROOT] = str(root)
        self.assertEqual(scratch.resolve(), root)
        keep = root / "keep.txt"
        keep.write_text("x", encoding="utf-8")
        target = root / "nf-abc123def456"
        target.mkdir()
        os.utime(target, (time.time() - 48 * 3600,) * 2)
        (root / scratch.MARKER).unlink()     # 模拟：标记被删/根不是本模块建的
        with self.assertRaises(scratch.ScratchUnavailable) as ctx:
            scratch.gc()
        self.assertIn(scratch.MARKER, str(ctx.exception))
        self.assertTrue(keep.exists())
        self.assertTrue(target.exists(), "拒绝时必须一个都不删")

    def test_refuses_to_adopt_home_like_dir(self):
        """S1：非空、无标记且含非本模块条目的目录不被收养（$HOME 形态）。"""
        home_like = self._tmpdir()
        (home_like / "documents").mkdir()
        (home_like / "keep.txt").write_text("x", encoding="utf-8")
        with (mock.patch.object(scratch, "_candidates", return_value=[home_like]),
              self.assertRaises(scratch.ScratchUnavailable)):
            scratch.resolve()
        self.assertTrue((home_like / "keep.txt").exists())
        self.assertFalse((home_like / scratch.MARKER).exists(), "拒绝收养时不得写标记")


class InRepoTest(unittest.TestCase):
    def test_repo_and_outside(self):
        self.assertTrue(scratch.in_repo(scratch._repo_root() / "verify.sh"))
        self.assertFalse(scratch.in_repo(Path.home()))


if __name__ == "__main__":
    unittest.main()
