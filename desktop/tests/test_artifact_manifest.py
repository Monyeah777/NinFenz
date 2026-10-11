import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import artifact_manifest as A  # noqa: E402


class Test(unittest.TestCase):
    def test_build_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.txt").write_text("hi", encoding="utf-8")
            m = A.build(d, ["a.txt"], "gen", "覆盖 a.txt；不覆盖 b")
            self.assertEqual([], A.verify(m, d))
            Path(d, "a.txt").write_text("changed", encoding="utf-8")
            self.assertTrue(any("漂移" in i for i in A.verify(m, d)))

    def test_coverage_required(self):
        with self.assertRaises(ValueError):
            A.build(".", [], "gen", "  ")
