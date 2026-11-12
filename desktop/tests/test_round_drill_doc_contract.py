#!/usr/bin/env python3
"""docs/45_M2 契约：回合级 drill 规范必须「判据不变 + 样本集/测试现状 + 轨迹回读口径 + 复现命令」。

为什么必须有：这是回合级断言的指令档——它写「样本集 5 份 / 独立 scan + --check --rounds」；现行样本
已 6 份（含真实语料自跑 selfrun-2026-10-20.json）、常驻判据 6 例，且 --check-trace 回读有
「trace 必须带 --rounds」的 exit 2 口径。不标这些，读者会少跑真实样本、或把 exit 2 当通过。
本轮补状态横幅、样本集更新、回读口径、现状对照与复现命令，并把判据/样本/测试/CLI 参数立成断言。

范围：只判本文与 round_drill/测试/CLI 事实自洽（不改判据）。同族判据：
test_round_drill.py（6 例）/ test_m2_round_header_contract.py（状态头）/
test_doc_hygiene.py（指令档标识）/ test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated、用途 + 调用 + 标记约定 + 现状对照 + 复现口径、
R-R1–R-R4 在文且 round_drill 含同名注释、样本 6 份在文且文件在场、测试 6 例、
CLI --rounds/--check-trace 参数在册、exit 2「未执行漂移断言」口径、历史 5 份快照保留。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import round_drill as rd  # noqa: E402

DOC = ROOT / "docs" / "45_M2_回合级drill.md"
MOD = ROOT / "desktop" / "src" / "core" / "round_drill.py"
TEST = ROOT / "desktop" / "tests" / "test_round_drill.py"
ROUNDS = ROOT / "desktop" / "tests" / "fixtures" / "execution" / "rounds"
NF = ROOT / "scripts" / "nf.py"
SECTIONS = ("## 用途", "## 调用", "## 转录标记约定", "## 现状对照", "## 复现与引用口径")
FIXTURES = ("good.json", "bad.json", "bad_r2.json", "bad_r3.json", "gap_ok.json",
            "selfrun-2026-10-20.json")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"回合级 drill 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("回合级 drill 文档为空")
    return text


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def drill_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 45 A2 · 回合级 drill"):
        issues.append("缺标题「# 45 A2 · 回合级 drill」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "回合级断言口径沿用" not in text:
        issues.append("缺「回合级断言口径沿用」状态声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    mod = MOD.read_text(encoding="utf-8")
    for rule in ("R-R1", "R-R2", "R-R3", "R-R4"):
        if rule not in text:
            issues.append(f"正文缺判据：{rule}")
        if rule not in mod:
            issues.append(f"round_drill 缺判据注释：{rule}")
    for name in FIXTURES:
        if not (ROUNDS / name).is_file():
            issues.append(f"样本缺失：rounds/{name}")
    if "selfrun-2026-10-20.json" not in text:
        issues.append("未写真实语料样本 selfrun-2026-10-20.json")
    if "6 份" not in text:
        issues.append("未写现行样本份数（6 份）")
    if str(case_count()) + " 例" not in text:
        issues.append(f"未写常驻测试例数（{case_count()} 例）")
    if case_count() != 6:
        issues.append(f"test_round_drill 例数已变（{case_count()}）")
    nf = NF.read_text(encoding="utf-8")
    for flag in ("--rounds", "--check-trace"):
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺参数：{flag}")
    for marker in ("--check-trace", "--rounds", "未执行漂移断言"):
        if marker not in text:
            issues.append(f"回读口径缺要素：{marker}")
    if "5 份" not in text:
        issues.append("历史样本数快照（5 份）被改写")
    for cmd in ("python scripts/nf.py assemble --help",
                "python -m pytest desktop/tests/test_round_drill.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class RoundDrillDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_round_drill_doc_matches_contract(self):
        self.assertEqual([], drill_issues(self.text), "回合级 drill 文档不满足契约")

    def test_fixtures_and_rules_live(self):
        for name in FIXTURES:
            self.assertTrue((ROUNDS / name).is_file(), name)
        self.assertEqual(6, case_count())
        self.assertTrue(hasattr(rd, "scan"))

    def test_contract_catches_mutations(self):
        """变异自证：去标识 / 判据缺失 / 样本回退 / 例数漂移 / 缺回读口径 / 缺复现命令。"""
        no_marker = self.text.replace("⛔ 操作指令", "操作指令")
        self.assertTrue(any("⛔" in i for i in drill_issues(no_marker)))
        no_rule = self.text.replace("R-R4", "R-R9")
        self.assertTrue(any("R-R4" in i for i in drill_issues(no_rule)))
        old_samples = self.text.replace("**6 份**", "**5 份**")
        self.assertTrue(any("selfrun" in i or "6 份" in i
                            for i in drill_issues(old_samples)))
        wrong = self.text.replace("6 例", "3 例")
        self.assertTrue(any("例数" in i or "6 例" in i for i in drill_issues(wrong)))
        no_trace = self.text.replace("--check-trace", "--trace")
        self.assertTrue(any("--check-trace" in i for i in drill_issues(no_trace)))
        no_cmd = self.text.replace("python -m pytest desktop/tests/test_round_drill.py",
                                   "跑测试")
        self.assertTrue(any("test_round_drill" in i for i in drill_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_round_drill.md")


if __name__ == "__main__":
    unittest.main()
