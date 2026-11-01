import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import ast_missing as A  # noqa: E402

SRC = "def ws_ok():\n    get_entry()\n    require_admin()\n\ndef ws_bad():\n    get_entry()\n"


class Test(unittest.TestCase):
    def test_missing_list(self):
        got = A.missing_guards(SRC, "ws_", ["get_entry", "require_admin"])
        self.assertEqual([("ws_bad", ["require_admin"])], got)

    def test_syntax_error_reported(self):
        self.assertIn("<syntax>", A.missing_guards("def :", "ws_", ["x"])[0])
