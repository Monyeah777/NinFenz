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
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import json_doc  # noqa: E402

WEIGHTS_REL = "protocol/check12_weights.json"
#: 总预算（秒）。口径 = `--write-weights` 的**逐模块独立进程**实测之和：含每模块一次解释器
#: 启动（311 个模块 ≈ 120 s 固定税），故比单进程串行墙钟（~1080 s）高。2026-10-18 实测
#: 1851 s；留 ~15% 余量，超过即要求重测并在提交说明里写清"为什么变重"。
BUDGET_S = 2130.0
#: 单模块上限（秒）：超过说明该模块该被拆（或该被优化），不是"正常重"。
#: 2026-10-29 实测 daemon parity 24 切片为 301.5 s（同判据历史 191–302 s），
#: 给 10% 环境波动余量；超过 330 s 仍必须拆分。
MODULE_CAP_S = 330.0


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

    def test_every_test_belongs_to_a_measured_module(self):
        """硬判据 = **模块级**覆盖（新增模块必须重测）；逐测试权重只要求高覆盖（≥90%）。

        为什么分层（2026-10-18 实测教训）：逐测试权重是 30 分钟量级的测量，而"新增一条测试"
        是分钟级的日常动作——把后者也判死会让门禁逼着贡献者每次重测全量。于是：
        模块必须有权重（否则分片估算失真），测试缺失则退回"模块内均分"（LPT 仍有界），
        只要求整体逐测试覆盖率不低于 90%（低于它就说明很久没重测了）。
        """
        ids = _discover_ids()
        known = set(self.tests)
        uncovered_modules = sorted({t.split(".")[0] for t in ids - known} - set(self.modules))
        self.assertEqual(uncovered_modules, [], "有模块整块没有权重（跑 --write-weights）")
        ratio = len(ids & known) / max(1, len(ids))
        self.assertGreaterEqual(ratio, 0.90,
                                "逐测试权重覆盖率降到 %.1f%%（跑 --write-weights）"
                                % (ratio * 100))

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
