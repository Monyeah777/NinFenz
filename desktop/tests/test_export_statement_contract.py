#!/usr/bin/env python3
"""docs/EXPORT.md 契约：出口管制声明必须「署名声明与仓库密码学事实一致 + 机检面 + 复现口径」。

为什么必须有：这是一份**对外声明**——旧版写「本仓库不自制 ed25519 或任何密码算法」，但 2026-11-07
起仓库确有 RFC 8032 Ed25519 的纯标准库自写实现（core/ed25519.py）。对外声明的错误表述是合规
风险：读者会据此误判实现面。本轮修正表述（标准公开算法 + 纯标准库 + 不引入第三方密码库 +
可外调 ssh-keygen），并补「声明 ⇄ 机检面」对照与复现命令；判据要防的正是「声明重新漂移回旧说法」。

范围：只判本文与密码学面事实自洽（不做法律判断）。同族判据：
test_ed25519.py（12 例）/ test_doc_reachability.py（指引旗标可达）/ test_doc_hygiene.py。
契约：最后复核位、**不再出现「不自制 ed25519」旧表述**、明示自写 RFC 8032 实现与纯标准库、
ssh-keygen 外调路径、anchors 在场、EAR 段落与「不构成法律意见」保留、声明⇄机检面对照表、
复现三命令、签名字面旗标可达（library attest --ssh-key）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

DOC = ROOT / "docs" / "EXPORT.md"
ED25519 = ROOT / "desktop" / "src" / "core" / "ed25519.py"
ED_TEST = ROOT / "desktop" / "tests" / "test_ed25519.py"
ANCHORS = ROOT / "library" / "anchors"
ATTEST = ROOT / "desktop" / "src" / "core" / "attest.py"
SECTIONS = ("## 声明与仓库事实对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"EXPORT 声明不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("EXPORT 声明为空")
    return text


def case_count() -> int:
    return ED_TEST.read_text(encoding="utf-8").count("def test")


def export_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 出口管制声明"):
        issues.append("缺标题「# 出口管制声明（Export Control）」")
    if "最后复核" not in text:
        issues.append("缺「最后复核」位")
    body = text
    if "**修正（2026-11-13）**" in body:
        start = body.index("**修正（2026-11-13）**")
        end = body.find("\n\n", start)
        if end > 0:
            body = body[:start] + body[end:]
    if "不自制 ed25519" in body:
        issues.append("仍出现「不自制 ed25519」式表述（与仓库事实不符）")
    for marker in ("RFC 8032", "标准库", "ed25519.py", "ssh-keygen", "anchors"):
        if marker not in text:
            issues.append(f"声明缺事实要素：{marker}")
    if "不构成法律意见" not in text:
        issues.append("缺「不构成法律意见」免责语")
    if "EAR" not in text:
        issues.append("缺 EAR 通行读法段落")
    if "第三方密码库" not in text:
        issues.append("缺「不引入第三方密码库」口径")
    if not ED25519.is_file():
        issues.append("缺实现件 core/ed25519.py（声明失真）")
    if "hashlib" not in ED25519.read_text(encoding="utf-8"):
        issues.append("ed25519 实现非标准库依赖（声明失真）")
    if not ANCHORS.is_dir() or not list(ANCHORS.glob("*.sig")):
        issues.append("缺 library/anchors/*.sig（声明失真）")
    if "ssh-keygen" not in ATTEST.read_text(encoding="utf-8"):
        issues.append("attest.py 缺 ssh-keygen 外调（声明失真）")
    if case_count() != 12:
        issues.append(f"test_ed25519 例数已变（{case_count()}）")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py attest --help",
                "python -m pytest desktop/tests/test_ed25519.py",
                "python scripts/nf.py explain check27"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "library attest <编号> --ssh-key" not in text and "library attest" not in text:
        issues.append("缺 library attest --ssh-key 可达写法")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ExportStatementContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_export_matches_contract(self):
        self.assertEqual([], export_issues(self.text), "EXPORT 声明不满足契约")

    def test_crypto_facts_live(self):
        self.assertTrue(ED25519.is_file())
        self.assertIn("hashlib", ED25519.read_text(encoding="utf-8"))
        self.assertTrue(list(ANCHORS.glob("*.sig")))
        self.assertEqual(12, case_count())

    def test_contract_catches_mutations(self):
        """变异自证：回退旧表述 / 去实现 / 去免责 / 缺机检面 / 缺命令 / 缺 ssh-key。"""
        old = self.text + "\n\n本仓库不自制 ed25519 或任何密码算法。\n"
        self.assertTrue(any("不自制 ed25519" in i for i in export_issues(old)))
        no_impl = self.text.replace("ed25519.py", "某实现")
        self.assertTrue(any("ed25519.py" in i for i in export_issues(no_impl)))
        no_legal = self.text.replace("不构成法律意见", "见条款")
        self.assertTrue(any("法律意见" in i for i in export_issues(no_legal)))
        no_table = self.text.replace("## 声明与仓库事实对照（机检面）", "## 对照")
        self.assertTrue(any("缺段" in i for i in export_issues(no_table)))
        no_cmd = self.text.replace("python scripts/nf.py explain check27", "看纯度")
        self.assertTrue(any("check27" in i for i in export_issues(no_cmd)))
        no_key = self.text.replace("library attest", "attest")
        self.assertTrue(any("ssh-key" in i for i in export_issues(no_key)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_export.md")


if __name__ == "__main__":
    unittest.main()
