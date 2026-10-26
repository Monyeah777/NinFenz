# -*- coding: utf-8 -*-
"""Gate profile 缺陷注入台回归（T5.3）——把「检出率/误报率」从报告数字变成可执行断言。

判据分五层
----------
1. **台架可信**：注入算子零失效（锚点不存在/注入无变化 = 台架自身不可信，必须红）；
2. **形状**：10 类 × 10 例（8 负 + 2 正）/ 每 profile；target clause 必须真实存在于该 profile；
3. **阈值**：每 profile 负例检出率 ≥90%、清洁件误报率 ≤10%；overall 同口径；
4. **scope 诚实**：regulatory-strict 的「标题标点」明确标 out_of_scope（无判据面，不进分母），
   且 out_of_scope 类必须带原因说明——不许悄悄少算；
5. **确定性**：两次跑报告逐字节一致；CLI 落盘 == 进程内重算（陈旧报告会被这里抓住）。

跑法：python -m pytest desktop/tests/test_gate_defect_bench.py -q
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desktop" / "src"))

import gate_defect_bench as bench  # noqa: E402

COMMITTED = ROOT / bench.REPORT_REL


class BenchTrustTest(unittest.TestCase):
    """1 台架可信 + 5 确定性（先跑一次，全类共享）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = bench.run_bench()
        cls.text = bench.dumps(cls.report)

    def test_injection_ops_never_silently_fail(self) -> None:
        self.assertEqual([], self.report["invalid_cases"],
                         "注入算子失效：%s" % self.report["invalid_cases"])

    def test_two_runs_are_byte_identical(self) -> None:
        self.assertEqual(self.text, bench.dumps(bench.run_bench()),
                         "台架输出不确定（含时间/随机序/缓存态）")

    def test_committed_report_is_fresh(self) -> None:
        """落盘报告必须等于进程内重算（防"报告写着 100% 但台架已经变了"）。"""
        if not COMMITTED.is_file():
            self.skipTest("报告尚未落盘（首次运行 bench 前允许缺失）")
        self.assertEqual(self.text, COMMITTED.read_text(encoding="utf-8"),
                         "results/bench 报告陈旧：请重跑 scripts/gate_defect_bench.py")


class BenchShapeTest(unittest.TestCase):
    """2 形状：10 类、每类 10 例（8 负 + 2 正）、target 真实存在。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = bench.run_bench()
        cls.profile_clauses = {}
        for pid, rel in bench.PROFILES.items():
            from core import gate_profile as gp

            doc = gp.load(str(ROOT / rel))
            cls.profile_clauses[pid] = {str(c["clause_id"]) for c in doc["clauses"]}

    def test_ten_defect_classes_declared(self) -> None:
        ids = [c["id"] for c in self.report["defect_classes"]]
        self.assertEqual(10, len(ids))
        self.assertEqual(10, len(set(ids)))
        self.assertEqual({"跨域", "缺章节", "术语不一致", "标题标点", "单空格", "弱表达",
                          "披露缺失", "审计字段缺失", "风险档位", "版本不回退"},
                         {c["label"] for c in self.report["defect_classes"]})

    def test_every_class_is_ten_cases(self) -> None:
        bad = []
        for pid, doc in self.report["profiles"].items():
            self.assertEqual(10, len(doc["classes"]))
            for row in doc["classes"]:
                if row["cases"] != 10:
                    bad.append((pid, row["id"], "cases=%r" % row["cases"]))
                if row["negatives"] != bench.NEGATIVES_PER_CLASS:
                    bad.append((pid, row["id"], "negatives=%r" % row["negatives"]))
                if row["cleans"] != bench.CLEANS_PER_CLASS:
                    bad.append((pid, row["id"], "cleans=%r" % row["cleans"]))
        self.assertEqual([], bad, "类目形状不符：%s" % bad)

    def test_target_clauses_really_exist(self) -> None:
        """声明的 target 若不在此 profile 里，检出的语义就是假的——必须红。"""
        bad = []
        for pid, doc in self.report["profiles"].items():
            for row in doc["classes"]:
                for clause in row["target_clauses"]:
                    if clause not in self.profile_clauses[pid]:
                        bad.append((pid, row["id"], clause))
        self.assertEqual([], bad, "target clause 不存在于 profile：%s" % bad)

    def test_targets_match_scope_mode(self) -> None:
        for pid, doc in self.report["profiles"].items():
            for row in doc["classes"]:
                if row["in_scope"]:
                    self.assertTrue(row["target_clauses"],
                                    "%s/%s：in_scope 但没声明 target" % (pid, row["id"]))
                    self.assertIn(row["mode"], ("native", "compensated"))
                else:
                    self.assertEqual([], row["target_clauses"],
                                     "%s/%s：out_of_scope 不应声明 target" % (pid, row["id"]))
                    self.assertIn("无判据面", row["note"],
                                  "%s/%s：out_of_scope 必须写明原因" % (pid, row["id"]))


class BenchThresholdTest(unittest.TestCase):
    """3 阈值 + 4 scope 诚实。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = bench.run_bench()

    def test_profile_thresholds(self) -> None:
        for pid, doc in self.report["profiles"].items():
            tot = doc["totals"]
            self.assertGreaterEqual(tot["detection_rate"], bench.MIN_DETECTION_RATE,
                                    "%s 检出率不足：%r" % (pid, tot["detection_rate"]))
            self.assertLessEqual(tot["fp_rate"], bench.MAX_FP_RATE,
                                 "%s 误报率超限：%r" % (pid, tot["fp_rate"]))

    def test_overall_thresholds(self) -> None:
        ov = self.report["overall"]
        self.assertTrue(ov["negatives"] >= 100, "负例总量过少：%r" % ov["negatives"])
        self.assertGreaterEqual(ov["detection_rate"], bench.MIN_DETECTION_RATE)
        self.assertLessEqual(ov["fp_rate"], bench.MAX_FP_RATE)

    def test_in_scope_class_recall_is_not_decorative(self) -> None:
        """每类（在册时）至少 7/8 检出——单类整体失效说明注入配方坏了，不该只靠 aggregate 掩盖。"""
        bad = []
        for pid, doc in self.report["profiles"].items():
            for row in doc["classes"]:
                if row["in_scope"] and row["detection_rate"] < 0.875:
                    bad.append((pid, row["id"], row["detection_rate"]))
        self.assertEqual([], bad, "单类检出率过低：%s" % bad)

    def test_clean_baselines_are_not_flagged(self) -> None:
        from core import gate_profile as gp

        for pid, rel in bench.PROFILES.items():
            profile = gp.load(str(ROOT / rel))
            base = (ROOT / bench.FIXTURES[pid]).read_text(encoding="utf-8")
            doc = gp.report(base, profile)
            self.assertTrue(doc["ok"], "%s 清洁基线被误判为 FAIL：%r"
                            % (pid, doc["summary"]))
            self.assertEqual(0, doc["summary"]["fail"],
                             "%s 清洁基线含 fail 级 finding" % pid)

    def test_regulatory_scope_gap_is_explicit(self) -> None:
        reg = self.report["profiles"]["regulatory-strict"]
        out = [row["id"] for row in reg["classes"] if not row["in_scope"]]
        self.assertEqual(["heading_punct"], out,
                         "regulatory-strict 的未覆盖类变了：%r（若 profile 新增条款，"
                         "请把该类改成 native 并重抽）" % out)
        self.assertEqual(9, reg["totals"]["classes_in_scope"])
        tech = self.report["profiles"]["techdoc-strict"]
        self.assertEqual(10, tech["totals"]["classes_in_scope"])

    def test_verdict_is_ok_and_explained(self) -> None:
        v = self.report["verdict"]
        self.assertTrue(v["ok"], "台架判定为未通过：%r" % v["reasons"])
        self.assertEqual([], v["reasons"])
        self.assertEqual({"techdoc-strict", "regulatory-strict"}, set(v["profiles"]))


class CliTest(unittest.TestCase):
    """CLI 契约：rc=0、写盘、机器面 schema。"""

    def test_cli_writes_report_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "gate_defect_bench.py"),
                 "--out", str(out), "--json"],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", timeout=300)
            self.assertEqual(0, proc.returncode, "stderr=%s" % proc.stderr[-800:])
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(bench.SCHEMA, doc["schema"])
            self.assertEqual(bench.dumps(bench.run_bench()),
                             out.read_text(encoding="utf-8"),
                             "CLI 落盘与进程内重算不一致")
            self.assertEqual(doc["schema"], json.loads(proc.stdout)["schema"])


if __name__ == "__main__":
    unittest.main()
