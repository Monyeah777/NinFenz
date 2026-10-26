import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import dirty_tree as D  # noqa: E402


class Test(unittest.TestCase):
    def test_validate(self):
        self.assertEqual([], D.validate(D.describe("abc123", [])))
        self.assertEqual([], D.validate(D.describe("abc123", ["x"])))
        self.assertEqual(1, len(D.validate({"head": "abc", "dirty": True})))

    def test_missing_head(self):
        self.assertTrue(any("head" in i for i in D.validate({"dirty": False})))
