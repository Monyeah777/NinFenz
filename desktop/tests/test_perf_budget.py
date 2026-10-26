#!/usr/bin/env python3
"""性能预算（`core/perf_budget.py`）回归测试 —— ISO 25010 性能效率面。

全部用注入计时器 + 临时根；不依赖真实耗时与工作区状态。
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import perf_budget as pb  # noqa: E402


def _decl(tmp: str, entries, evidence=None) -> None:
    p = Path(tmp) / pb.DECL_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": pb.SCHEMA, "note": "t", "reference_host": "test",
                             "entries": entries, "evidence": evidence or {}},
                            ensure_ascii=False), encoding="utf-8")


# 预算 120：注入了 [70,90,110] 的三连发 ⇒ P95=110 恰好进预算（判据是 P95，不是中位）。
ONE = [{"id": "x", "cmd": "python -c pass", "budget_ms": 120, "runs": 3, "max_age_days": 7}]


class LoadTest(unittest.TestCase):
    def test_missing_declaration_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues, _w, _s = pb.scan(tmp)
        self.assertTrue(any(pb.DECL_REL in i and "修复指引" in i for i in issues), issues)

    def test_empty_entries_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, [])
            issues, _w, _s = pb.scan(tmp)
        self.assertTrue(any("entries" in i for i in issues), issues)


class ScanTest(unittest.TestCase):
    def test_missing_record_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE)
            issues, _w, _s = pb.scan(tmp)
        self.assertTrue(any("无实测记录" in i for i in issues), issues)

    def test_over_budget_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE, {"x": {"median_ms": 250, "measured_at": dt.date.today().isoformat()}})
            issues, _w, stats = pb.scan(tmp)
        self.assertTrue(any("超预算" in i and "250" in i for i in issues), issues)
        self.assertEqual(1, stats["over_budget"])

    def test_within_budget_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE, {"x": {"median_ms": 80, "measured_at": dt.date.today().isoformat()}})
            issues, _w, _s = pb.scan(tmp)
        self.assertEqual([], issues)

    def test_stale_record_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = (dt.date.today() - dt.timedelta(days=30)).isoformat()
            _decl(tmp, ONE, {"x": {"median_ms": 80, "measured_at": old}})
            issues, _w, _s = pb.scan(tmp)
        self.assertTrue(any("过期" in i for i in issues), issues)

    def test_undeclared_record_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE, {"x": {"median_ms": 80, "measured_at": dt.date.today().isoformat()},
                             "ghost": {"median_ms": 1, "measured_at": dt.date.today().isoformat()}})
            issues, _w, _s = pb.scan(tmp)
        self.assertTrue(any("ghost" in i for i in issues), issues)

    def test_p95_is_judged_when_present(self):
        """判据取 P95（尾延迟），不是中位——中位漂亮但尾抖大同样要红（审计 X3/M2）。"""
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE, {"x": {"median_ms": 80, "p95_ms": 250, "stdev_ms": 90,
                                   "measured_at": dt.date.today().isoformat()}})
            issues, _w, stats = pb.scan(tmp)
        self.assertTrue(any("P95" in i and "250" in i for i in issues), issues)
        self.assertEqual(1, stats["over_budget"])

    def test_exit_code_is_not_judged(self):
        """性能面只看耗时与新鲜度；正确性归 verify_report——故 exit_code 非 0 不该 FAIL。"""
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE, {"x": {"median_ms": 50, "exit_code": 1,
                                   "measured_at": dt.date.today().isoformat()}})
            issues, _w, _s = pb.scan(tmp)
        self.assertEqual([], issues)


class RecordTest(unittest.TestCase):
    def test_record_writes_median_and_scan_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE)
            bad, doc = pb.record(tmp, only="all", runner=lambda cmd, n: (0, [90, 110, 70]))
            rec = doc["evidence"]["x"]
            self.assertEqual(90, rec["median_ms"], "中位数须取排序后中位（70,90,110 → 90）")
            self.assertEqual(110, rec["p95_ms"], "P95 须落进证据（3 样本最近秩即最大值）")
            self.assertEqual(20.0, rec["stdev_ms"], "样本标准差须落证据（70,90,110 → 20）")
            self.assertEqual(70, rec["min_ms"])
            self.assertEqual(110, rec["max_ms"])
            self.assertEqual([], bad)
            issues, _w, _s = pb.scan(tmp)
        self.assertEqual([], issues)

    def test_true_median_for_even_runs(self):
        """偶数样本取真中位（审计 M1）：[10,20,30,70] → 25，不是上中位 30。"""
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, [dict(ONE[0], runs=4, budget_ms=200)])
            _bad, doc = pb.record(tmp, only="all", runner=lambda cmd, n: (0, [10, 20, 30, 70]))
            rec = doc["evidence"]["x"]
        self.assertEqual(25.0, rec["median_ms"])
        self.assertEqual(70, rec["p95_ms"])

    def test_warmup_is_not_measured(self):
        """预热不计入证据（审计 F2）：第一次调用只热场，第二次才是 measured runs。"""
        calls = []

        def runner(cmd, n):
            calls.append(n)
            return 0, [10] * n

        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, [dict(ONE[0], warmups=2, runs=3)])
            _bad, doc = pb.record(tmp, only="all", runner=runner)
        self.assertEqual([2, 3], calls, "先热 2 次（丢弃），再测 3 次")
        self.assertEqual(3, doc["evidence"]["x"]["runs"])
        self.assertEqual(2, doc["evidence"]["x"]["warmups"])

    def test_record_reports_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, ONE)
            bad, _doc = pb.record(tmp, only="all", runner=lambda cmd, n: (0, [500, 500, 500]))
        self.assertEqual(["x"], bad)

    def test_record_only_filters(self):
        two = [dict(ONE[0], id="a"), dict(ONE[0], id="b")]
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, two)
            _bad, doc = pb.record(tmp, only="a", runner=lambda cmd, n: (0, [10]))
        self.assertIn("a", doc["evidence"])
        self.assertNotIn("b", doc["evidence"])


class RealRepoTest(unittest.TestCase):
    def test_declaration_committed_with_evidence(self):
        p = ROOT / pb.DECL_REL
        self.assertTrue(p.is_file(), "须提交性能预算声明：%s" % pb.DECL_REL)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(pb.SCHEMA, doc["schema"])
        self.assertGreaterEqual(len(doc["entries"]), 3, "至少声明 3 个性能目标")
        for e in doc["entries"]:
            self.assertTrue(e.get("id") and e.get("cmd") and float(e.get("budget_ms") or 0) > 0,
                            "每条须有 id/cmd/budget_ms：%s" % e)


if __name__ == "__main__":
    unittest.main()


class PlatformBudgetTest(unittest.TestCase):
    """平台化预算（2026-10-25）：同一命令 Windows 比 Linux 慢 1.5~2×，单一阈值必然二选一。"""

    def test_budget_of_prefers_platform_override(self):
        e = {"budget_ms": 100, "budget_ms_by_platform": {"windows": 250, "linux": 80}}
        self.assertEqual(250, pb.budget_of(e, "windows"))
        self.assertEqual(80, pb.budget_of(e, "linux"))
        # 未声明的平台：回落到 budget_ms（不是 0——0 会被当成「不判」而静默放行）
        self.assertEqual(100, pb.budget_of(e, "macos"))
        # 老声明没有平台表：行为与改造前一致
        self.assertEqual(100, pb.budget_of({"budget_ms": 100}, "windows"))

    def test_platform_alias_maps_win32(self):
        self.assertEqual("windows", pb.platform_of("win32"))
        self.assertEqual("linux", pb.platform_of("linux"))

    def test_scan_judges_by_current_platform_budget(self):
        # 40 ms 在 linux 预算 30 下超、在 windows 预算 90 下不超
        entry = {"id": "x", "cmd": "python -c pass", "budget_ms": 30, "runs": 3,
                 "max_age_days": 7,
                 "budget_ms_by_platform": {"linux": 30, "windows": 90}}
        today = dt.date.today().isoformat()
        ev_w = {"x": {"p95_ms": 40, "median_ms": 35, "platform": "windows", "measured_at": today}}
        ev_l = {"x": {"p95_ms": 40, "median_ms": 35, "platform": "linux", "measured_at": today}}
        with tempfile.TemporaryDirectory() as tmp_w, tempfile.TemporaryDirectory() as tmp_l:
            _decl(tmp_w, [entry], ev_w)
            _decl(tmp_l, [entry], ev_l)
            issues_w, _w, stats_w = pb.scan(tmp_w, platform="windows")
            issues_l, _w, stats_l = pb.scan(tmp_l, platform="linux")
        self.assertEqual([], issues_w, issues_w)
        self.assertEqual(0, stats_w["over_budget"])
        self.assertTrue(any("超预算" in i for i in issues_l), issues_l)
        self.assertEqual(1, stats_l["over_budget"])

    def test_cross_platform_evidence_warns_not_fails(self):
        entry = {"id": "x", "cmd": "python -c pass", "budget_ms": 10, "runs": 3,
                 "max_age_days": 7}
        ev = {"x": {"p95_ms": 999999, "median_ms": 999999, "platform": "windows",
                    "measured_at": dt.date.today().isoformat()}}
        with tempfile.TemporaryDirectory() as tmp:
            _decl(tmp, [entry], ev)
            issues, warns, _s = pb.scan(tmp, platform="linux")
        # 记录采集于别的平台 ⇒ 耗时不可比：不判超预算（也不静默），改发 WARN 要求本平台重录
        self.assertEqual([], issues, issues)
        self.assertTrue(any("采集于平台" in w for w in warns), warns)
