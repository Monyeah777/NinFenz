import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import face_coverage as F  # noqa: E402


class Test(unittest.TestCase):
    def test_uncovered_and_orphan(self):
        self.assertEqual(["face-b"], F.uncovered_faces(["face-a", "face-b"],
                                                       [{"id": "c1", "covers": ["face-a"]}]))
        self.assertEqual(1, len(F.orphan_checks(["face-a"], [{"id": "c1", "covers": ["ghost"]}])))
