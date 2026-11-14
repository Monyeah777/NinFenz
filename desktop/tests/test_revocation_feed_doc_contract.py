#!/usr/bin/env python3
"""docs/ccos/revocation-feed-v0.md 契约：吊销 feed 文档必须「五子命令/链深/判据数与实现一致」。

为什么必须有：这份文档是威胁模型 G2 的落地口径——feed 形状、签名方案（hmac + ed25519）、
信任锚链深、新鲜度三档，任何一项漂移都会让「来源/回滚可判」这个承诺失真。本轮修的真实缺陷是
**文末边界与上文自相矛盾**（上文已实装 ed25519，文末仍说「吊销件还没走那条线」）。本判据把
五子命令、MAX_DEPTH=2、43+16 项判据、签名/digest 口径、新鲜度优先级全部活绑定。

范围：只判本文与 revocations/trust_anchor 实现事实自洽（不改协议）。同族判据：
test_revocations.py（43 例）/ test_trust_anchor.py（16 例）/ test_ed25519.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、五子命令在 CLI 且在文、MAX_DEPTH=2 与文档「2 级」一致、43+16 例、
ed25519 段在文、旧矛盾措辞缺席、新鲜度优先级在文、现状对照 + 复现三命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import trust_anchor  # noqa: E402

DOC = ROOT / "docs" / "ccos" / "revocation-feed-v0.md"
NF = ROOT / "scripts" / "nf.py"
TEST = ROOT / "desktop" / "tests" / "test_revocations.py"
TRUST = ROOT / "desktop" / "tests" / "test_trust_anchor.py"
SUBS = ("sign", "pubkey", "verify", "trust", "merge")
SECTIONS = ("## 解决什么", "## 形状", "## 怎么用", "## 判定（可证）", "## 新鲜度",
            "## 边界", "## 现状对照", "## 复现与引用口径", "## 复核")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"吊销 feed 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("吊销 feed 文档为空")
    return text


def case_count(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("def test")


def feed_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 吊销分发件 v0"):
        issues.append("缺标题「# 吊销分发件 v0（nf-revocation-feed/1）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    nf = NF.read_text(encoding="utf-8")
    for sub in SUBS:
        if 'add_parser("' + sub + '"' not in nf:
            issues.append(f"CLI 缺子命令：{sub}")
        if sub not in text:
            issues.append(f"正文缺子命令：{sub}")
    if trust_anchor.MAX_DEPTH != 2:
        issues.append(f"MAX_DEPTH 已变：{trust_anchor.MAX_DEPTH}")
    if "2 级" not in text:
        issues.append("未写「2 级委派」")
    n_rev = case_count(TEST)
    n_trust = case_count(TRUST)
    if n_rev != 43:
        issues.append(f"test_revocations 例数已变（{n_rev}）")
    if n_trust != 16:
        issues.append(f"test_trust_anchor 例数已变（{n_trust}）")
    for label in ("43 项", "16 项"):
        if label not in text:
            issues.append(f"未写判据数：{label}")
    if "ed25519" not in text:
        issues.append("缺 ed25519 方案段")
    legit = ("原写", "旧边界", "文末「")
    bad = [ln for ln in text.splitlines()
           if "还没走那条线" in ln and not any(k in ln for k in legit)]
    if bad:
        issues.append("仍写「吊销件还没走那条线」（与已实装 ed25519 矛盾）")
    for marker in ("nf-revocation-feed/1", "prev_digest", "issued_at", "seq"):
        if marker not in text:
            issues.append(f"形状缺要素：{marker}")
    for marker in ("require-fresh-revocations", "revoked > expired",
                   "完全没有吊销来源"):
        if marker not in text:
            issues.append(f"新鲜度口径缺要素：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("nf evidence revocations verify",
                "nf evidence revocations merge",
                "python -m pytest desktop/tests/test_revocations.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class RevocationFeedDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_feed_doc_matches_contract(self):
        self.assertEqual([], feed_issues(self.text), "吊销 feed 文档不满足契约")

    def test_implementation_live(self):
        self.assertEqual(2, trust_anchor.MAX_DEPTH)
        self.assertEqual(43, case_count(TEST))
        self.assertEqual(16, case_count(TRUST))
        nf = NF.read_text(encoding="utf-8")
        for sub in SUBS:
            self.assertIn('add_parser("' + sub + '"', nf)

    def test_contract_catches_mutations(self):
        """变异自证：回退旧矛盾 / 缺子命令 / 缺 2 级 / 例数漂移 / 缺复现命令。"""
        back = self.text + "\n吊销件还没走那条线。\n"
        self.assertTrue(any("还没走那条线" in i for i in feed_issues(back)))
        no_sub = self.text.replace("pubkey", "pkey")
        self.assertTrue(any("pubkey" in i for i in feed_issues(no_sub)))
        no_depth = self.text.replace("2 级", "3 级")
        self.assertTrue(any("2 级" in i or "MAX_DEPTH" in i
                            for i in feed_issues(no_depth)))
        old_n = self.text.replace("43 项", "40 项")
        self.assertTrue(any("43 项" in i or "例数" in i for i in feed_issues(old_n)))
        no_cmd = self.text.replace("nf evidence revocations merge", "合并")
        self.assertTrue(any("merge" in i for i in feed_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_feed.md")


if __name__ == "__main__":
    unittest.main()
