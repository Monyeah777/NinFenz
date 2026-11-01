import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import case_schema as C  # noqa: E402


class Test(unittest.TestCase):
    def test_all_four_required(self):
        self.assertEqual(4, len(C.validate({})))

    def test_complete_case_ok(self):
        case = C.make("为什么要这条", "怎么跑", "期望结果", "曾经给过的错误答案")
        self.assertEqual([], C.validate(case))
