"""dep_closure 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import dep_closure as D  # noqa: E402


class Test(unittest.TestCase):
    def test_transitive_closure(self):
        self.assertEqual({"b", "c"}, D.closure({"a": ["b"], "b": ["c"]}, ["a"]))

    def test_offender_is_transitive(self):
        bad = D.offenders({"a": ["b"], "b": ["thirdparty"]}, ["a"], ["b"])
        self.assertEqual([("thirdparty", "a → b → thirdparty")], bad)

    def test_allowed_closure_is_clean(self):
        self.assertEqual([], D.offenders({"a": ["b"], "b": ["c"]}, ["a"], ["b", "c"]))
