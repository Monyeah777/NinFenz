import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import residual_registry as R  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_match(self):
        e = [{"id": "r1", "pattern": "rm -rf", "reason": "用户显式", "impact": "误报"}]
        self.assertEqual([], R.validate(e))
        self.assertEqual(1, len(R.accepted(e, "run rm -rf /x")))
        self.assertEqual([], R.accepted(e, "ls"))

    def test_missing_fields(self):
        self.assertEqual(4, len(R.validate([{}])))
