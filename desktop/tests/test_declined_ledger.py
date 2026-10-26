import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import declined_ledger as D  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_query(self):
        e = [{"candidate": "repo/x", "reason": "不适面", "date": "2026-10-11"}]
        self.assertEqual([], D.validate(e))
        self.assertTrue(D.is_declined(e, "repo/x"))

    def test_missing_reason(self):
        self.assertEqual(1, len(D.validate([{"candidate": "x", "date": "2026-10-11"}])))
