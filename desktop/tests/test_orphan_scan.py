import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import orphan_scan as O  # noqa: E402


class Test(unittest.TestCase):
    def test_orphans_and_dangling(self):
        self.assertEqual(["b"], O.orphans(["a", "b"], {"a": ["x"]}))
        self.assertEqual(1, len(O.dangling({"s": ["GHOST"]}, ["a"])))
