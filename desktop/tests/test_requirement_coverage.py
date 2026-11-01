"""requirement_coverage 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import requirement_coverage as C  # noqa: E402


class Test(unittest.TestCase):
    def test_uncovered_must_is_reported(self):
        reqs = [{"id": "R1", "level": "MUST"}, {"id": "R2", "level": "MUST", "plan": "后续补"}]
        checks = [{"id": "c1", "covers": ["R1"]}]
        self.assertEqual([], C.uncovered(reqs, checks))

    def test_uncovered_without_plan_fails(self):
        reqs = [{"id": "R9", "level": "MUST"}]
        self.assertEqual(1, len(C.uncovered(reqs, [])))

    def test_orphan_check(self):
        self.assertEqual(1, len(C.orphan_checks([{"id": "R1", "level": "MUST"}],
                                                [{"id": "c1", "covers": ["R1", "GHOST"]}])))
