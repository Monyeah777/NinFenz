#!/usr/bin/env python3
"""gate_select 判据：合成读面逐条钉住选择规则与可缓存性闸门。

为什么用合成面：真仓读面是**环境相关缓存**（不入库），判据不能依赖它；
而选择逻辑的每条规则都必须有独立判据，否则「多跑」的保证无从证明。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_select as gs  # noqa: E402


def _faces(tmp, modules):
    p = Path(tmp) / "faces.json"
    p.write_text(json.dumps({"schema": gs.SCHEMA, "modules": modules}),
                 encoding="utf-8", newline="\n")
    return p


def _tests_dir(tmp):
    d = Path(tmp) / "tests"
    d.mkdir(exist_ok=True)
    (d / "test_plain.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
    (d / "test_spawn_ok.py").write_text("import subprocess\n", encoding="utf-8", newline="\n")
    (d / "test_spawn_bad.py").write_text("import subprocess\n", encoding="utf-8", newline="\n")
    (d / "test_native.py").write_text('CMD = ["ruff"]\nimport subprocess\n',
                                      encoding="utf-8", newline="\n")
    return d


def _doc():
    return {
        "test_plain": {"status": "ok", "reads": ["src/x.py"], "seconds": 1},
        "test_spawn_ok": {"status": "ok", "reads": ["src/y.py"], "seconds": 1,
                         "child_reads_captured": 5},
        "test_spawn_bad": {"status": "ok", "reads": ["src/z.py"], "seconds": 1},
        "test_native": {"status": "ok", "reads": ["src/v.py"], "seconds": 1,
                        "child_reads_captured": 9},
        "test_red": {"status": "tests_failed", "reads": ["src/w.py"], "seconds": 1},
    }


class SelectTest(unittest.TestCase):
    """五条规则 + 车道 + 可缓存性。"""

    def _select(self, changed, tmp):
        return gs.select(changed, doc=_doc(), tests_dir=_tests_dir(tmp), root=tmp)

    def test_read_hit_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = {m for m, _w in self._select(["src/x.py"], tmp)["run"]}
            self.assertIn("test_plain", run)

    def test_captured_child_face_can_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = self._select(["src/x.py"], tmp)
            self.assertIn("test_spawn_ok", got["skip"])

    def test_unobservable_child_always_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = {m for m, _w in self._select(["src/x.py"], tmp)["run"]}
            self.assertIn("test_spawn_bad", run)

    def test_native_tool_always_runs_even_with_captured_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = {m for m, _w in self._select(["src/x.py"], tmp)["run"]}
            self.assertIn("test_native", run)

    def test_red_observation_always_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = {m for m, _w in self._select(["src/x.py"], tmp)["run"]}
            self.assertIn("test_red", run)

    def test_module_changed_runs_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = {m for m, _w in self._select(["desktop/tests/test_plain.py"], tmp)["run"]}
            self.assertIn("test_plain", run)

    def test_no_hit_no_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            got = self._select(["src/nothing.py"], tmp)
            run = {m for m, _w in got["run"]}
            self.assertNotIn("test_plain", run)

    def test_unobserved_module_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _tests_dir(tmp)
            (d / "test_extra.py").write_text("x = 1\n", encoding="utf-8", newline="\n")
            got = gs.select(["src/x.py"], doc=_doc(), tests_dir=d, root=tmp)
            self.assertIn("test_extra", {m for m, _w in got["run"]})

    def test_cacheable_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _tests_dir(tmp)
            doc = _doc()
            self.assertTrue(gs.cacheable("test_plain", doc["test_plain"], tdir))
            self.assertTrue(gs.cacheable("test_spawn_ok", doc["test_spawn_ok"], tdir))
            for mod in ("test_spawn_bad", "test_native", "test_red"):
                self.assertFalse(gs.cacheable(mod, doc[mod], tdir), mod)

    def test_lane_threshold(self):
        """阈值只对「成本可信」（status ok）的记录生效；缺 status 一律保守让位。"""
        self.assertEqual(gs.lane_of({"status": "ok", "seconds": gs.SLOW_SECONDS - 1}), "quick")
        self.assertEqual(gs.lane_of({"status": "ok", "seconds": gs.SLOW_SECONDS}), "slow")
        self.assertEqual(gs.lane_of({"seconds": 1}), "slow")

    def test_unknown_cost_goes_to_slow_lane(self):
        """成本说不清（观测非 ok）必须让位：实测有 observe_error 记 0s、真跑 137s 的模块。"""
        self.assertEqual(gs.lane_of({"status": "observe_error", "seconds": 0}), "slow")
        self.assertEqual(gs.lane_of({"status": "timeout", "seconds": 0}), "slow")
        self.assertEqual(gs.lane_of({"status": "tests_failed", "seconds": 1}), "slow")
        self.assertEqual(gs.lane_of({"status": "ok", "seconds": 1}), "quick")


class FailClosedDataTest(unittest.TestCase):
    """读面数据不可信时**不崩、不跳**：全部当未观测（一律常跑）。"""

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gs.load_faces(tmp, Path(tmp) / "nope.json"), {})

    def test_bad_schema_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.json"
            p.write_text(json.dumps({"schema": "other/9", "modules": {}}),
                         encoding="utf-8", newline="\n")
            self.assertEqual(gs.load_faces(tmp, p), {})

    def test_corrupt_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "f.json"
            p.write_text("{ not json", encoding="utf-8", newline="\n")
            self.assertEqual(gs.load_faces(tmp, p), {})

    def test_empty_faces_runs_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _tests_dir(tmp)
            got = gs.select(["src/x.py"], doc={}, tests_dir=d, root=tmp)
            self.assertEqual(len(got["skip"]), 0)
            self.assertGreaterEqual(len(got["run"]), 4)


class FilterTest(unittest.TestCase):
    """归一化：私有面/字节码不进读面，仓外路径丢弃。"""

    def test_filters_private_and_bytecode(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = _faces(tmp, {"test_plain": {
                "status": "ok", "seconds": 1,
                "reads": [str(Path(tmp) / ".rivet" / "x.json"),
                          str(Path(tmp) / "a.pyc"), str(Path(tmp) / "src" / "x.py"),
                          "C:/outside/y.py"]}})
            got = gs.load_faces(tmp, p)
            self.assertEqual(got["test_plain"]["reads"], ["src/x.py"])


if __name__ == "__main__":
    unittest.main()
