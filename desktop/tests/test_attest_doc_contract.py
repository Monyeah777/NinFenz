#!/usr/bin/env python3
"""docs/attest.md 契约：内容 attestation 文档必须「三级语义 + 六旗标 + 库签名边界 + 现状活绑定」。

为什么必须有：这是「证据强度」层的操作规范——文档列 4 个旗标，实际有 6 个（漏了 --selfcheck 与
--json；前者是 check42 的用户侧入口，语义是「体检外部验签机制 + 篡改必红」）；且 nf library attest
（库条目 SSH 签名锚）与本文三级（内容信封）不是同一层，不写边界容易被混称。本轮补旗标表、边界、
现状对照与复现口径，并把三级值/六旗标/check42/9 例立成机检断言。

范围：只判本文与 attest 实现/判据事实自洽（不改三级机制）。同族判据：
test_attest.py（9 例）/ 库签名相关测试 / test_doc_hygiene.py /
test_doc_examples.py（命令块）。
契约：⛔ 标识 + last-updated + 复核位、三级值在文且与实现常量一致、六旗标在册、
selfcheck 语义（独立子进程/篡改必红/check42）、库签名边界段、9 例判据、复现三命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import attest as core_attest  # noqa: E402

DOC = ROOT / "docs" / "attest.md"
NF = ROOT / "scripts" / "nf.py"
VERIFY = ROOT / "verify.sh"
TEST = ROOT / "desktop" / "tests" / "test_attest.py"
SECTIONS = ("## 为什么有这一层", "## 三级信任", "## 用法", "## 与门禁的关系",
            "## 现状对照", "## 复现与引用口径")
FLAGS = ("--out", "--issuer", "--key-file", "--verify", "--selfcheck", "--json")
LEVELS = ("digest_only", "hmac-sha256", "sigstore-keyless")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"attest 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("attest 文档为空")
    return text


def case_count() -> int:
    return TEST.read_text(encoding="utf-8").count("def test")


def attest_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 内容 attestation"):
        issues.append("缺标题「# 内容 attestation（nf attest）」")
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
    for level in LEVELS:
        if level not in text:
            issues.append(f"正文缺信任级：{level}")
    if getattr(core_attest, "SCHEME_HMAC", None) != "hmac-sha256":
        issues.append("实现常量 SCHEME_HMAC 已变")
    if getattr(core_attest, "SCHEME_SIGSTORE", None) != "sigstore-keyless":
        issues.append("实现常量 SCHEME_SIGSTORE 已变")
    nf = NF.read_text(encoding="utf-8")
    for flag in FLAGS:
        if '"' + flag + '"' not in nf:
            issues.append(f"CLI 缺旗标：{flag}")
        if flag not in text:
            issues.append(f"正文缺旗标：{flag}")
    for marker in ("独立子进程", "篡改必红", "check42"):
        if marker not in text:
            issues.append(f"selfcheck 语义缺要素：{marker}")
    if "check42" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 缺 check42（selfcheck 入口引用失效）")
    if "library attest" not in text:
        issues.append("缺库条目签名边界（nf library attest）")
    if "另一层" not in text and "不是同一层" not in text:
        issues.append("缺「库签名与三级不是同一层」边界")
    if "不降级" not in text and "不静默降级" not in text:
        issues.append("缺「缺锚即拒绝、不降级」口径")
    n_cases = case_count()
    if n_cases != 9:
        issues.append(f"test_attest 例数已变（{n_cases}）")
    if str(n_cases) + " 例" not in text:
        issues.append(f"未写常驻判据例数（{n_cases} 例）")
    for cmd in ("python scripts/nf.py attest --selfcheck",
                "python scripts/nf.py attest --json",
                "python -m pytest desktop/tests/test_attest.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class AttestDocContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_attest_matches_contract(self):
        self.assertEqual([], attest_issues(self.text), "attest 文档不满足契约")

    def test_levels_and_flags_live(self):
        self.assertEqual("hmac-sha256", core_attest.SCHEME_HMAC)
        self.assertEqual("sigstore-keyless", core_attest.SCHEME_SIGSTORE)
        nf = NF.read_text(encoding="utf-8")
        for flag in FLAGS:
            self.assertIn('"' + flag + '"', nf)
        self.assertEqual(9, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：去复核位 / 缺级 / 缺 selfcheck / 缺边界 / 缺 check42 / 缺命令。"""
        no_date = self.text.replace("复核（2026-11-13）", "说明")
        self.assertTrue(any("复核（2026-11-13）" in i for i in attest_issues(no_date)))
        no_level = self.text.replace("sigstore-keyless", "sigstore")
        self.assertTrue(any("sigstore-keyless" in i for i in attest_issues(no_level)))
        no_flag = self.text.replace("--selfcheck", "--check")
        self.assertTrue(any("--selfcheck" in i for i in attest_issues(no_flag)))
        no_bound = self.text.replace("library attest", "库签名").replace("另一层", "同层")
        self.assertTrue(any("library attest" in i or "边界" in i
                            for i in attest_issues(no_bound)))
        no_check = self.text.replace("check42", "某 check")
        self.assertTrue(any("check42" in i for i in attest_issues(no_check)))
        no_cmd = self.text.replace("python scripts/nf.py attest --json", "看信封")
        self.assertTrue(any("--json" in i for i in attest_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_attest.md")


if __name__ == "__main__":
    unittest.main()
