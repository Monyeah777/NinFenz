import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import path_moved as P  # noqa: E402


class Test(unittest.TestCase):
    def test_resolve_chain(self):
        self.assertEqual("c", P.resolve({"a": "b", "b": "c"}, "a"))

    def test_dangling_and_duplicates(self):
        self.assertEqual(1, len(P.dangling({"a": "gone.md"}, ["here.md"])))
        self.assertEqual(1, len(P.duplicates({"a": "n", "b": "n"})))

    def test_cycle(self):
        self.assertTrue(P.cycles({"a": "b", "b": "a"}))
