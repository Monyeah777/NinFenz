#!/usr/bin/env python3
"""运行时形状契约（2026-10-10 全仓审计 N 系列：N2/N3/N5/N6/N7/N10）。

集中成一件的理由：这批修的是**同一个病**——「不可信/畸形输入被静默收下，读成合法结果」。
判据落在 core 层纯函数上（快、确定性）；N2 走一次真 CLI（rc 语义）。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import knowledge as kn  # noqa: E402
from core import registry_loader as rl  # noqa: E402
from core import telemetry_semconv as ts  # noqa: E402
from core import trace_drill as td  # noqa: E402


def _tmp_text(test, text, prefix):
    fd, p = tempfile.mkstemp(prefix=prefix, suffix=".json")
    os.close(fd)
    test.addCleanup(os.unlink, p)
    Path(p).write_text(text, encoding="utf-8")
    return p


class KnowledgeTraceShapeTest(unittest.TestCase):
    """N5：顶层非对象/对象数组、NaN、混标量都必须报错（不再读成「0 源有事件」）。"""

    def test_rejects_non_object_toplevel(self):
        for text in ('"hello"', "42"):
            with self.assertRaises(ValueError):
                kn.harvest_frequency(_tmp_text(self, text, "nf_trace_n5_"))

    def test_rejects_scalar_array(self):
        with self.assertRaises(ValueError):
            kn.harvest_frequency(_tmp_text(self, "[1, 2, 3]", "nf_trace_n5_"))

    def test_rejects_nan(self):
        with self.assertRaises(ValueError):
            kn.harvest_frequency(_tmp_text(self, '{"x": NaN}', "nf_trace_n5_"))

    def test_valid_forms_still_pass(self):
        got = kn.harvest_frequency(
            _tmp_text(self, '[{"knowledge_source": "s1"}]', "nf_trace_n5_"))
        self.assertEqual({"s1": 1}, got)
        self.assertEqual({}, kn.harvest_frequency(_tmp_text(self, "", "nf_trace_n5_")))


class BomToleranceTest(unittest.TestCase):
    """N4：带 BOM 的外来 JSON 必须被正常解析（不再把编码问题误报成「不是 JSON」）。"""

    def test_bom_json_is_accepted_by_external_readers(self):
        raw = b"\xef\xbb\xbf" + b'[{"knowledge_source": "s1"}]'
        fd, p = tempfile.mkstemp(prefix="nf_bom_n4_", suffix=".json")
        os.close(fd)
        self.addCleanup(os.unlink, p)
        Path(p).write_bytes(raw)
        self.assertEqual({"s1": 1}, kn.harvest_frequency(p))
        self.assertEqual(1, len(ts.load_trace(p)))

    def test_registry_loader_tolerates_bom(self):
        """定向 BOM 容错：registry JSON 解析入口去 BOM（通用读口与摘要口径**保持不变**）。

        2026-10-10 审计 N4 的修正：通用文本层（conformance_scan / atomic_write）**不能**默认
        utf-8-sig——那会改变带 BOM 件的内容摘要；BOM 容错只落在解析入口。
        """
        raw = b"\xef\xbb\xbf" + json.dumps(
            {"registry_schema_version": "2", "modules": [], "protocols": []}).encode("utf-8")
        fd, p = tempfile.mkstemp(prefix="nf_bom_reg_", suffix=".json")
        os.close(fd)
        self.addCleanup(os.unlink, p)
        Path(p).write_bytes(raw)
        rl.load_registry.cache_clear()
        reg = rl.load_registry(p)
        self.assertEqual([], list(reg.modules))


class RegistryShapeTest(unittest.TestCase):
    """N6：registry.json 顶层非对象 → 带指引的 ValueError（不再 AttributeError 裸崩）。"""

    def test_non_object_shapes_raise_with_guide(self):
        for text in ("[1,2,3]", '"hello"', "42", "null"):
            p = _tmp_text(self, text, "nf_reg_n6_")
            with self.assertRaises(ValueError) as ctx:
                rl.load_registry.cache_clear()
                rl.load_registry(p)
            self.assertIn("修复指引", str(ctx.exception))


class TelemetryShapeTest(unittest.TestCase):
    """N10：{} 不得产出伪造 span；NaN 不得被收下；与 knowledge 拒同一批形状。"""

    def test_empty_object_record_is_refused(self):
        with self.assertRaises(ValueError):
            ts.load_trace(_tmp_text(self, "{}", "nf_tel_n10_"))

    def test_nan_is_refused(self):
        with self.assertRaises(ValueError):
            ts.load_trace(_tmp_text(self, '{"x": NaN}', "nf_tel_n10_"))

    def test_scalar_array_is_refused(self):
        with self.assertRaises(ValueError):
            ts.load_trace(_tmp_text(self, "[1,2,3]", "nf_tel_n10_"))

    def test_valid_record_passes(self):
        self.assertEqual(1, len(ts.load_trace(_tmp_text(self, '{"name": "nf doctor"}',
                                                        "nf_tel_n10_"))))

    def test_two_modules_reject_the_same_shapes(self):
        """同一批形状两处同判（跨实现夹具；刻意不为此加模块间边）。"""
        for text in ('"hello"', "42", "[1,2,3]", '{"x": NaN}'):
            p = _tmp_text(self, text, "nf_shape_dual_")
            with self.assertRaises(ValueError):
                kn.harvest_frequency(p)
            with self.assertRaises(ValueError):
                ts.load_trace(p)


class TraceDrillShapeTest(unittest.TestCase):
    """N3：--check-trace 对非对象 trace 必须走带指引分支（不冒内部错误）。"""

    def test_non_dict_trace_is_diagnosed(self):
        issues, stats = td.analyze(_tmp_text(self, "[1,2,3]", "nf_td_n3_"), str(ROOT))
        self.assertTrue(issues)
        self.assertIn("不是 JSON 对象", issues[0])
        self.assertEqual({}, stats)

    def test_missing_source_is_diagnosed(self):
        issues, _ = td.analyze(_tmp_text(self, '{"tool": "nf assemble"}', "nf_td_n3_"),
                               str(ROOT))
        self.assertTrue(any("缺 source" in i for i in issues))


class DiskCacheStoreObservabilityTest(unittest.TestCase):
    """N7：写失败不再全吞——计数 + 最近原因可观测。"""

    def test_store_failure_is_counted(self):
        from core import disk_cache as dc
        from core import atomic_write as aw
        if not dc.enabled():
            self.skipTest("本环境磁盘缓存被显式关闭")
        orig = aw.write_text
        before = dc.STORE_FAILURES

        def boom(*_a, **_k):
            raise OSError("injected write failure")

        aw.write_text = boom
        try:
            dc.store("nf_test_n7", "key", {"v": 1})
        finally:
            aw.write_text = orig
        self.assertEqual(before + 1, dc.STORE_FAILURES)
        self.assertIn("nf_test_n7", dc.LAST_STORE_ERROR)


class WatcherOwnershipTest(unittest.TestCase):
    """N8：监听件必须只有一个写入口（daemon.set_watcher），不许跨模块直写。

    跨模块可变全局没有所有权时，改动无处可查、换手也不原子——本判据是「唯一持有者断言」。
    """

    def test_only_daemon_assigns_watcher_global(self):
        import re
        offenders = []
        for rel in ("desktop/src/core", "scripts", "tui", ".github/scripts",
                    "desktop/tests"):
            for p in (ROOT / rel).rglob("*.py"):
                if p.name == "daemon.py":
                    continue
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                for i, line in enumerate(lines, 1):
                    # 只拦**跨模块**写：daemon._WATCHER / dm._WATCHER
                    # （各模块自己的私有 _WATCHER 不在本判据范围）。
                    if re.search(r"\b(?:daemon|dm)\._WATCHER\s*=", line):
                        offenders.append("%s:%d %s"
                                         % (p.relative_to(ROOT).as_posix(), i, line.strip()))
        self.assertEqual([], offenders, "监听件被 daemon 之外直写：%s" % offenders)


class AssembleTraceWriteRcTest(unittest.TestCase):
    """N2：--trace 写失败必须让 rc≠0（此前返回值被丢弃 ⇒ 静默失败却报成功）。"""

    def test_unwritable_trace_path_fails_the_command(self):
        bad = str(ROOT / "README.md" / "trace.json")      # 落点「文件之下」⇒ 必然 OSError
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"), "assemble",
                            "西幻生存", "--trace", bad],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180)
        self.assertNotEqual(0, p.returncode, "写 trace 失败仍返回 0（静默失败却报成功）")
        self.assertIn("写 trace 失败", p.stderr)


if __name__ == "__main__":
    unittest.main()
