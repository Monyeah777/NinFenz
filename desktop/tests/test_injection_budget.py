"""injection_budget 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import injection_budget as B  # noqa: E402

P = {"max_items": 3, "token_budget": 10, "priority_order": ["contract", "asset"], "exclude_types": ["secret"]}


class Test(unittest.TestCase):
    def test_validate_ok(self):
        self.assertEqual([], B.validate(P))

    def test_selection_is_deterministic_and_accounted(self):
        items = [{"name": "a", "type": "asset", "tokens": 4},
                 {"name": "b", "type": "contract", "tokens": 5},
                 {"name": "c", "type": "secret", "tokens": 1},
                 {"name": "d", "type": "asset", "tokens": 9}]
        keep, drop = B.select(P, items)
        self.assertEqual(["b", "a"], [x["name"] for x in keep])
        self.assertEqual({"c", "d"}, {x["name"] for x in drop})
        self.assertTrue(all("reason" in x for x in drop))
