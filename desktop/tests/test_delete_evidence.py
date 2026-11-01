import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import delete_evidence as D  # noqa: E402


class Test(unittest.TestCase):
    def test_kind_and_ref_required(self):
        self.assertEqual(2, len(D.check([{"target": "a.md", "kind": "guess"}])))

    def test_ok_and_blame(self):
        r = [{"target": "a.md", "kind": "vcs", "ref": "abc123"}]
        self.assertEqual([], D.check(r))
        self.assertEqual(1, len(D.missing_blame(r, require_blame=True)))
