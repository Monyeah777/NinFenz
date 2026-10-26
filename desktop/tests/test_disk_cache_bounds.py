"""disk_cache 的全局容量边界（TDD）：按标签有界之外，总量也必须可裁。"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import disk_cache as dc  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._patch = mock.patch.object(dc, "root_dir", lambda: self.root)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(lambda: setattr(dc, "_STORE_TICKS", 0))
        self._env = {k: os.environ.get(k) for k in (dc.ENV_OFF, dc.ENV_MAX_TOTAL)}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _mk(self, tag, key, age=0.0):
        d = self.root / tag
        d.mkdir(parents=True, exist_ok=True)
        p = d / (key + ".json")
        p.write_text("{}", encoding="utf-8")
        if age:
            old = time.time() - age
            os.utime(p, (old, old))
        return p


class BoundsTest(_Base):
    def test_count_files_counts_two_levels(self):
        self._mk("t1", "a")
        self._mk("t1", "b")
        self._mk("t2", "c")
        self.assertEqual(dc.count_files(), 3)

    def test_enforce_bounds_keeps_newest(self):
        old = self._mk("t1", "old", age=1000)
        new = self._mk("t1", "new", age=1)
        removed = dc.enforce_bounds(limit=1)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_enforce_bounds_is_noop_under_cap(self):
        self._mk("t1", "a")
        self.assertEqual(dc.enforce_bounds(limit=10), 0)

    def test_max_total_env_override_and_fallback(self):
        os.environ[dc.ENV_MAX_TOTAL] = "5"
        self.assertEqual(dc.max_total(), 5)
        os.environ[dc.ENV_MAX_TOTAL] = "not-a-number"
        self.assertEqual(dc.max_total(), dc.MAX_TOTAL_DEFAULT)
        os.environ[dc.ENV_MAX_TOTAL] = "0"
        self.assertEqual(dc.max_total(), dc.MAX_TOTAL_DEFAULT)

    def test_store_returns_false_when_disabled(self):
        os.environ[dc.ENV_OFF] = "1"
        self.assertFalse(dc.store("t", "k", {"v": 1}))

    def test_store_returns_true_and_load_roundtrips(self):
        self.assertTrue(dc.store("t9", "k1", {"v": 1}))
        self.assertEqual(dc.load("t9", "k1"), {"v": 1})

    def test_load_tolerates_corrupt_file(self):
        p = self._mk("t2", "bad")
        p.write_text("{not json", encoding="utf-8")
        self.assertIsNone(dc.load("t2", "bad"))


if __name__ == "__main__":
    unittest.main()
