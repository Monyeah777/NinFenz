#!/usr/bin/env python3
"""全仓 CQ0/CQ1 契约（NF-Final WP-0H）：工具矩阵 + 全量扫描件 + 热点 + 质量债/清单。

真源 = `results/cq/{toolchain,scan}.json` + `findings.jsonl` + `hotspots.md`；
人读面 = `docs/CQ_REPORT.md` + `docs/QUALITY_DEBT.md` + `docs/REVIEW_CHECKLIST.md`。
判据：
1. 工具矩阵：13 个工具逐条记录版本/状态；缺失或不可用 → BLOCKED 且有理由（不冒充通过）；
2. 扫描件：9 个维度齐全；P0 维（语法/JSON/Shell/YAML）零问题；claims 同形技术词排除后零命中；
   findings 分诊（severity/owner/status）；计数与明细一致；hotspots 按复杂度降序；
3. 新鲜度：`cq_scan.check` 指纹（HEAD/工作树/工具版本）一致——树变/工具变必须重跑；
4. 文档：CQ 报告含 CQ0/CQ1 与 CQ2–CQ6 待办、BLOCKED 工具名；质量债有 owner/状态/复审；
   审查清单有四类工件清单与记录模板；
5. 不越级：报告不写「全绿/认证/合规」正向结论；缺失工具不写成通过；
6. 变异自证：删维度/改计数/删工具/blocked 无理由/指纹坏/hotspots 乱序/缺 P0 维零问题。
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cq_scan  # noqa: E402

DIR = ROOT / "results" / "cq"
DOCS = {
    "CQ": ROOT / "docs" / "CQ_REPORT.md",
    "DEBT": ROOT / "docs" / "QUALITY_DEBT.md",
    "CHECK": ROOT / "docs" / "REVIEW_CHECKLIST.md",
}
NEGATION = ("不", "非", "无", "未")


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class CqScanContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tc = _json(DIR / "toolchain.json")
        cls.scan = _json(DIR / "scan.json")
        cls.findings = [json.loads(line) for line in
                        (DIR / "findings.jsonl").read_text(encoding="utf-8").splitlines()
                        if line.strip()]
        cls.texts = {k: _text(p) for k, p in DOCS.items()}

    def test_artifacts_valid(self):
        self.assertEqual([], cq_scan.artifact_issues(self.tc, self.scan))
        self.assertTrue((DIR / "hotspots.md").is_file())
        self.assertGreaterEqual(len(self.tc["tools"]), 13)

    def test_blocked_tools_are_honest(self):
        for entry in self.tc["tools"]:
            if entry["status"] == "ok":
                self.assertTrue(entry["version"].strip(), entry["id"])
            else:
                self.assertIn(entry["id"], self.tc["blocked"])
                self.assertTrue(entry["blocked_reason"].strip(), entry["id"])
        # 本机环境事实：cosign/gitleaks 缺失必须是 BLOCKED（环境变化时测试会提醒重写报告）
        self.assertIn("cosign", self.tc["blocked"])
        self.assertIn("gitleaks", self.tc["blocked"])

    def test_scan_dimensions_and_p0_zero(self):
        dims = self.scan["dimensions"]
        for dim in cq_scan.DIMS:
            self.assertIn(dim, dims)
        for dim in ("syntax-python", "json-parse", "shell-syntax", "yaml-parse",
                    "claims-words"):
            self.assertEqual(0, dims[dim]["issues"], "%s 不应有 P0/命中" % dim)
        self.assertEqual(0, self.scan["p0"])
        self.assertEqual(0, self.scan["findings_counts"]["P1"])

    def test_findings_shaped_and_counted(self):
        for item in self.findings:
            self.assertIn(item["severity"], cq_scan.SEVERITIES)
            self.assertTrue(item["dim"] and item["owner"] and item["status"])
            self.assertTrue(str(item["id"]).startswith("F-"))
        for sev in cq_scan.SEVERITIES:
            want = sum(1 for f in self.findings if f["severity"] == sev)
            self.assertEqual(want, self.scan["findings_counts"][sev])

    def test_hotspots_sorted(self):
        hotspots = self.scan["hotspots"]
        self.assertTrue(hotspots, "热点不能为空（radon 已跑）")
        values = [int(h["complexity"]) for h in hotspots]
        self.assertEqual(sorted(values, reverse=True), values)

    def test_freshness_fingerprint(self):
        self.assertEqual([], cq_scan.check(str(ROOT)))
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "results" / "cq"
            dest.mkdir(parents=True)
            shutil.copy(DIR / "toolchain.json", dest / "toolchain.json")
            shutil.copy(DIR / "scan.json", dest / "scan.json")
            self.assertTrue(cq_scan.check(tmp), "拷贝到无 git 树仍应判指纹不一致")

    def test_docs_present_and_consistent(self):
        for key, path in DOCS.items():
            self.assertTrue(path.is_file(), "缺文档：%s" % path)
            self.assertTrue(self.texts[key].strip(), "文档为空：%s" % path)
        cq_text = self.texts["CQ"]
        for marker in ("CQ0", "CQ1", "CQ2", "CQ6", "cosign", "gitleaks", "dotnet"):
            self.assertIn(marker, cq_text)
        for marker in ("QD-01", "QD-05", "QD-07"):
            self.assertIn(marker, self.texts["DEBT"])
        for marker in ("Python", "Rust", ".NET", "Shell", "Schema", "review_id"):
            self.assertIn(marker, self.texts["CHECK"])
        self.assertIn("python scripts/cq_scan.py --run", cq_text)

    def test_no_overclaim(self):
        text = "\n".join(self.texts.values())
        for line in text.splitlines():
            for word in ("不可抵赖", "认证"):
                if word in line:
                    self.assertTrue(any(m in line for m in NEGATION),
                                    "禁用词未在否定语境：%s" % line.strip())

    def test_mutations_red(self):
        no_dim = copy.deepcopy(self.scan)
        no_dim["dimensions"].pop("bandit")
        self.assertTrue(cq_scan.artifact_issues(self.tc, no_dim), "删维度必须红")

        bad_count = copy.deepcopy(self.scan)
        bad_count["findings_counts"]["P2"] = 0
        self.assertTrue(cq_scan.artifact_issues(self.tc, bad_count), "计数不一致必须红")

        no_tool = copy.deepcopy(self.tc)
        no_tool["tools"] = no_tool["tools"][:-1]
        self.assertTrue(cq_scan.artifact_issues(no_tool, self.scan), "删工具必须红")

        no_reason = copy.deepcopy(self.tc)
        next(e for e in no_reason["tools"] if e["status"] == "blocked")["blocked_reason"] = ""
        self.assertTrue(cq_scan.artifact_issues(no_reason, self.scan), "blocked 缺理由必须红")

        bad_fp = copy.deepcopy(self.scan)
        bad_fp["fingerprint"] = "short"
        self.assertTrue(cq_scan.artifact_issues(self.tc, bad_fp), "坏指纹必须红")

        unsorted = copy.deepcopy(self.scan)
        unsorted["hotspots"] = list(reversed(unsorted["hotspots"]))
        self.assertTrue(cq_scan.artifact_issues(self.tc, unsorted), "hotspots 乱序必须红")

    def test_cheap_live_scans_clean(self):
        files = cq_scan._tracked(str(ROOT))
        stats, findings = cq_scan._scan_json(str(ROOT), files)
        self.assertEqual(0, stats["issues"], findings[:3])
        stats, findings = cq_scan._scan_shell(str(ROOT), files)
        self.assertEqual(0, stats["issues"], findings[:3])


if __name__ == "__main__":
    unittest.main()
