import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import since_tags as T  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_covers(self):
        e = [{"id": "c1", "since": "2.10.0"}, {"id": "c2", "since": "2.12.0"}]
        self.assertEqual([], T.validate(e))
        self.assertEqual(["c1"], T.covers(e, "2.11.0"))

    def test_missing_and_bad(self):
        self.assertEqual(1, len(T.validate([{"id": "c1"}])))
        self.assertEqual(1, len(T.validate([{"id": "c1", "since": "v2"}])))
