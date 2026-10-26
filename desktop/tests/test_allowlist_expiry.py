import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import allowlist_expiry as A  # noqa: E402


class Test(unittest.TestCase):
    def test_expired(self):
        self.assertEqual(1, len(A.expired([{"id": "x", "expires": "2026-01-01"}], "2026-10-11")))

    def test_unused(self):
        self.assertEqual(1, len(A.unused([{"id": "x"}, {"id": "y"}], ["x"])))

    def test_validate_requires_expires(self):
        self.assertTrue(any("expires" in i for i in A.validate([{"id": "x", "reason": "r"}])))
