import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import unknown_policy as U  # noqa: E402


class Test(unittest.TestCase):
    def test_resolve_fallback(self):
        s = {"id": "kind", "values": ["a"], "unknown_policy": "fallback", "fallback_value": "untyped"}
        self.assertEqual((False, "untyped", "fallback"), U.resolve(s, "zzz"))

    def test_validate(self):
        self.assertTrue(U.validate({"id": "k", "unknown_policy": "fallback"}))
        self.assertEqual([], U.validate({"id": "k", "values": [], "unknown_policy": "warn"}))
