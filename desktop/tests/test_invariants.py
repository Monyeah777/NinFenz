import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import invariants as I  # noqa: E402


class Test(unittest.TestCase):
    def test_register_and_evaluate(self):
        I.register("zt3_ok", lambda ctx: (ctx.get("x") == 1, "x"))
        I.register("zt3_bad", lambda ctx: (False, "always false"))
        r = I.evaluate({"x": 1})
        got = {x["name"]: x["ok"] for x in r["results"]}
        self.assertTrue(got["zt3_ok"])
        self.assertFalse(got["zt3_bad"])
        self.assertFalse(r["ok"])

    def test_duplicate_name_rejected(self):
        I.register("zt3_dup", lambda ctx: (True, ""))
        with self.assertRaises(ValueError):
            I.register("zt3_dup", lambda ctx: (True, ""))
