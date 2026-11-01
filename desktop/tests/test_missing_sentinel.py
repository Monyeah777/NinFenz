import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import missing_sentinel as M  # noqa: E402


class Test(unittest.TestCase):
    def test_missing_is_explicit(self):
        self.assertEqual((M.SENTINEL, True), M.parse_marked(""))
        self.assertEqual((M.SENTINEL, True), M.parse_marked(M.SENTINEL))

    def test_present_value(self):
        self.assertEqual(("模型A", False), M.parse_marked("模型A"))

    def test_reject_missing(self):
        self.assertEqual(1, len(M.reject_missing(["ok", M.SENTINEL])))
