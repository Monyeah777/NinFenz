import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import boundaries as B  # noqa: E402


class Test(unittest.TestCase):
    def test_missing_files_reported(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "code.py").write_text("x", encoding="utf-8")
            issues = B.validate([{"id": "b1", "code": "code.py", "doc": "doc.md"}], d)
            self.assertEqual(1, len(issues))
            self.assertIn("doc", issues[0])

    def test_both_present_ok(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "code.py").write_text("x", encoding="utf-8")
            Path(d, "doc.md").write_text("y", encoding="utf-8")
            self.assertEqual([], B.validate([{"id": "b1", "code": "code.py", "doc": "doc.md"}], d))
