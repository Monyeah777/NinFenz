#!/usr/bin/env python3
"""docs/42_M4 资产评估报告契约：快照状态 + 现状活绑定 + 结论口径不变 + 复现口径。

为什么必须有：这是一次性资产评估存档——它写「校园 29 / 西幻 23 / ledger 2 / 只有 5 个域包」，而
现行已是 **111 个域包（108 有资产）/ 465 资产文件 / 台账 103 · 托管 308 · 孤儿 0**。结论方向
（无孤儿、按需等待消费方）仍成立，但基数全变；不标现状，读者会拿旧基数做密度判断。本轮补
快照横幅、现状对照（含结论复核注）、复现口径，并把基数与闭合事实立成机检断言。

范围：只判本文与 05 台账/community 资产面自洽（不改结论）。同族判据：
test_doc_truth.py（资产面命令）/ test_doc_reachability.py（ARCHIVE_DOCS，故 glob 用通配符）/
check23（供应链闭合门禁，verify.sh）。
契约：标题 + 快照横幅、四节 + 现状对照 + 复现口径、历史值保留（29/23/2/5 包）、
现行基数（111 包 / 108 有资产 / 3 个 0-资产包 / 校园 30 / 西幻 24 / 465 文件 / 台账 3）、
结论口径「无孤儿 / 按需等待消费方」保留、复现三命令为 nf 形式。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

HITS = sorted((ROOT / "docs").glob("42_M4_资产评估报告*.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-asset-report.md"
PROV = ROOT / "05_资产库" / "provenance.json"
COMMUNITY = ROOT / "community"
SECTIONS = ("## 一、现状盘点", "## 二、密度判定", "## 三、建议", "## 四、结论",
            "## 现状对照", "## 复现与引用口径")
ZERO_PKGS = ("技术文档域包", "校园西幻轻混组合包", "通用核心基础包")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"资产评估报告不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("资产评估报告为空")
    return text


def asset_stats() -> tuple:
    pkgs = [p for p in COMMUNITY.iterdir() if p.is_dir()]
    with_assets = [p for p in pkgs if (p / "assets").is_dir() and any((p / "assets").iterdir())]
    zero = [p.name for p in pkgs if p not in with_assets]
    files = sum(len(list((p / "assets").glob("*"))) for p in with_assets)
    ledger = len(json.loads(PROV.read_text(encoding="utf-8")).get("assets") or [])
    campus = len(list((COMMUNITY / "校园情感领域包" / "assets").glob("*")))
    western = len(list((COMMUNITY / "西幻生存领域包" / "assets").glob("*")))
    return len(pkgs), len(with_assets), files, ledger, campus, western, sorted(zero)


def report_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M4 · 资产密度评估报告"):
        issues.append("缺标题「# 42 M4 · 资产密度评估报告」")
    if "状态：历史评估快照" not in text:
        issues.append("缺「历史评估快照」状态横幅")
    if "结论方向" not in text:
        issues.append("缺「结论方向仍成立」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for old in ("29", "23", "2（TECH_RULES", "5 包"):
        if old not in text:
            issues.append(f"历史值被改写：{old}")
    pkgs, with_assets, files, ledger, campus, western, zero = asset_stats()
    if (pkgs, with_assets, files, ledger, campus, western) != (111, 108, 465, 3, 30, 24):
        issues.append(f"资产面已变（包 {pkgs}/有资产 {with_assets}/文件 {files}/台账 {ledger}"
                      f"/校园 {campus}/西幻 {western}）：现状对照需复核")
    if zero != sorted(ZERO_PKGS):
        issues.append(f"0-资产包集合已变：{zero}")
    markers = ("111 包", "108 有资产", "465", "台账 103", "托管 308",
               "孤儿头 0", "30 / 24")
    for marker in markers:
        if marker not in text:
            issues.append(f"现状对照缺要素：{marker}")
    if "3 个 0-资产包" not in text:
        issues.append("未写 3 个 0-资产包")
    for keep in ("无孤儿", "按需等待消费方"):
        if keep not in text:
            issues.append(f"结论口径丢失：{keep}")
    for cmd in ("python scripts/nf.py asset verify", "python scripts/nf.py asset inventory",
                "asset ledger --refresh"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AssetReportContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_asset_report_matches_contract(self):
        self.assertEqual([], report_issues(self.text), "资产评估报告不满足契约")

    def test_asset_stats_are_live(self):
        pkgs, with_assets, files, ledger, campus, western, zero = asset_stats()
        expect = (111, 108, 465, 3, 30, 24)
        self.assertEqual(expect, (pkgs, with_assets, files, ledger, campus, western))
        self.assertEqual(sorted(ZERO_PKGS), zero)

    def test_contract_catches_mutations(self):
        """变异自证：去快照横幅 / 旧基数回退 / 基数漂移 / 缺结论口径 / 缺现状对照 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史评估快照", "> **状态：现行", 1)
        self.assertTrue(any("历史评估快照" in i for i in report_issues(no_banner)))
        old = self.text.replace("30 / 24", "29 / 23")
        self.assertTrue(any("30 / 24" in i or "历史值" in i for i in report_issues(old)))
        wrong = self.text.replace("111 包", "5 包")
        self.assertTrue(any("111 包" in i for i in report_issues(wrong)))
        no_keep = self.text.replace("按需等待消费方", "待补资产")
        self.assertTrue(any("按需等待消费方" in i for i in report_issues(no_keep)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in report_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py asset verify", "检查资产")
        self.assertTrue(any("asset verify" in i for i in report_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_asset_report.md")


if __name__ == "__main__":
    unittest.main()
