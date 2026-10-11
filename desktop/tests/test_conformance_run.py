import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import conformance_run as C  # noqa: E402


class Test(unittest.TestCase):
    def test_plan_is_valid(self):
        p = C.plan("svc", "run svc", 8080, "/health", "1.2.3")
        self.assertEqual([], C.validate(p))

    def test_missing_teardown(self):
        p = C.plan("svc", "run svc", 8080, "/health", "1.2.3")
        p["steps"] = ["start", "run-suite"]
        self.assertTrue(any("teardown" in i for i in C.validate(p)))
