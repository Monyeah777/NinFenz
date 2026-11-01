#!/usr/bin/env python3
"""`nf verify --jobs` 的判据：**并行结果必须与串行逐字节一致**，且失败必须如实计入。

为什么这条是硬判据
------------------
并行是**唯一能让「跑过」与「判定为真」脱钩**的调度改动（缓存同理）。
它一旦不一致或吞掉失败，门禁就会在「看起来更快」的同时给出错的结论——
正是 `ADR-0002-门禁不注水` 禁的事。故这里不测快不快，**只测等价性与 fail-closed**。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import verify_checks as vc  # noqa: E402


class ParallelEqualsSerialTest(unittest.TestCase):
    """并行合并出的 `checks` 必须与串行的 `checks` **逐字段相同**（含顺序）。"""

    @classmethod
    def setUpClass(cls):
        from core import gate_engine as ge
        ge.build_registry()
        cls.nums = sorted(ge.REGISTRY)

    def test_parallel_merge_matches_serial_for_a_representative_subset(self):
        """取几条**快**的代表（含一条 inproc、一条 delegated），比对逐字段等价。

        为什么用子集而不是全量：全量 22 条串行 ~19 s，本判据会跑两遍；子集把耗时压到
        可接受，同时覆盖两类执行形态（`inproc` 跑 verify.sh 原文 / `delegated` 委托 core.*）。
        """
        from core import gate_engine as ge
        kinds = {}
        for n in self.nums:
            kinds.setdefault(ge.REGISTRY[n].kind, n)
        pick = sorted(kinds.values())          # 每种 kind 取一条（inproc / delegated / native）
        self.assertGreaterEqual(len(pick), 2, "至少要覆盖两种执行形态")

        checks, broken = vc.run_checks_parallel(ROOT, pick, jobs=min(4, len(pick)))
        self.assertEqual([], broken, "并行子 check 不得有不可信项")

        from core import gate_engine as ge2
        serial = ge2.run_checks(ROOT, only=pick)
        want = [{"check": int(v.name.replace("check", "")), "status": v.status,
                 "verdicts": [s for s, _ in v.verdicts],
                 "messages": [m for _, m in v.verdicts]} for v in serial]
        self.assertEqual(want, checks, "并行合并结果必须与串行逐字段相同")

    def test_merge_is_sorted_by_check_number(self):
        """合并口径 = 按 check 号排序（与串行 `run_checks` 的顺序一致，输出才可重放）。"""
        checks, broken = vc.run_checks_parallel(ROOT, [20, 1, 13], jobs=3)
        self.assertEqual([], broken)
        got = [c["check"] for c in checks]
        self.assertEqual(sorted(got), got, "合并必须按 check 号排序")


class FailClosedTest(unittest.TestCase):
    """拿不到可信结论时**必须如实报错**，不许当通过。"""

    def test_untrusted_check_is_reported_not_skipped(self):
        """子进程跑不出一条**已迁入**的 check ⇒ 该号必须进 `broken`，不许静默丢失。"""
        # 999 不在 REGISTRY：`nf verify --only 999` 会以「未迁入」的机器面失败（rc=2）
        checks, broken = vc.run_checks_parallel(ROOT, [999], jobs=1)
        self.assertEqual([], checks, "不可信项不得产出结论")
        self.assertEqual([999], broken, "不可信项必须被点名")

    def test_run_one_marks_bad_json_as_untrusted(self):
        """非法 JSON / 非 0-1 退出码 ⇒ `ok=False`（不是「空结果 = 通过」）。"""
        r = vc.run_one(ROOT, 999)
        self.assertFalse(r["ok"], "不可信输出必须标 ok=False")
        self.assertTrue(r["stderr"], "必须留下诊断理由")


if __name__ == "__main__":
    unittest.main()
