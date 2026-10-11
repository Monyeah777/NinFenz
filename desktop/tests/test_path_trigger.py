import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import path_trigger as P  # noqa: E402


class Test(unittest.TestCase):
    def test_trigger_and_missing(self):
        m = {"desktop/src/core/*.py": "check27", "docs/*.md": "check36"}
        hit = P.triggered(m, ["desktop/src/core/x.py"])
        self.assertEqual(["check27"], list(hit))
        self.assertEqual(1, len(P.missing_evidence(hit, [])))
        self.assertEqual([], P.missing_evidence(hit, ["check27"]))
