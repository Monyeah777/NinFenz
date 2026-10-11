import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import numeric_grounding as N  # noqa: E402


class Test(unittest.TestCase):
    def test_grounded(self):
        self.assertEqual([], N.check("共 13 模块", ["模块数 13"]))

    def test_ungrounded_flagged(self):
        self.assertEqual(["99"], N.ungrounded("共 99 项", ["共 13 项"]))
