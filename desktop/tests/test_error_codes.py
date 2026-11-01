import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import error_codes as E  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_lookup(self):
        reg = {"codes": [{"id": "NF_NO_MODULE", "message": "缺模块", "fix": "补模块"}]}
        self.assertEqual([], E.validate(reg))
        self.assertEqual(("缺模块", "补模块"), E.lookup(reg, "NF_NO_MODULE"))

    def test_duplicate_and_bad_lexis(self):
        reg = {"codes": [{"id": "bad", "message": "m", "fix": "f"},
                         {"id": "NF_X", "message": "m", "fix": "f"},
                         {"id": "NF_X", "message": "m", "fix": "f"}]}
        issues = E.validate(reg)
        self.assertTrue(any("词法" in i for i in issues))
        self.assertTrue(any("重复" in i for i in issues))

    def test_unknown_code_raises(self):
        with self.assertRaises(ValueError):
            E.lookup({"codes": []}, "NF_X")
