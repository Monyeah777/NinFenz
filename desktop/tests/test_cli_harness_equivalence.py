# -*- coding: utf-8 -*-
"""P-I3 等价性差分 + 收益实测：harness 只对被证明等价的命令类放行。

语料刻意选**只读、廉价**的入口面（版本/帮助/参数错误）。任何一例不等价即红——那是
「该命令类不得用 harness」的结论，不是可以放宽的噪声。
"""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "tests"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import cli_harness as h  # noqa: E402

CORPUS = (
    ["--version"],
    ["--help"],
    ["-h"],
    ["definitely-not-a-command"],
    ["daemon", "--help"],
)


class EquivalenceTest(unittest.TestCase):
    def test_corpus_is_byte_equivalent(self):
        bad = []
        for argv in CORPUS:
            ok, why = h.equivalent(argv)
            if not ok:
                bad.append((argv, why))
        self.assertEqual([], bad, "这些命令类不得用 harness：%s" % bad[:3])

    def test_harness_is_cheaper_after_warmup(self):
        h.run_cli(["--version"])                       # 冷启动（导入 nf.py）
        t0 = time.perf_counter()
        for _ in range(3):
            h.run_cli(["--version"])
        warm = (time.perf_counter() - t0) / 3
        t0 = time.perf_counter()
        h.spawn_cli(["--version"])
        cold = time.perf_counter() - t0
        self.assertLess(warm, cold, "热路径应快于单次 spawn：warm=%.4fs cold=%.4fs" % (warm, cold))
        print("\n[P-I3] warm=%.4fs · spawn=%.4fs · 比值 %.1f×"
              % (warm, cold, cold / warm if warm else float("inf")))


if __name__ == "__main__":
    unittest.main()
