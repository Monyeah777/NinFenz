"""严格 ISO-8601 解析判据（2026-10-23）。"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import iso8601  # noqa: E402


class Iso8601Test(unittest.TestCase):
    def test_strict_date(self):
        self.assertIsNotNone(iso8601.parse_date("2026-10-23"))
        self.assertIsNone(iso8601.parse_date("2026-1-2"))
        self.assertIsNone(iso8601.parse_date("2026-10-23T00:00:00Z"))

    def test_instant_normalization(self):
        self.assertEqual(datetime(2026, 10, 23, tzinfo=timezone.utc),
                         iso8601.parse_instant("2026-10-23"))
        self.assertEqual(datetime(2026, 10, 23, tzinfo=timezone.utc),
                         iso8601.parse_instant("2026-10-23T08:00:00+08:00"))
        self.assertEqual(datetime(2026, 10, 23, tzinfo=timezone.utc),
                         iso8601.parse_instant("2026-10-23T00:00:00Z"))
        self.assertEqual(datetime(2026, 10, 23, tzinfo=timezone.utc),
                         iso8601.parse_instant("2026-10-23T00:00:00"))

    def test_invalid(self):
        for bad in (None, "", "x", "2026-13-01", "2026-10-23T25:00:00Z"):
            self.assertIsNone(iso8601.parse_instant(bad))
            self.assertFalse(iso8601.is_iso_instant(bad))


if __name__ == "__main__":
    unittest.main()
