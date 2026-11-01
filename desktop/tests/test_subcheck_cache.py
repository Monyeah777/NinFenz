#!/usr/bin/env python3
"""子 check 缓存（`core/subcheck_cache.py`）的判据：**命中即等价，且绝不假命中**。

为什么这几条是硬判据
--------------------
缓存是**唯一能把「跑过了」与「判定为真」脱钩**的机制——它一旦错，门禁就会拿旧结论
当新结论（`ADR-0002-门禁不注水` 禁止的正是这件事）。故这里不测「快不快」，
只测**语义**：命中必须等价、输入一变必须失效、说不清必须重跑。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import subcheck_cache as sc  # noqa: E402


class _TempHome(unittest.TestCase):
    """隔离 `NF_HOME`，免得把开发机的真实缓存搅进来。"""

    def setUp(self):
        self._old = os.environ.get("NARRATIVE_FORGE_HOME")
        self.home = tempfile.mkdtemp(prefix="nf_subcheck_home_")
        os.environ["NARRATIVE_FORGE_HOME"] = self.home
        self.root = Path(tempfile.mkdtemp(prefix="nf_subcheck_root_"))
        (self.root / "a.txt").write_text("A1", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.txt").write_text("B1", encoding="utf-8")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("NARRATIVE_FORGE_HOME", None)
        else:
            os.environ["NARRATIVE_FORGE_HOME"] = self._old
        import shutil
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.root, ignore_errors=True)

    def _runner(self, out):
        def run():
            # 读一个文件：判据就是它的内容
            return (self.root / "a.txt").read_text(encoding="utf-8")
        return run


class HitIsEquivalentTest(_TempHome):
    def test_second_run_is_a_hit_and_same_value(self):
        r = self._runner(None)
        v1, s1 = sc.run_cached(str(self.root), "probe", r)
        v2, s2 = sc.run_cached(str(self.root), "probe", r)
        self.assertEqual("run", s1, "首跑应为 run（建面）")
        self.assertEqual("hit", s2, "输入未变应命中")
        self.assertEqual(v1, v2, "命中值必须与首跑逐字节等价")

    def test_hit_does_not_execute_the_body(self):
        """**判据本体不许跑**——这是「命中」的定义，用副作用证明。"""
        calls = []

        def body():
            calls.append(1)
            return (self.root / "a.txt").read_text(encoding="utf-8")

        sc.run_cached(str(self.root), "probe2", body)
        n_first = len(calls)
        self.assertGreaterEqual(n_first, 1)
        sc.run_cached(str(self.root), "probe2", body)
        self.assertEqual(n_first, len(calls), "命中时判据本体不得被执行")


class NeverFalseHitTest(_TempHome):
    def test_file_content_change_invalidates(self):
        r = self._runner(None)
        sc.run_cached(str(self.root), "probe3", r)
        (self.root / "a.txt").write_text("A2", encoding="utf-8")
        got, state = sc.run_cached(str(self.root), "probe3", r)
        self.assertEqual("run", state, "输入内容已变 ⇒ 必须重算")
        self.assertEqual("A2", got)

    def test_missing_input_invalidates(self):
        """Tup 规则：**缺失即失效**（不许拿「文件没了」当「没变」）。"""
        r = self._runner(None)
        sc.run_cached(str(self.root), "probe4", r)
        (self.root / "a.txt").unlink()
        with self.assertRaises(OSError):
            # 判据本体被**真的重跑**了，于是它自己撞上「文件没了」——正是「缺失即失效」的证据
            sc.run_cached(str(self.root), "probe4", r)

    def test_directory_listing_change_invalidates(self):
        """**目录里多出一个文件**必须失效——它不产生 `open` 事件，只靠文件面会漏。"""
        def body():
            # 读一个文件（让本件可缓存）**并**列举目录（glob 类输入）
            (self.root / "a.txt").read_text(encoding="utf-8")
            return sorted(p.name for p in (self.root / "sub").iterdir())

        sc.run_cached(str(self.root), "probe5", body)
        (self.root / "sub" / "c.txt").write_text("C1", encoding="utf-8")
        got, state = sc.run_cached(str(self.root), "probe5", body)
        self.assertEqual("run", state, "目录项已变 ⇒ 必须重算")
        self.assertIn("c.txt", got)

    def test_empty_read_face_is_never_cached(self):
        """读面为空（输入在环境/时间里）⇒ 一律不缓存。"""
        def body():
            return os.environ.get("SOME_UNCAPTURED_INPUT", "x")

        _v, s1 = sc.run_cached(str(self.root), "probe6", body)
        _v, s2 = sc.run_cached(str(self.root), "probe6", body)
        self.assertEqual("untrusted", s1)
        self.assertEqual("untrusted", s2, "读面为空的件不得进先验表")
        self.assertIsNone(sc.read_face(str(self.root), "probe6"))

    def test_outside_read_is_never_cached(self):
        """读到仓外 ⇒ 不缓存（仓外内容不在内容寻址管辖内）。"""
        outside = Path(tempfile.mkdtemp(prefix="nf_subcheck_out_"))
        try:
            (outside / "o.txt").write_text("O", encoding="utf-8")

            def body():
                return (outside / "o.txt").read_text(encoding="utf-8")

            _v, s1 = sc.run_cached(str(self.root), "probe7", body)
            self.assertEqual("untrusted", s1, "读到仓外 ⇒ 不得缓存")
        finally:
            import shutil
            shutil.rmtree(outside, ignore_errors=True)


class DirFaceIsNotMemoizedTest(_TempHome):
    """**目录项哈希不按 mtime 记忆**——这条是「实测否决一个优化」的守门判据。

    背景（2026-10-16）：大 check 的命中复核成本全在重算目录项哈希，于是「拿目录 mtime
    当廉价失效键」看起来很值。但实测发现在同一瞬时内新增条目时**目录 mtime 可能不变**
    （Windows/NTFS 复现），记忆就会返回旧哈希 ⇒ **假命中**。按 `ADR-0002-门禁不注水`，
    本模块**不记忆**，每次老实重算。下面的判据守住「不许把记忆再加回来」。
    """

    def test_added_entry_always_changes_the_dir_digest(self):
        d = self.root / "sub"
        first = sc.dir_digest(d)
        (d / "new.txt").write_text("N", encoding="utf-8")
        self.assertNotEqual(first, sc.dir_digest(d),
                            "新增条目后目录项哈希必须变（不许靠 mtime 记忆吞掉它）")

    def test_snapshot_recomputes_dir_digest_every_time(self):
        """同一次进程内连取两次快照，目录哈希都必须**当场重算**（无记忆即无陈旧）。"""
        d = self.root / "sub"
        snap1 = sc.snapshot(str(self.root), ["sub/b.txt"], ["sub"])
        (d / "later.txt").write_text("L", encoding="utf-8")
        snap2 = sc.snapshot(str(self.root), ["sub/b.txt"], ["sub"])
        self.assertNotEqual(snap1["dirs"]["sub"], snap2["dirs"]["sub"],
                            "快照不得复用上一次的目录项哈希")

    def test_file_content_change_is_caught_by_the_file_face(self):
        """**互补性判据**：改文件内容**不改**目录项哈希，必须由 `files` 面独立抓住。"""
        (self.root / "sub" / "b.txt").write_text("B1", encoding="utf-8")
        face = sc.snapshot(str(self.root), ["sub/b.txt"], ["sub"])
        (self.root / "sub" / "b.txt").write_text("B2", encoding="utf-8")
        ok, why = sc.equiv(str(self.root), face)
        self.assertFalse(ok, "内容变化必须由 files 面抓住")
        self.assertTrue(any("输入已变" in w for w in why))

    def test_ancestors_are_not_in_the_snapshot_by_default(self):
        """默认**不**把祖先目录塞进快照（实测净亏来源：check39 目录面膨胀到 24718）。"""
        snap = sc.snapshot(str(self.root), ["sub/b.txt"], [])
        self.assertNotIn("sub", snap["dirs"], "未实际列举的祖先目录不应进快照")
        self.assertIn("sub/b.txt", snap["files"])
        snap2 = sc.snapshot(str(self.root), ["sub/b.txt"], [], with_ancestors=True)
        self.assertIn("sub", snap2["dirs"], "with_ancestors=True 用于诊断/对照")


class RuntimePathNotOutsideTest(_TempHome):
    def test_interpreter_paths_do_not_mark_untrusted(self):
        """读**解释器自己的地盘**（stdlib / site-packages）不得算「读到仓外」。

        不过滤的实测后果（2026-10-16）：check33 报 **948** 条仓外读（全是 `csv.pyc` 这类
        字节码）⇒ 永久判为不可缓存。过滤后仍须把**真仓外**（用户 home / 临时目录）算进去。
        """
        import sys as _sys
        stdlib_probe = Path(_sys.prefix) / "os.py"
        if not stdlib_probe.is_file():
            self.skipTest("本机 stdlib 布局不同")
        _v, _files, _dirs, outside = sc.observe(
            str(self.root), lambda: stdlib_probe.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual([], outside, "解释器路径不得被报成仓外")

    def test_real_outside_read_is_still_reported(self):
        """真仓外（例如用户临时目录）**仍须**报出来 —— 过滤不能过宽。"""
        outside_dir = Path(tempfile.mkdtemp(prefix="nf_sc_out2_"))
        try:
            f = outside_dir / "o.txt"
            f.write_text("O", encoding="utf-8")
            _v, _files, _dirs, outside = sc.observe(
                str(self.root), lambda: f.read_text(encoding="utf-8"))
            self.assertTrue(outside, "真仓外读取必须被报出（否则缓存会越界复用）")
        finally:
            import shutil
            shutil.rmtree(outside_dir, ignore_errors=True)


class RelFaceBoundaryTest(_TempHome):
    def test_in_repo_paths_are_not_misjudged_as_outside(self):
        """**回归判据**：仓内相对路径不得被判成仓外。

        2026-10-16 实测抓到的真 bug：`gate_faces.rel_face` 按 `normcase(abspath)` 比较，
        而 hook 收到的是**原始 open 路径**；盘符大小写/cd 之后不同形时，`03_管线库/…`
        这类**明明在仓内**的路径被判成仓外 ⇒ check33/39/40 永久不缓存。
        本模块改用 `resolve()` 判界，这里守住它。
        """
        _v, files, _dirs, outside = sc.observe(
            str(self.root), lambda: (self.root / "a.txt").read_text(encoding="utf-8"))
        self.assertIn("a.txt", files, "仓内文件必须在读面里")
        self.assertEqual([], outside, "仓内文件不得被报成仓外")

    def test_nested_relative_path_is_inside(self):
        old = os.getcwd()
        os.chdir(str(self.root))
        try:
            _v, files, _dirs, outside = sc.observe(
                str(self.root), lambda: (self.root / "sub" / "b.txt").read_text(encoding="utf-8"))
        finally:
            os.chdir(old)
        self.assertIn("sub/b.txt", files)
        self.assertEqual([], outside)


if __name__ == "__main__":
    unittest.main()
