#!/usr/bin/env python3
"""套件级隔离的**契约测试**（P1）：单模块跑与全量跑必须看到同一初始态。

背景（2026-10-17 实测）：`test_launcher` / `test_watch` 单模块跑会红、全量跑却绿——判据依赖
「守护不在跑」这个进程外部状态。修法见 `desktop/tests/__init__.py`：套件导入时把
`NARRATIVE_FORGE_HOME` 兜底到临时目录，退出时停掉其中的守护。

本文件钉住三条，防止隔离被"优化"掉：
1. 未显式指定时，套件必有一个**临时** home（不是用户真实 `~/.NinFenz`）；
2. 该 home 与仓库路径不同源，且不带用户主目录前缀；
3. 显式设置过的 home 不被套件篡改（用例自管隔离时不许被覆盖）。
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


class SuiteHomeIsolationTest(unittest.TestCase):
    @staticmethod
    def _verify_tests_module():
        path = ROOT / "scripts" / "verify_tests.py"
        spec = importlib.util.spec_from_file_location("nf_verify_tests_retry", path)
        if spec is None or spec.loader is None:
            raise AssertionError("cannot load verify_tests.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_session_home_is_a_temp_dir(self):
        home = os.environ.get("NARRATIVE_FORGE_HOME", "")
        self.assertTrue(home, "套件未设置 NARRATIVE_FORGE_HOME——隔离兜底被移除了？")
        self.assertTrue(Path(home).is_dir(), "套件 home 不是目录：%s" % home)
        self.assertEqual(Path(tempfile.gettempdir()).resolve(),
                         Path(home).resolve().parent,
                         "套件 home 必须落在系统临时目录下（不许指向用户真实 home）")

    def test_session_home_is_not_the_real_user_home(self):
        home = Path(os.environ.get("NARRATIVE_FORGE_HOME", "")).resolve()
        self.assertNotEqual(Path.home().resolve() / ".NinFenz", home,
                            "套件 home 指向了用户真实 ~/.NinFenz")

    def test_repo_root_is_not_the_home(self):
        home = Path(os.environ.get("NARRATIVE_FORGE_HOME", "")).resolve()
        self.assertNotEqual(ROOT.resolve(), home, "套件 home 不该是仓库根")

    def test_shard_runner_owns_cleanup_for_explicit_home(self):
        """分片显式传 home 时，`desktop/tests/__init__.py` 的 atexit 不注册。"""
        src = (ROOT / "scripts" / "verify_tests.py").read_text(encoding="utf-8")
        for needle in ("_cleanup_shard_home", "daemon.json", "popen_capture",
                       "NF_SHARD_TIMEOUT",
                       'env.setdefault("NF_DAEMON_IDLE", "30")'):
            self.assertIn(needle, src, f"分片执行器缺进程/守护回收判据：{needle}")
        atom = (ROOT / "desktop" / "src" / "core" / "atoms" / "proc.py").read_text(
            encoding="utf-8")
        for needle in ("def kill_tree", "taskkill", "def popen_capture"):
            self.assertIn(needle, atom, f"进程原子缺超时树回收判据：{needle}")

    def test_shard_temp_directory_retries_transient_permission_errors(self):
        """Windows AV/indexer locks must not turn a shard into a 0-second false red."""
        module = self._verify_tests_module()
        real = tempfile.TemporaryDirectory(prefix="nf_shard_retry_")
        with mock.patch.object(
            module.tempfile,
            "TemporaryDirectory",
            side_effect=[PermissionError(13, "busy"), real],
        ) as factory, module._temporary_directory(
                "nf_shard_retry_", ignore_cleanup_errors=True) as home:
            self.assertTrue(Path(home).is_dir())
        self.assertTrue(factory.call_args.kwargs["ignore_cleanup_errors"])
        self.assertFalse(Path(real.name).exists(), "临时 home 必须在上下文退出后回收")

    def test_full_gate_uses_the_measured_ten_shard_cap(self):
        """20-core host benchmark says 10 is the wall-clock/stability turning point."""
        text = (ROOT / "verify.sh").read_text(encoding="utf-8")
        self.assertEqual(2, text.count("print(min(10, max(2, (os.cpu_count() or 2) - 1)))"))

    def test_coverage_entries_use_the_isolated_shard_runner(self):
        """覆盖率入口必须经分片执行器（独立 home/进程），不得裸跑单进程 discover。"""
        paths = (
            ROOT / ".github" / "workflows" / "coverage.yml",
            ROOT / "scripts" / "coverage_summary.sh",
            ROOT / "scripts" / "gates_all.sh",
            ROOT / "scripts" / "per_module_coverage.sh",
        )
        stale = []
        for p in paths:
            text = p.read_text(encoding="utf-8")
            if "verify_tests.py" not in text or "NF_COVERAGE" not in text:
                stale.append(str(p.relative_to(ROOT)))
        self.assertEqual([], stale,
                         "覆盖率入口绕过了进程隔离（修复指引：经 verify_tests.py + NF_COVERAGE=1）")

    def test_coverage_workflow_bootstraps_clean_clone_dirs(self):
        """coverage 单 job 也须补齐 CI 忽略目录，否则文档可达性与资产面在干净 clone 必红。"""
        text = (ROOT / ".github" / "workflows" / "coverage.yml").read_text(encoding="utf-8")
        for rel in (".gitee/ISSUE_TEMPLATE", "engine/dotnet/dist",
                    "engine/rust/canonical/target"):
            self.assertIn(rel, text)


if __name__ == "__main__":
    unittest.main()
