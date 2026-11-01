import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import yaml_recheck as Y  # noqa: E402


class Test(unittest.TestCase):
    def test_valid(self):
        r = Y.recheck("a: 1\n")
        self.assertTrue(r["ok"])
        self.assertEqual({"a": 1}, r["parsed"])

    def test_invalid_reports_line_and_fix(self):
        r = Y.recheck("a: [unclosed\n")
        self.assertFalse(r["ok"])
        self.assertIn("修复指引", r["error"])
