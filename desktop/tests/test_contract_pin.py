import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import contract_pin as C  # noqa: E402


class Test(unittest.TestCase):
    def test_pin_and_verify(self):
        obj = {"a": 1, "b": 2}
        p = C.pin(obj, ["a", "b"], 2)
        self.assertEqual([], C.verify(p, obj))

    def test_count_and_field_drift(self):
        p = C.pin({"a": 1}, ["a", "b"], 1)
        issues = C.verify(p, {"a": 1})
        self.assertTrue(any("缺字段 b" in i for i in issues))
        issues2 = C.verify(C.pin({"a": 1}, ["a"], 5), {"a": 1})
        self.assertTrue(any("条目数" in i for i in issues2))
