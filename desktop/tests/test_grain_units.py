import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import grain_units as G  # noqa: E402


class Test(unittest.TestCase):
    def test_required_fields(self):
        self.assertEqual(2, len(G.validate([{"name": "s1"}])))

    def test_ok_and_clock_vocab(self):
        self.assertEqual([], G.validate([{"name": "s1", "grain": "一天一行", "unit": "度"}]))
        self.assertTrue(any("clock" in i for i in G.validate(
            [{"name": "s1", "grain": "g", "unit": "u", "clock": "wall"}])))
