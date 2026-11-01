import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import style_dna as S  # noqa: E402


class Test(unittest.TestCase):
    def test_applies_to_required(self):
        self.assertEqual(1, len(S.validate([{"dna_id": "d1", "name": "n", "rule": "r"} ])))

    def test_for_path(self):
        e = [{"dna_id": "d1", "name": "n", "rule": "r", "applies_to": ["docs/*.md"]}]
        self.assertEqual([], S.validate(e))
        self.assertEqual(["d1"], S.for_path(e, "docs/x.md"))
        self.assertEqual([], S.for_path(e, "src/x.py"))
