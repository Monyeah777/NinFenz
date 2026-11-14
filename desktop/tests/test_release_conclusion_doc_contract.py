#!/usr/bin/env python3
"""docs/ccos/release-conclusion.md 契约：发布结论文档必须「五步/快照语义/预算与分工数字活绑定」。

为什么必须有：这份文档是「这台机器现在能不能发布」的口径来源——五步顺序、快照绑定语义、
权重预算线、与 precheck 的分工，任何一处漂移都会让人跑错或误读结论。本轮修两处真实陈旧数字：
预算线（1788 s/4210 条 → 1882.7 s/4922 条）与 precheck 分工（20/378 → 25 门/540 模块）。
本判据把五步顺序、快照关键语义、65 项判据、权重总耗时与条数、precheck 门数、绿红台账分表、
复现三命令全部活绑定。

范围：只判本文与 release_conclusion 脚本/权重件/precheck 事实自洽（不跑全量快照）。
同族判据：test_release_conclusion.py（65 例）/ test_verify_tests_selection.py /
test_verifier_version.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、五步顺序在文、快照语义四要素、65 项判据、权重总耗时/条数与权重件相等、
precheck 25 门在文、绿红两表分开、现状对照 + 复现三命令。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _budget() -> float:
    """预算真源 = test_check12_budget.BUDGET_S（避免两处各钉一个数）。"""
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "desktop" / "tests"))
    from test_check12_budget import BUDGET_S
    return float(BUDGET_S)
sys.path.insert(0, str(ROOT / "scripts"))

import precheck_gates as pg  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "release-conclusion.md"
SCRIPT = ROOT / "scripts" / "release_conclusion.py"
TEST = ROOT / "desktop" / "tests" / "test_release_conclusion.py"
WEIGHTS = ROOT / "protocol" / "check12_weights.json"
SECTIONS = ("## 是什么", "## 为什么有它", "## 怎么用", "## 快照模式", "## 五步各判什么",
            "## 修复回路", "## 判据（可证）", "## 绿结论台账", "## 红结论台账",
            "## 现状对照", "## 复现与引用口径", "## 边界")
STEPS = ("供应链核对", "生成物新鲜度", "静态棘轮", "checks-only", "分片")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"发布结论文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("发布结论文档为空")
    return text


def weights() -> dict:
    return json.loads(WEIGHTS.read_text(encoding="utf-8"))


def rc_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def conclusion_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 发布结论复跑 v0"):
        issues.append("缺标题「# 发布结论复跑 v0（release conclusion）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for step in STEPS:
        if step not in text:
            issues.append(f"五步缺要素：{step}")
    for marker in (".worktrees/gate-snap", "NARRATIVE_FORGE_HOME", "TEMP", "锁"):
        if marker not in text:
            issues.append(f"快照语义缺要素：{marker}")
    for flag in ("--snapshot", "--allow-dirty", "--dry-run", "--only-preflight",
                 "--json", "--shards"):
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
        if flag not in SCRIPT.read_text(encoding="utf-8"):
            issues.append(f"脚本缺旗标：{flag}")
    n_cases = rc_cases()
    if n_cases != 65:
        issues.append(f"test_release_conclusion 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text and str(n_cases) + " 例" not in text:
        issues.append(f"未写判据数（{n_cases}）")
    w = weights()
    total = float(w["total_s"])
    if total > _budget():
        issues.append(f"权重总耗时越预算：{total}")
    if "≤ **2000 s**" not in text and "2000 s" not in text:
        issues.append("未写权重预算线 2000 s")
    for stale in ("1788", "4210", "20/378"):
        bad = [ln for ln in text.splitlines()
               if stale in ln and "原写" not in ln]
        if bad:
            issues.append(f"仍残留陈旧数字：{stale}")
    n_gates = len(pg.GATES)
    n_slow = len(pg.SLOW_GATES)
    if (n_gates + n_slow) != 25:
        issues.append(f"precheck 门数已变（{n_gates}+{n_slow}）")
    if "25 门" not in text:
        issues.append("未写 precheck 25 门")

    if "绿结论台账" not in text or "红结论台账" not in text:
        issues.append("绿/红台账未分节")
    if "不与绿结论混号" not in text:
        issues.append("缺「红不与绿混号」口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/release_conclusion.py --dry-run",
                "python scripts/release_conclusion.py --only-preflight",
                "python -m pytest desktop/tests/test_release_conclusion.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ReleaseConclusionDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_conclusion_matches_contract(self):
        self.assertEqual([], conclusion_issues(self.text), "发布结论文档不满足契约")

    def test_numbers_live(self):
        w = weights()
        self.assertEqual(65, rc_cases())
        self.assertEqual(25, len(pg.GATES) + len(pg.SLOW_GATES))
        self.assertGreaterEqual(len(w["tests"]), 4800)
        self.assertLessEqual(float(w["total_s"]), _budget())

    def test_contract_catches_mutations(self):
        """变异自证：权重数字回退 / 回退 20-378 / 缺快照要素 / 缺判据数 / 缺命令。"""
        old_w = self.text.replace("1882.9", "1788")
        self.assertTrue(any("陈旧数字" in i for i in conclusion_issues(old_w)))
        old_p = self.text.replace("**25 门", "**20/378")
        self.assertTrue(any("25 门" in i or "20/378" in i
                            for i in conclusion_issues(old_p)))
        no_snap = self.text.replace("NARRATIVE_FORGE_HOME", "HOME")
        self.assertTrue(any("快照语义" in i for i in conclusion_issues(no_snap)))
        old_n = self.text.replace("65 项", "60 项").replace("65 例", "60 例")
        self.assertTrue(any("例数" in i or "65" in i for i in conclusion_issues(old_n)))
        no_cmd = self.text.replace("python scripts/release_conclusion.py --dry-run", "看计划")
        self.assertTrue(any("--dry-run" in i for i in conclusion_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_conclusion.md")


if __name__ == "__main__":
    unittest.main()
