import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import strict_schema as S  # noqa: E402


class Test(unittest.TestCase):
    def test_unknown_key_path(self):
        issues = S.check({"a": 1, "b": {"c": 2, "d": 3}}, ["a", "b", "c"])
        self.assertEqual(1, len(issues))
        self.assertTrue(any("$.b.d" in i for i in issues))
        self.assertEqual(1, len(S.check({"zz": 1}, ["a"])))

    def test_clean(self):
        self.assertEqual([], S.check({"a": 1}, ["a"]))
