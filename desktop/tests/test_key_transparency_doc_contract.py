#!/usr/bin/env python3
"""docs/ccos/key-transparency-v0.md 契约：四子命令真实存在 + 形状/边界活绑定。

为什么必须有：这份规范是「发现分叉」的承诺——它的 CLI 子命令名与形状不变量必须真实。本轮修的真实
缺陷正是 CLI 引用失效：原文写 kt-build/kt-verify/kt-witness，其中 kt-witness 根本不存在（真实第 4 个
是 kt-split，kt-lookup 也没列）。读者照文操作会报 invalid choice。
本判据把四个真实子命令、15 例判据、
叶/根/链/版本四条不变量、三条「不做」边界全部活绑定。

范围：只判本文与 key_transparency 实现/CLI 事实自洽（不改协议）。同族判据：
test_key_transparency.py（15 例）/ test_revocation_feed*.py（信任锚）/ test_evidence.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：状态/实现位置行 + 最后更新位 + 复核、四子命令在 CLI 且在文、**无 kt-witness**、15 例判据、
叶 0x00 / RFC6962 根 / prev 链 / version==len(log) 四不变量、不做项三条、现状对照 + 复现四命令。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "ccos" / "key-transparency-v0.md"
NF = ROOT / "scripts" / "nf.py"
CORE = ROOT / "desktop" / "src" / "core" / "key_transparency.py"
TEST = ROOT / "desktop" / "tests" / "test_key_transparency.py"
SUBS = ("kt-build", "kt-verify", "kt-lookup", "kt-split")
SECTIONS = ("## 解决什么", "## 形状", "## 用法", "## 判定（可证）", "## 现状对照",
            "## 边界（诚实写清）", "## 判据（自证）", "## 复现与引用口径",
            "## 与既有件的关系")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"密钥透明目录文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("密钥透明目录文档为空")
    return text


def kt_cases() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def kt_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 密钥透明目录 v0"):
        issues.append("缺标题「# 密钥透明目录 v0（nf-key-transparency/1）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    if "已实装" not in text:
        issues.append("缺实装状态")
    if "desktop/src/core/key_transparency.py" not in text:
        issues.append("缺实现位置")
    nf = NF.read_text(encoding="utf-8")
    for sub in SUBS:
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"CLI 缺子命令：{sub}")
        if sub not in text:
            issues.append(f"正文缺子命令：{sub}")
    legit = ("不存在", "已修正", "失效引用")
    bad = [ln for ln in text.splitlines()
           if "kt-witness" in ln and not any(k in ln for k in legit)]
    if bad:
        issues.append("仍把不存在的 kt-witness 当子命令引用")
    for inv in ("0x00", "RFC 6962", "log[i].prev", "len(log)", "version"):
        if inv not in text:
            issues.append(f"形状不变量缺要素：{inv}")
    for na in ("前缀树", "abridged proof", "隐私"):
        if na not in text:
            issues.append(f"不做项缺：{na}")
    if "外部锚或审计者" not in text and "外部锚" not in text:
        issues.append("缺「发现分叉≠裁决谁对」边界")
    n_cases = kt_cases()
    if n_cases != 15:
        issues.append(f"test_key_transparency 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text and str(n_cases) + " 项" not in text:
        issues.append(f"未写判据数（{n_cases}）")
    if not CORE.is_file():
        issues.append("缺实现件 key_transparency.py")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("nf evidence revocations trust kt-build",
                "nf evidence revocations trust kt-verify",
                "nf evidence revocations trust kt-lookup",
                "nf evidence revocations trust kt-split"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class KeyTransparencyDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_kt_matches_contract(self):
        self.assertEqual([], kt_issues(self.text), "密钥透明目录文档不满足契约")

    def test_kt_live(self):
        nf = NF.read_text(encoding="utf-8")
        for sub in SUBS:
            self.assertIn('add_parser("' + sub + '"', nf)
        self.assertNotIn('add_parser("kt-witness"', nf)
        self.assertTrue(CORE.is_file())
        self.assertEqual(15, kt_cases())

    def test_contract_catches_mutations(self):
        """变异自证：回退 kt-witness / 缺子命令 / 缺不变量 / 缺判据数 / 缺复现命令。"""
        bad = self.text + "\nCLI：nf evidence revocations trust kt-witness\n"
        self.assertTrue(any("kt-witness" in i for i in kt_issues(bad)))
        no_sub = self.text.replace("kt-lookup", "kt-find")
        self.assertTrue(any("kt-lookup" in i for i in kt_issues(no_sub)))
        no_inv = self.text.replace("RFC 6962", "merkle")
        self.assertTrue(any("RFC 6962" in i for i in kt_issues(no_inv)))
        no_na = self.text.replace("前缀树", "树")
        self.assertTrue(any("前缀树" in i for i in kt_issues(no_na)))
        no_n = self.text.replace("15 例", "9 例").replace("15 项", "9 项")
        self.assertTrue(any("例数" in i or "15" in i for i in kt_issues(no_n)))
        no_cmd = self.text.replace("nf evidence revocations trust kt-split", "kt 分叉")
        self.assertTrue(any("kt-split" in i for i in kt_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_kt.md")


if __name__ == "__main__":
    unittest.main()
