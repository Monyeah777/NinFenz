#!/usr/bin/env python3
"""gate_observe 判据：读面观测的端到端行为（含子进程读面与失败分类）。

用合成包（tmp/desktop/tests/…）跑真子进程，因此这些判据证明的是**真行为**，不是桩。
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_observe as go  # noqa: E402
from core import gate_select as gs  # noqa: E402

_READ_PROBE = """
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
(ROOT / "src" / "data.txt").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "desktop"))
"""

_CHILD_PROBE = """
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
code = "open(r'%s', encoding='utf-8').read()" % (ROOT / "src" / "child.txt")
subprocess.run([sys.executable, "-c", code], check=True)
"""

_RED_PROBE = """
import unittest


class T(unittest.TestCase):
    def test_red(self):
        self.assertTrue(False)
"""

_SLEEP_PROBE = """
import time
import unittest


class T(unittest.TestCase):
    def test_slow(self):
        time.sleep(6)
"""


def _make_pkg(tmp):
    root = Path(tmp)
    (root / "desktop" / "tests").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "src" / "data.txt").write_text("d", encoding="utf-8", newline="\n")
    (root / "src" / "child.txt").write_text("c", encoding="utf-8", newline="\n")
    (root / "desktop" / "tests" / "test_probe.py").write_text(_READ_PROBE,
                                                              encoding="utf-8", newline="\n")
    (root / "desktop" / "tests" / "test_probe_child.py").write_text(_CHILD_PROBE,
                                                                    encoding="utf-8", newline="\n")
    (root / "desktop" / "tests" / "test_probe_sleep.py").write_text(_SLEEP_PROBE,
                                                                  encoding="utf-8", newline="\n")
    (root / "desktop" / "tests" / "test_probe_red.py").write_text(_RED_PROBE,
                                                                  encoding="utf-8", newline="\n")
    return root


class ObserveOneTest(unittest.TestCase):
    """真子进程观测：读面、子进程读面、失败分类。"""

    def test_in_process_read_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            rec = go.observe_one("test_probe", root=str(root), capture_children=False)
            self.assertEqual(rec["status"], "ok", rec)
            self.assertIn("src/data.txt", rec["reads"])

    def test_child_process_read_is_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            rec = go.observe_one("test_probe_child", root=str(root))
            self.assertEqual(rec["status"], "ok", rec)
            self.assertIn("src/child.txt", rec["reads"])
            self.assertGreater(rec["child_reads_captured"], 0)

    def test_red_module_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            rec = go.observe_one("test_probe_red", root=str(root), capture_children=False)
            self.assertEqual(rec["status"], "tests_failed", rec)

    def test_timeout_is_enforced_and_says_so(self):
        """超时必须在场上生效并如实记 timeout（此前 timeout 参数根本没传到子进程）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            rec = go.observe_one("test_probe_sleep", root=str(root), timeout=1,
                                 capture_children=False)
            self.assertEqual(rec["status"], "timeout", rec)

    def test_missing_module_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            rec = go.observe_one("test_nope", root=str(root), capture_children=False)
            self.assertNotEqual(rec["status"], "ok", rec)


class DocTest(unittest.TestCase):
    """数据落盘/读回与 gate_select 的 schema 兼容（单一 schema 出处）。"""

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "faces.json"
            doc = {"schema": gs.SCHEMA, "modules": {"m": {"status": "ok", "reads": ["a.py"],
                                                    "seconds": 1}}}
            go.save_doc(doc, p)
            self.assertEqual(go.load_doc(p)["modules"]["m"]["reads"], ["a.py"])
            self.assertEqual(gs.load_faces(tmp, p)["m"]["reads"], ["a.py"])

    def test_bad_schema_loads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "faces.json"
            p.write_text('{"schema": "nope/1", "modules": {}}', encoding="utf-8", newline="\n")
            self.assertEqual(go.load_doc(p)["modules"], {})

    def test_run_all_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _make_pkg(tmp)
            p = Path(tmp) / "faces.json"
            first = go.run_all(str(root), mods=["test_probe"], workers=2, path=p)
            self.assertIn("test_probe", first["modules"])
            again = go.run_all(str(root), mods=["test_probe"], workers=2, path=p)
            self.assertEqual(again["modules"]["test_probe"]["status"], "ok")


class NormalizeTest(unittest.TestCase):
    """归一化：仓外丢弃、私有面/字节码丢弃、相对与绝对等价。"""

    def test_filters(self):
        got = go.normalize_reads(".", ["desktop/src/core/gate_select.py", "C:/outside/x.py",
                                       "desktop/x.pyc", ".rivet/private_archive/a.json"])
        self.assertEqual(got, ["desktop/src/core/gate_select.py"])


if __name__ == "__main__":
    unittest.main()
