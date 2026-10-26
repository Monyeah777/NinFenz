import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import output_envelope as O  # noqa: E402


class Test(unittest.TestCase):
    def test_no_truncation(self):
        e = O.envelope("abc", 10)
        self.assertFalse(e["truncated"])
        self.assertEqual([], O.validate(e))

    def test_truncation_requires_pointer(self):
        e = O.envelope("abcdef", 3)
        self.assertTrue(e["truncated"])
        self.assertEqual(1, len(O.validate(e)))
        self.assertEqual([], O.validate(O.envelope("abcdef", 3, "full.txt")))
