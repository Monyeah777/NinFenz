import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import host_projection as H  # noqa: E402


class Test(unittest.TestCase):
    def test_parity_and_allowlist(self):
        self.assertEqual([], H.parity("A", {"claude": "A", "cursor": "A"}))
        self.assertEqual(1, len(H.parity("A", {"claude": "B"})))

    def test_placeholder_residue(self):
        self.assertTrue(any("占位符" in i for i in H.parity("A", {"claude": "{{X}}"})))

    def test_render_and_marker_guard(self):
        out = H.render("head<!--B-->old<!--E-->tail", "<!--B-->", "<!--E-->", "new")
        self.assertIn("new", out)
        with self.assertRaises(ValueError):
            H.render("no marker", "<!--B-->", "<!--E-->", "x")
