import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import doc_routing as D  # noqa: E402


class Test(unittest.TestCase):
    def test_validate_and_lookup(self):
        e = [{"file": "01.md", "when": "写协议时"}, {"file": "02.md", "when": "装配模块时"}]
        self.assertEqual([], D.validate(e))
        self.assertEqual(["01.md"], D.lookup(e, "协议"))

    def test_duplicate_file(self):
        self.assertTrue(any("重复" in i for i in D.validate(
            [{"file": "a", "when": "x"}, {"file": "a", "when": "y"}])))
