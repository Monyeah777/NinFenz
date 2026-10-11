# -*- coding: utf-8 -*-
"""core.gate_graph 回归：导入图反向闭包 + 变更→专家，含变异自证。"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import gate_graph as gg  # noqa: E402


def _mk_core(tmp, name, body):
    p = Path(tmp) / "desktop" / "src" / "core" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


class ClosureTest(unittest.TestCase):
    def test_chain_closure_and_rdeps(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk_core(tmp, "a.py", "X = 1\n")
            _mk_core(tmp, "b.py", "from core import a\n")
            _mk_core(tmp, "c.py", "from core import b\n")
            dm = gg.module_deps(tmp)
            self.assertEqual({"b"}, gg.rdeps(dm, "a"))
            self.assertEqual({"a", "b", "c"}, gg.closure(dm, ["a"]))
            self.assertEqual({"b", "c"}, gg.closure(dm, ["b"]))

    def test_changed_modules_only_accepts_core_paths(self):
        self.assertEqual({"a"}, gg.changed_modules(["desktop/src/core/a.py"]))
        self.assertEqual({"a"}, gg.changed_modules(["desktop" + chr(92) + "src" + chr(92) + "core" + chr(92) + "a.py"]))
        self.assertEqual(set(), gg.changed_modules(["docs/x.md", "scripts/nf.py"]))


class AffectedExpertsTest(unittest.TestCase):
    def _decl(self):
        return {"e_a": {"id": "e_a", "module": "desktop/src/core/a.py", "reads": []},
                "e_x": {"id": "e_x", "module": "desktop/src/core/x.py", "reads": ["docs"]}}

    def test_closure_marks_dependents(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk_core(tmp, "a.py", "X = 1\n")
            _mk_core(tmp, "b.py", "from core import a\n")
            decl = self._decl()
            decl["e_b"] = {"id": "e_b", "module": "desktop/src/core/b.py", "reads": []}
            got = gg.affected_experts(tmp, ["desktop/src/core/a.py"], experts=decl)
            self.assertEqual("依赖闭包", got.get("e_b"))
            self.assertEqual("依赖闭包", got.get("e_a"))

    def test_read_face_hit_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk_core(tmp, "a.py", "X = 1\n")
            got = gg.affected_experts(tmp, ["docs/x.md"], experts=self._decl())
            self.assertEqual("读面命中", got.get("e_x"))
            self.assertNotIn("e_a", got)

    def test_no_change_affects_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            _mk_core(tmp, "a.py", "X = 1\n")
            self.assertEqual({}, gg.affected_experts(tmp, [], experts=self._decl()))


if __name__ == "__main__":
    unittest.main()
