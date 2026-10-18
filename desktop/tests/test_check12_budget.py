#!/usr/bin/env python3
"""check12 规模棘轮（P0）：权重基线必须**覆盖全部模块与测试**，总预算不得回升。

为什么要有它（2026-10-18）：P2 把 check12 改成分片并行后，"新增模块/测试要不要重测权重"
成了新的静默漂移点——没有权重的新测试会被按 1.0 秒估（份额最小），于是它**永远被最先塞进
同一分片**，而没人会发现。本测试把「权重覆盖面」变成可判事实：新增模块 /= 权重文件即红，
提示跑 `python scripts/verify_tests.py --write-weights`。

口径（故意只判**规模与预算**，不判具体秒数）：
- 模块集合必须双向相等（新增即红；消失的模块权重视为过期亦红）；
- 当前测试全集必须全部在 `tests` 权重里（逐测试权重覆盖）；
- 总预算：`total_s` ≤ BUDGET（防"慢慢变重还不自知"）；
- 单个模块上限：任何模块 ≤ MODULE_CAP（防单模块重新长成 200 s 的怪）。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import json_doc  # noqa: E402

WEIGHTS_REL = "protocol/check12_weights.json"
#: 总预算（秒）：分片并行前的实测是 1064 s；留 ~10% 余量，超过即要求重测并说明。
BUDGET_S = 1180.0
#: 单模块上限（秒）：超过说明该模块该被拆（或该被优化），不是"正常重"。
MODULE_CAP_S = 220.0


def _current_modules() -> set:
    return {p.stem for p in (ROOT / "desktop" / "tests").glob("test*.py")}


def _discover_ids() -> set:
    sys.path.insert(0, str(ROOT / "desktop"))
    sys.path.insert(0, str(ROOT / "desktop" / "tests"))
    import unittest as ut
    suite = ut.TestLoader().discover(str(ROOT / "desktop" / "tests"), pattern="test*.py")
    ids = []

    def walk(node):
        if isinstance(node, ut.TestSuite):
            for child in node:
                walk(child)
        else:
            ids.append(node.id())

    walk(suite)
    return set(ids)


class Check12BudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json_doc.load(ROOT / WEIGHTS_REL, dict, what=WEIGHTS_REL)
        cls.modules = cls.doc.get("modules") or {}
        cls.tests = cls.doc.get("tests") or {}

    def test_every_module_has_a_weight(self):
        have = set(self.modules)
        now = _current_modules()
        self.assertEqual(sorted(now - have), [], "新增模块没有权重（跑 --write-weights）")
        self.assertEqual(sorted(have - now), [], "权重里有已删除的模块（重测）")

    def test_every_test_has_a_weight(self):
        ids = _discover_ids()
        missing = sorted(ids - set(self.tests))
        self.assertEqual(missing[:8], [], "新增测试没有逐测试权重（跑 --write-weights）：%d 条"
                         % len(missing))

    def test_total_budget_does_not_grow(self):
        total = float(self.doc.get("total_s") or 0.0)
        self.assertGreater(total, 0.0, "权重基线缺 total_s")
        self.assertLessEqual(total, BUDGET_S,
                             "check12 总耗时回升到 %.1f s（预算 %.0f s）：重测并说明原因"
                             % (total, BUDGET_S))

    def test_no_module_is_absurdly_heavy(self):
        heavy = sorted(((v, k) for k, v in self.modules.items()), reverse=True)[:3]
        self.assertLessEqual(heavy[0][0], MODULE_CAP_S,
                             "单模块过重：%s = %.1f s（上限 %.0f s）"
                             % (heavy[0][1], heavy[0][0], MODULE_CAP_S))


if __name__ == "__main__":
    unittest.main()
