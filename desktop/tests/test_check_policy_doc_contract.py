#!/usr/bin/env python3
"""docs/ccos/check-policy-v0.md 契约：单对象策略规范必须「5 类封闭词表/形状/CLI 五入口与实现一致」。

为什么必须有：这份规范定义「判据即数据」的最小单元——词表、字段、verdict 两态、policy_digest、
坏策略拒绝都是稳定面。旧版只写 --policy/--compile/--list-rules，漏了 --intent-from-text
（法规原文→意图草稿，四张账）；且 19 项判据数要与测试实读一致。本轮补复核位、文本层小节、
现状对照与复现口径，并把词表/字段/旗标/例数/四账立成机检断言。

范围：只判本文与 check_policy 实现/测试事实自洽（不改词表）。同族判据：
test_check_policy.py（19 例）/ 草稿层测试 / test_ccos_abi_docs.py（ABI §2 联动）/
test_doc_hygiene.py / test_doc_examples.py。
契约：⛔ 标识 + last-updated + 复核位、5 类词表逐项、策略字段行、CLI 五入口在册、
verdict 两态 + exit 0/1/2、policy_digest、四账在文、19 例判据、现状对照与复现五命令。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import check_policy  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "check-policy-v0.md"
NF = ROOT / "scripts" / "nf.py"
TEST = ROOT / "desktop" / "tests" / "test_check_policy.py"
DRAFT_MOD = ROOT / "desktop" / "src" / "core" / "check_text_to_intent.py"
SECTIONS = ("## 是什么", "## 策略形状", "## 意图编译器", "## 判定", "## 怎么用", "## 判据",
            "## 现状对照", "## 复现与引用口径", "## 边界")
KINDS = ("utf8", "regex_present", "regex_absent", "count_at_least", "digest_pin")
FLAGS = ("--policy", "--json", "--compile", "--list-rules", "--intent-from-text")
ACCOUNTS = ("covered", "pending", "unsupported", "uncovered")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"check-policy 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("check-policy 文档为空")
    return text


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def policy_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 单对象策略体检 v0"):
        issues.append("缺标题「# 单对象策略体检 v0（check policy）」")
    if "⛔ 操作指令" not in text:
        issues.append("缺「⛔ 操作指令」标识")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核（2026-11-13）" not in text:
        issues.append("缺「复核（2026-11-13）」位")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if tuple(check_policy.KINDS) != KINDS:
        issues.append(f"实现词表已变：{check_policy.KINDS}")
    for kind in KINDS:
        if kind not in text:
            issues.append(f"正文缺词表项：{kind}")
    for field in ("id", "kind", "severity", "fix", "pattern", "sha256"):
        if field not in text:
            issues.append(f"策略字段缺：{field}")
    nf = NF.read_text(encoding="utf-8")
    for flag in FLAGS:
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    for word in ("ok", "invalid", "warn"):
        if word not in text:
            issues.append(f"判定词缺：{word}")
    if "policy_digest" not in text:
        issues.append("缺 policy_digest")
    if "nf-check-intent-draft/1" not in text:
        issues.append("缺意图草稿 schema（nf-check-intent-draft/1）")
    if "SCHEMA" not in DRAFT_MOD.read_text(encoding="utf-8"):
        issues.append("草稿模块缺 SCHEMA 常量")
    for acct in ACCOUNTS:
        if acct not in text:
            issues.append(f"四张账缺：{acct}")
    n_cases = case_count()
    if n_cases != 19:
        issues.append(f"test_check_policy 例数已变（{n_cases}）")
    if str(n_cases) + " 项" not in text and str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases}）")
    for cmd in ("python scripts/nf.py check --list-rules",
                "python scripts/nf.py check --compile intent.json --out policy.json",
                "python scripts/nf.py check 01_核心协议.md --policy policy.json --json",
                "python scripts/nf.py check --intent-from-text",
                "python -m pytest desktop/tests/test_check_policy.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不判内容质量" not in text and "不判内容好不好" not in text:
        issues.append("缺「不判内容质量」边界")
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    if "TODO" in prose or "待补" in prose:
        issues.append("含 TODO/待补 占位")
    return issues


class CheckPolicyDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_policy_matches_contract(self):
        self.assertEqual([], policy_issues(self.text), "check-policy 文档不满足契约")

    def test_kinds_flags_cases_live(self):
        self.assertEqual(KINDS, tuple(check_policy.KINDS))
        self.assertEqual(19, case_count())
        nf = NF.read_text(encoding="utf-8")
        for flag in FLAGS:
            self.assertIn('"' + flag + '"', nf)

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 缺词表项 / 缺草稿层 / 缺四账 / 例数漂移 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in policy_issues(no_date)))
        no_kind = self.text.replace("digest_pin", "digest_fixed")
        self.assertTrue(any("digest_pin" in i for i in policy_issues(no_kind)))
        no_draft = self.text.replace("nf-check-intent-draft/1", "意图草稿")
        self.assertTrue(any("草稿 schema" in i for i in policy_issues(no_draft)))
        no_acct = self.text.replace("uncovered", "未覆盖")
        self.assertTrue(any("四张账" in i for i in policy_issues(no_acct)))
        old_n = self.text.replace("19 项", "17 项").replace("19 例", "17 例")
        self.assertTrue(any("例数" in i or "19" in i for i in policy_issues(old_n)))
        no_cmd = self.text.replace("python scripts/nf.py check --list-rules", "看词表")
        self.assertTrue(any("--list-rules" in i for i in policy_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_policy.md")


if __name__ == "__main__":
    unittest.main()
