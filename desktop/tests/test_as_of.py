import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import as_of as A  # noqa: E402


class Test(unittest.TestCase):
    def test_lookahead_detected(self):
        inputs = [{"id": "x", "known_at": "2026-01-01"}, {"id": "y", "known_at": "2026-12-01"}]
        self.assertEqual(["x"], A.usable_inputs(inputs, "2026-06-01"))
        self.assertEqual(1, len(A.check(inputs, "2026-06-01", ["x", "y"])))

    def test_no_lookahead(self):
        self.assertEqual([], A.check([{"id": "x", "known_at": "2026-01-01"}], "2026-06-01", ["x"]))
