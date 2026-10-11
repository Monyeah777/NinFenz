"""absence_guard 单测。"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from core import absence_guard as G  # noqa: E402


class Test(unittest.TestCase):
    def test_absence_without_boundary_is_issue(self):
        self.assertTrue(G.check("该依赖不存在。"))

    def test_boundary_declared_is_ok(self):
        self.assertEqual([], G.check("在检索面 04_模块库/ 共 13 条内未找到，属未命中（下界）。"))

    def test_claims_listed(self):
        self.assertEqual(1, len(G.absence_claims("没有找到任何锚点。")))
