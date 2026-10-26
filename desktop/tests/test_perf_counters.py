#!/usr/bin/env python3
"""结构计数器（`core/perf_counters.py` + `scripts/perf_counters.py`）回归测试。

为什么要有：墙钟判据在本机当日漂移 13.1 s ↔ 24.3 s（热降频/杀毒/并行 CI），结构性计数是
**跨机器稳定**的那一面；它一旦失真（漏计/不还原补丁），后续所有"重复劳动棘轮"都会骗人。
"""
import ast
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import perf_counters  # noqa: E402
from scripts import perf_counters as pc  # noqa: E402


class CountTest(unittest.TestCase):
    def test_counts_open_stat_ast_and_spawn(self):
        with perf_counters.count() as c:
            Path(__file__).read_text(encoding="utf-8")
            Path(__file__).stat()
            ast.parse("x = 1")
            re.search("x", "x = 1")
            subprocess.run([sys.executable, "-c", "pass"], capture_output=True)
        self.assertGreaterEqual(c["open"], 1)
        self.assertGreaterEqual(c["read_text"], 1)
        self.assertGreaterEqual(c["stat"], 1)
        self.assertGreaterEqual(c["ast_parse"], 1)
        self.assertGreaterEqual(c["regex"], 1)
        self.assertGreaterEqual(c["spawn"], 1)

    def test_patches_are_restored(self):
        import builtins
        import os

        before = (builtins.open, os.stat, ast.parse, subprocess.Popen)
        with perf_counters.count():
            pass
        after = (builtins.open, os.stat, ast.parse, subprocess.Popen)
        self.assertEqual(before, after, "退出计数上下文后必须原样还原被补丁的入口")

    def test_empty_block_is_zero(self):
        with perf_counters.count() as c:
            pass
        self.assertTrue(all(c[k] == 0 for k in perf_counters.KEYS), dict(c))

    def test_keys_are_documented(self):
        self.assertEqual(set(perf_counters.KEYS), set(perf_counters.KEY_NOTES))


class RatchetTest(unittest.TestCase):
    """棘轮语义：任一工作集任一计数**上升**即 issue；持平/下降放过。"""

    BASE = {"schema": pc.SCHEMA, "workloads": {"w": {"open": 10, "stat": 5}}}

    def test_equal_passes(self):
        live = {"workloads": {"w": {"open": 10, "stat": 5}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / pc.BASELINE_REL).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / pc.BASELINE_REL).write_text(json.dumps(self.BASE), encoding="utf-8")
            self.assertEqual([], pc.check(tmp, live=live))

    def test_increase_fails(self):
        live = {"workloads": {"w": {"open": 11, "stat": 5}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / pc.BASELINE_REL).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / pc.BASELINE_REL).write_text(json.dumps(self.BASE), encoding="utf-8")
            issues = pc.check(tmp, live=live)
        self.assertTrue(any("结构计数上升" in i and "open" in i for i in issues), issues)

    def test_decrease_passes(self):
        live = {"workloads": {"w": {"open": 3, "stat": 1}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / pc.BASELINE_REL).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / pc.BASELINE_REL).write_text(json.dumps(self.BASE), encoding="utf-8")
            self.assertEqual([], pc.check(tmp, live=live))

    def test_missing_baseline_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues = pc.check(tmp, live={"workloads": {}})
        self.assertTrue(any("缺结构计数基线" in i for i in issues), issues)


class CommittedBaselineTest(unittest.TestCase):
    def test_baseline_is_present_and_shaped(self):
        doc = pc.load(str(ROOT))
        self.assertEqual(pc.SCHEMA, doc.get("schema"))
        loads = doc.get("workloads") or {}
        self.assertGreaterEqual(len(loads), 5, loads)
        for name, c in loads.items():
            self.assertEqual(set(perf_counters.KEYS), set(c), name)
