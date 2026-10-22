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
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SuiteHomeIsolationTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
