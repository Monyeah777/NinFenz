import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import feature_lifecycle as F  # noqa: E402


class Test(unittest.TestCase):
    def test_short_window_is_fail(self):
        e = [{"name": "old-api", "state": "removed", "deprecated_at": "2026-09-01"}]
        self.assertTrue(any("弃用窗不足" in i for i in F.check(e, "2026-10-01")))

    def test_full_window_ok(self):
        e = [{"name": "old-api", "state": "removed", "deprecated_at": "2025-01-01"}]
        self.assertEqual([], F.check(e, "2026-10-01"))

    def test_breaking_requires_new_identifier(self):
        e = [{"name": "x", "state": "active", "breaking": True}]
        self.assertTrue(any("新标识符" in i for i in F.check(e, "2026-10-01")))
