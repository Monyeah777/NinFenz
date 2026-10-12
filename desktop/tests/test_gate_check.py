#!/usr/bin/env python3
"""gate_check 判据：计划期定键 / 并行执行 / 红的缓存不洗绿 / 不可缓存常跑 / 慢车道让位。

执行动作是**注入**的（fake invoker）⇒ 判据不 spawn、确定、快；
另有 1 例用真 subprocess 跑合成包，证明真路径也可用。
"""
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_check as gck  # noqa: E402
from core import gate_select as gs  # noqa: E402


def _make(tmp, names, native=()):
    """合成 tests 目录 + 对应的 faces 文档（节点名唯一，避免跨用例串缓存）。"""
    tdir = Path(tmp) / "tests"
    tdir.mkdir(parents=True, exist_ok=True)
    uniq = uuid.uuid4().hex[:8]
    faces = {}
    for name in names:
        mod = f"test_{name}_{uniq}"
        body = "x = 1\n"
        if name in native:
            body = 'CMD = ["ruff"]\nimport subprocess\n'
        (tdir / f"{mod}.py").write_text(body, encoding="utf-8", newline="\n")
        faces[mod] = {"status": "ok", "reads": ["src/x.py"], "seconds": 1}
    return tdir, faces


class PlanExecuteTest(unittest.TestCase):
    """编排：命中即不跑；红的缓存仍是红；不可缓存每次真跑；慢车道让位。"""

    def test_first_run_then_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["aaa", "bbb"])
            calls = []

            def invoke(mod, timeout):
                calls.append(mod)
                return 0, 0.01

            r1 = gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            self.assertEqual(len(r1["fresh"]), 2)
            self.assertEqual(r1["failed"], [])
            r2 = gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            self.assertEqual(r2["fresh"], [], "第二次应全命中")
            self.assertEqual(len(calls), 2)

    def test_failed_verdict_stays_failed_from_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["red"])
            mod = next(iter(faces))

            def invoke(_mod, _timeout):
                return 1, 0.01

            r1 = gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            r2 = gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            self.assertEqual(r1["failed"], [mod])
            self.assertEqual(r2["failed"], [mod], "缓存的红必须仍是红")
            self.assertEqual(r2["fresh"], [])

    def test_uncacheable_always_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["native"], native=("native",))
            calls = []

            def invoke(mod, _timeout):
                calls.append(mod)
                return 0, 0.01

            gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            self.assertEqual(len(calls), 2, "原生工具节点不得走缓存")

    def test_slow_lane_is_deferred_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["slow", "fast"])
            slow = [m for m in faces if "slow" in m][0]
            faces[slow]["seconds"] = gs.SLOW_SECONDS + 1
            calls = []

            def invoke(mod, _timeout):
                calls.append(mod)
                return 0, 0.01

            res = gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir)
            self.assertIn(slow, res["deferred"])
            self.assertNotIn(slow, calls, "慢车道只让位，不执行——但名单要打印")

    def test_no_cache_mode_runs_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["aaa"])
            calls = []

            def invoke(_mod, _timeout):
                calls.append(1)
                return 0, 0.01

            gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir,
                      use_cache=False)
            gck.check(["src/x.py"], invoke, root=tmp, faces=faces, tests_dir=tdir,
                      use_cache=False)
            self.assertEqual(len(calls), 2)


class RealInvokerTest(unittest.TestCase):
    """真路径：用 subprocess 跑合成包，红/绿都要如实。"""

    def _invoke(self, desktop):
        def invoke(mod, timeout):
            proc = subprocess.run([sys.executable, "-m", "unittest", f"tests.{mod}", "-q"],
                                  cwd=str(desktop), capture_output=True, timeout=timeout)
            return proc.returncode, 0.0

        return invoke

    def test_real_subprocess_green_and_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir, faces = _make(tmp, ["green", "red"])
            red = [m for m in faces if "red" in m][0]
            for mod in list(faces):
                if mod == red:
                    (tdir / f"{mod}.py").write_text(
                        "import unittest\n\n\nclass T(unittest.TestCase):\n"
                        "    def test_red(self):\n        self.assertTrue(False)\n",
                        encoding="utf-8", newline="\n")
            res = gck.check(["src/x.py"], self._invoke(Path(tmp)), root=tmp, faces=faces,
                            tests_dir=tdir, timeout=120)
            self.assertEqual(res["failed"], [red])


if __name__ == "__main__":
    unittest.main()
