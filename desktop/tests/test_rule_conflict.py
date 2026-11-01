import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import rule_conflict as R  # noqa: E402


class Test(unittest.TestCase):
    def test_same_rank_same_match_conflicts(self):
        rules = [{"id": "a", "rank": 1, "match": "x"}, {"id": "b", "rank": 1, "match": "x"}]
        self.assertEqual([("a", "b")], R.conflicts(rules))

    def test_order_is_declaration_independent(self):
        rules = [{"id": "b", "rank": 2, "match": "y"}, {"id": "a", "rank": 1, "match": "x"}]
        self.assertEqual(["a", "b"], R.stable_order(rules))
        self.assertEqual(["a", "b"], R.stable_order(list(reversed(rules))))
