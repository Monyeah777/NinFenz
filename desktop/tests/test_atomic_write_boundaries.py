"""原子写的防御性边界（TDD）：只测边界与失败语义，不改既有判据。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import atomic_write as aw  # noqa: E402


class TargetGuardTest(unittest.TestCase):
    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):
            aw.write_text("", "x")
        with self.assertRaises(ValueError):
            aw.write_text("   ", "x")

    def test_directory_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(IsADirectoryError):
                aw.write_text(tmp, "x")
            with self.assertRaises(IsADirectoryError):
                aw.write_bytes(tmp, b"x")


class WriteSemanticsTest(unittest.TestCase):
    def test_lf_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "a.txt")
            aw.write_text(p, "a\r\nb\rc\n")
            self.assertEqual(p.read_bytes(), b"a\nb\nc\n")

    def test_no_temp_leftovers_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "a.json")
            aw.write_text(p, "{}")
            self.assertEqual(sorted(x.name for x in Path(tmp).iterdir()), ["a.json"])

    def test_failed_replace_keeps_old_content_and_no_leftovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "a.json")
            aw.write_text(p, "old")
            with (mock.patch.object(aw, "_replace", side_effect=PermissionError("busy")),
                  self.assertRaises(PermissionError)):
                aw.write_text(p, "new")
            self.assertEqual(p.read_text(encoding="utf-8"), "old")
            self.assertEqual(sorted(x.name for x in Path(tmp).iterdir()), ["a.json"])

    def test_bytes_writer_is_atomic_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "a.bin")
            aw.write_bytes(p, b"\x00\x01")
            self.assertEqual(p.read_bytes(), b"\x00\x01")


if __name__ == "__main__":
    unittest.main()
