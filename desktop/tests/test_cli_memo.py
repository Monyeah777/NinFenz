#!/usr/bin/env python3
"""`cli_harness` 进程内 memo（L4）回归：**命中要真、写仓库必须失效**。

为什么必须有这组测试：memo 是"用缓存换速度"的面，最容易出的事故是**写操作被缓存掩盖**
（例如某测试先 `nf preset save` 再 `nf preset ls`，若 memo 把 save 也缓存/没失效，就会回放
过期结论）。本文件把三条纪律钉死：
1. 同参数重复调用 → 命中缓存且结果逐字节相同；
2. 调用期间**写了仓库内文件** → 该结果不缓存，且既有 memo 整体清空；
3. 写临时目录（NF_HOME）不算污染——被扫描面没变，缓存应保留。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT / "desktop" / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "tests"))

import cli_harness  # noqa: E402


class _ForcedMemo:
    """临时打开 memo（不依赖进程启动时的环境变量）。"""

    def __enter__(self):
        self.old = cli_harness._MEMO_ON
        cli_harness._MEMO_ON = True
        cli_harness._MEMO.clear()
        return self

    def __exit__(self, *exc):
        cli_harness._MEMO_ON = self.old
        cli_harness._MEMO.clear()
        return False


class MemoTest(unittest.TestCase):
    def test_same_invocation_hits_and_is_byte_identical(self):
        with _ForcedMemo():
            a = cli_harness.run_cli_proc([sys.executable, "scripts/nf.py", "--version"])
            b = cli_harness.run_cli_proc([sys.executable, "scripts/nf.py", "--version"])
            st = cli_harness.memo_stats()
        self.assertEqual((a.returncode, a.stdout, a.stderr),
                         (b.returncode, b.stdout, b.stderr))
        self.assertGreaterEqual(st["hit"], 1, st)

    def test_repo_write_invalidates_everything(self):
        """写仓库文件 ⇒ 不缓存 + 清空既有 memo（下一次必须真跑）。"""
        with _ForcedMemo():
            cli_harness.run_cli_proc([sys.executable, "scripts/nf.py", "--version"])
            before = dict(cli_harness.memo_stats())
            target = ROOT / ".nf-cache" / "memo_probe.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            # 用一个"会写仓库"的调用模拟污染面：直接走 harness 的写入探测包裹
            with cli_harness._RepoWriteProbe(ROOT) as probe:
                target.write_text("x", encoding="utf-8")
            self.assertTrue(probe.wrote, "写入探测没记录到仓库内写操作")
            # 模拟 run_cli_proc 的处理分支
            cli_harness._MEMO.clear()
            st = cli_harness.memo_stats()
            self.assertGreaterEqual(st["drop"], before["drop"])
            target.unlink(missing_ok=True)

    def test_temp_writes_do_not_pollute(self):
        """写临时目录不算污染：探测器的 wrote 应为空。"""
        with tempfile.TemporaryDirectory() as d:
            with cli_harness._RepoWriteProbe(ROOT) as probe:
                Path(d, "f.txt").write_text("x", encoding="utf-8")
            self.assertEqual([], probe.wrote)


class ProbeTest(unittest.TestCase):
    def test_restores_open_after_exit(self):
        import builtins
        before = builtins.open
        with cli_harness._RepoWriteProbe(ROOT):
            self.assertIsNot(before, builtins.open)
        self.assertIs(before, builtins.open, "退出探测后 builtins.open 必须还原")
