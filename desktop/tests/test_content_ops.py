#!/usr/bin/env python3
"""内容 SRE（T11.1）判据：OK/WARN/UNKNOWN、缺源 fail-closed、确定性、真仓形状。

fixture = 一套**合成真实载体**（bench 报告 / LEADERBOARD / conformance / 回执 / verify 判据面 /
审计件 / 两个索引 / 执行记录模板），不联网、不跑 verify。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import content_ops as co  # noqa: E402

FIXED_NOW = 1_800_000_000.0
_ID = "a" * 64


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _json(root: Path, rel: str, doc) -> None:
    _write(root, rel, json.dumps(doc, ensure_ascii=False, indent=2))


def _scene() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="nf-ops-"))
    _json(tmp, "results/bench/gate_defect_report.json", {
        "overall": {"detection_rate": 1.0, "fp_rate": 0.0, "detected": 152,
                    "negatives": 152, "clean_cases": 40, "fail_flagged_clean": 0},
        "thresholds": {"min_detection_rate": 0.9, "max_fp_rate": 0.1},
        "verdict": {"ok": True, "profiles": {"p": True}, "reasons": []},
    })
    _write(tmp, "results/bench/LEADERBOARD.md", (
        "# NF Benchmark\n\n"
        "| profile | 来源 | 检出 | 漏报 | 误报 | 检出率 | 误报率 | 判定 | 证据 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| regulatory-strict | baseline | 72 | 72 | 0 | 100.00% | 0.00% | pass | x |\n"
        "| techdoc-strict | baseline | 80 | 80 | 0 | 100.00% | 0.00% | pass | x |\n"))
    _json(tmp, "protocol/conformance_report.json", {
        "schema": "nf-conformance/1", "passed": 2, "total": 2,
        "verdict": "conformant", "root": _ID, "contracts": [{}, {}]})
    _json(tmp, "protocol/RECEIPTS.json", {
        "schema": "nf-receipts/1", "scope": "protocol", "count": 2,
        "root": _ID, "entries": [{}, {}]})
    _json(tmp, "protocol/verification_report.json", {
        "declared": {"report_items": 6}, "items": [],
        "summary": {"pass": 5, "fail": 0, "warn": 0, "error": 0}})
    _write(tmp, "results/audit/a.md", "---\nid: AUD-1\n---\n")
    _write(tmp, "results/audit/b.md", "---\nid: AUD-2\n---\n")
    _json(tmp, "protocol/registry_index.json", {
        "schema": "nf-registry-index/1", "root": _ID, "entries": [{}, {}]})
    _json(tmp, "protocol/concept_graph_index.json", {
        "schema": "nf-concept-index/1", "root": _ID, "nodes": [{}, {}]})
    _json(tmp, "protocol/exec_records/_TEMPLATE.json",
          {"schema": "nf-exec-record/1", "template": True})
    # 把产物 mtime 钉在 now 附近（避免 stale 干扰）
    for rel in ("results/bench/gate_defect_report.json", "results/bench/LEADERBOARD.md",
                "protocol/conformance_report.json", "protocol/RECEIPTS.json",
                "protocol/verification_report.json",
                "protocol/registry_index.json", "protocol/concept_graph_index.json"):
        os.utime(tmp / rel, (FIXED_NOW - 3600, FIXED_NOW - 3600))
    for f in ("results/audit/a.md", "results/audit/b.md"):
        os.utime(tmp / f, (FIXED_NOW - 3600, FIXED_NOW - 3600))
    return tmp


def _by_id(report):
    return {s["id"]: s for s in report["slis"]}


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.root = _scene()
        self.report = co.collect(str(self.root), now=FIXED_NOW, live=False)

    def test_shape_and_expected_statuses(self):
        self.assertEqual("nf-ops-report/1", self.report["schema"])
        self.assertEqual(14, len(self.report["slis"]))
        for s in self.report["slis"]:
            for key in ("id", "title", "value", "unit", "source", "freshness", "status",
                        "reason", "threshold", "detail"):
                self.assertIn(key, s, s.get("id"))
            self.assertIn(s["status"], ("OK", "WARN", "UNKNOWN"))
        by = _by_id(self.report)
        for sid in ("gate_defect_detection_rate", "gate_defect_fp_rate", "conformance_passed",
                    "receipts_root", "audit_count", "verify_report_fail", "verify_report_warn",
                    "registry_index", "concept_index"):
            self.assertEqual("OK", by[sid]["status"], (sid, by[sid]))
        self.assertEqual(1.0, by["conformance_passed"]["value"])
        self.assertEqual("UNKNOWN", by["benchmark_real_model_rows"]["status"])
        self.assertEqual(0, by["benchmark_real_model_rows"]["value"])
        self.assertEqual("no_real_model_rows", by["benchmark_real_model_rows"]["reason"])
        self.assertEqual("UNKNOWN", by["exec_records_m2"]["status"])
        self.assertEqual("no_m2_records", by["exec_records_m2"]["reason"])
        self.assertEqual("UNKNOWN", by["security_critical"]["status"])
        self.assertEqual("live_disabled", by["security_critical"]["reason"])
        self.assertEqual("UNKNOWN", self.report["overall"])
        self.assertEqual({"OK": 9, "WARN": 0, "UNKNOWN": 5},
                         self.report["status_counts"])

    def test_check_does_not_fail_on_known_empty(self):
        issues, report = co.check(str(self.root), now=FIXED_NOW, live=False)
        self.assertEqual([], issues)
        self.assertEqual(self.report["overall"], report["overall"])

    def test_warn_on_threshold_breach(self):
        _json(self.root, "results/bench/gate_defect_report.json", {
            "overall": {"detection_rate": 0.5, "fp_rate": 0.5, "detected": 1,
                        "negatives": 2, "clean_cases": 1, "fail_flagged_clean": 3},
            "thresholds": {"min_detection_rate": 0.9, "max_fp_rate": 0.1},
            "verdict": {"ok": False}})
        _json(self.root, "protocol/conformance_report.json", {
            "passed": 1, "total": 2, "verdict": "non-conformant", "root": _ID})
        _json(self.root, "protocol/verification_report.json", {
            "summary": {"pass": 4, "fail": 1, "warn": 2, "error": 0}})
        rep = co.collect(str(self.root), now=FIXED_NOW, live=False)
        by = _by_id(rep)
        self.assertEqual("WARN", by["gate_defect_detection_rate"]["status"])
        self.assertEqual("WARN", by["gate_defect_fp_rate"]["status"])
        self.assertEqual("WARN", by["conformance_passed"]["status"])
        self.assertEqual("WARN", by["verify_report_fail"]["status"])
        self.assertEqual("WARN", by["verify_report_warn"]["status"])
        # overall 取最差：live 面（fixture 用 --no-live 等价）仍是 UNKNOWN，故顶层 UNKNOWN；
        # WARN 已逐条体现在 SLI 上（不因顶层 UNKNOWN 而吞掉告警）。
        self.assertEqual("UNKNOWN", rep["overall"])
        self.assertGreaterEqual(rep["status_counts"]["WARN"], 5)

    def test_stale_source_downgrades_to_warn(self):
        old = FIXED_NOW - 31 * 86400
        os.utime(self.root / "results/bench/gate_defect_report.json", (old, old))
        rep = co.collect(str(self.root), now=FIXED_NOW, live=False)
        s = _by_id(rep)["gate_defect_detection_rate"]
        self.assertEqual("WARN", s["status"])
        self.assertEqual("stale_source", s["reason"])
        self.assertTrue(s["freshness"]["stale"])

    def test_missing_source_fail_closed(self):
        (self.root / "protocol/conformance_report.json").unlink()
        rep = co.collect(str(self.root), now=FIXED_NOW, live=False)
        s = _by_id(rep)["conformance_passed"]
        self.assertEqual("UNKNOWN", s["status"])
        self.assertEqual("missing_source", s["reason"])
        issues, _ = co.check(str(self.root), now=FIXED_NOW, live=False)
        self.assertTrue(any("conformance_passed" in i and "missing_source" in i
                            for i in issues), issues)

    def test_malformed_source_fail_closed(self):
        _write(self.root, "protocol/RECEIPTS.json", "{ not json")
        rep = co.collect(str(self.root), now=FIXED_NOW, live=False)
        self.assertEqual("UNKNOWN", _by_id(rep)["receipts_root"]["status"])
        issues, _ = co.check(str(self.root), now=FIXED_NOW, live=False)
        self.assertTrue(any("receipts_root" in i for i in issues), issues)

    def test_deterministic(self):
        a = co.collect(str(self.root), now=FIXED_NOW, live=False)
        b = co.collect(str(self.root), now=FIXED_NOW, live=False)
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))


class RealRepoTest(unittest.TestCase):
    """真仓常驻判据：报告可采集、缺源不误报、已知无数据如实 UNKNOWN。"""

    def test_real_repo_shape(self):
        issues, rep = co.check(str(ROOT), live=False)
        self.assertEqual([], issues, issues[:3])
        self.assertEqual("nf-ops-report/1", rep["schema"])
        self.assertEqual(14, len(rep["slis"]))
        by = _by_id(rep)
        self.assertEqual("OK", by["gate_defect_detection_rate"]["status"])
        self.assertEqual("OK", by["conformance_passed"]["status"])
        self.assertEqual("UNKNOWN", by["benchmark_real_model_rows"]["status"])
        self.assertEqual(0, by["benchmark_real_model_rows"]["value"])
        self.assertEqual(0, by["exec_records_m2"]["value"])
        self.assertIn(rep["overall"], ("OK", "WARN", "UNKNOWN"))
        self.assertTrue((ROOT / "docs" / "ops" / "content-slo.md").is_file(),
                        "缺 docs/ops/content-slo.md（口径与实测值未落盘）")

    def test_cli_report_and_check(self):
        p = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py"),
                            "ops", "check", "--no-live", "--json"],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(0, p.returncode, (p.stdout or "") + (p.stderr or ""))
        doc = json.loads(p.stdout)
        self.assertEqual("ops-check", doc["kind"])
        self.assertEqual([], doc["issues"])
        self.assertEqual("nf-ops-report/1", doc["report"]["schema"])


if __name__ == "__main__":
    unittest.main()
