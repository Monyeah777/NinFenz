import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import eval_harness as E  # noqa: E402


class Test(unittest.TestCase):
    def test_digest_and_record_validation(self):
        self.assertEqual(E.case_digest({"a": 1}), E.case_digest({"a": 1}))
        rec = E.record("c1", True, 3.0, "2026-10-11T00:00:00Z", "author-explicit")
        self.assertEqual([], E.validate(rec))

    def test_bad_trigger(self):
        self.assertTrue(any("trigger" in i for i in E.validate(
            {"case_id": "c", "ok": True, "cost_usd": 0, "at": "x", "trigger": "random"})))
