#!/usr/bin/env python3
"""docs/42_M5_设计自查清单契约：六问必须「口径不变 + 每问有判据映射 + 证据命令可跑」。

为什么必须有：设计自查清单原来只有「问什么」，没有「证据在哪」——收口时容易变成主观打勾。
本轮把六问逐条映射到机检（check15/16/23/37、module contract/signature、patterns verify、
LAYERS.json）并给出复现命令。判据要保证：六问在场、每条映射的判据号与载体在仓库里真实存在、
命名（check15/16/23/37）仍在 verify.sh、模块面 13 件仍成立——避免「映射到空气」。

范围：只判本文与判据/载体事实自洽（不改六问口径）。同族判据：
test_doc_hygiene.py（文档卫生）/ test_doc_examples.py（命令块）/
test_m5_closure_contract.py（M5 邻档）/ verify.sh（check15/16/23/37 真源）。
契约：状态横幅、六问行、判据映射表（每条含判据号/载体）、现状对照、复现四命令、
check1-42 现行门禁规模、check37 脚本含 verify_reuse。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "42_M5_设计自查清单.md"
VERIFY = ROOT / "verify.sh"
CHECK37 = ROOT / "scripts" / "check37_knowledge.py"
NF = ROOT / "scripts" / "nf.py"
MODULES = ROOT / "04_模块库"
SECTIONS = ("## 判据映射", "## 现状对照", "## 复现与引用口径")
PRINCIPLES = ("单一职责", "开闭原则", "无重复", "单一真相源", "最小必要", "组合优于继承")
MAPPINGS = ("check16", "check15", "check37", "check23", "check27",
            "module contract", "module signature", "patterns verify", "LAYERS.json")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"设计自查清单不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("设计自查清单为空")
    return text


def module_count() -> int:
    return len(list(MODULES.glob("*/*.md")))


def design_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M5.5 · 设计原则自查清单"):
        issues.append("缺标题「# 42 M5.5 · 设计原则自查清单」")
    if "状态：六问口径不变" not in text:
        issues.append("缺「六问口径不变」状态声明")
    for principle in PRINCIPLES:
        if principle not in text:
            issues.append(f"缺原则：{principle}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for marker in MAPPINGS:
        if marker not in text:
            issues.append(f"判据映射缺要素：{marker}")
    verify = VERIFY.read_text(encoding="utf-8")
    for check in ("check15", "check16", "check23", "check37"):
        if check not in verify:
            issues.append(f"verify.sh 缺判据：{check}")
    if "verify_reuse" not in CHECK37.read_text(encoding="utf-8"):
        issues.append("check37 脚本缺 verify_reuse（DRY 映射失效）")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("module", "patterns", "explain", "conformance"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    if "check1-42" not in text:
        issues.append("未写现行门禁规模（check1-42）")
    if module_count() != 13:
        issues.append(f"官方核心模块数已变（{module_count()}）：映射表需复核")
    for cmd in ("python scripts/nf.py module signature --json",
                "python scripts/nf.py explain check15",
                "python scripts/nf.py explain check37",
                "python scripts/nf.py conformance"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class DesignChecklistContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_design_list_matches_contract(self):
        self.assertEqual([], design_issues(self.text), "设计自查清单不满足契约")

    def test_mappings_are_live(self):
        verify = VERIFY.read_text(encoding="utf-8")
        for check in ("check15", "check16", "check23", "check37"):
            self.assertIn(check, verify)
        self.assertIn("verify_reuse", CHECK37.read_text(encoding="utf-8"))
        self.assertEqual(13, module_count())

    def test_contract_catches_mutations(self):
        """变异自证：去状态 / 缺原则 / 映射缺失 / 判据号回退 / 缺现状对照 / 缺复现命令。"""
        no_status = self.text.replace("状态：六问口径不变", "状态：旧版")
        self.assertTrue(any("六问口径不变" in i for i in design_issues(no_status)))
        no_principle = self.text.replace("最小必要", "按需")
        self.assertTrue(any("最小必要" in i for i in design_issues(no_principle)))
        no_map = self.text.replace("check37", "某判据")
        self.assertTrue(any("check37" in i for i in design_issues(no_map)))
        old_gate = self.text.replace("check1-42", "check1-27")
        self.assertTrue(any("check1-42" in i for i in design_issues(old_gate)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in design_issues(no_sec)))
        no_cmd = self.text.replace("python scripts/nf.py conformance", "跑一致性")
        self.assertTrue(any("conformance" in i for i in design_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_design_list.md")


if __name__ == "__main__":
    unittest.main()
