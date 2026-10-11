import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import commit_title_guard as G  # noqa: E402


class Test(unittest.TestCase):
    def test_internal_ids_flagged(self):
        self.assertTrue(G.check("feat(core): 波C 收口 §13.3 计划第 2 步"))

    def test_amount_flagged(self):
        self.assertTrue(G.check("feat(x): 报价 12 万元"))

    def test_clean(self):
        self.assertEqual([], G.check("feat(core): 新增锚点回验模块"))
