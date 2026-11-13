#!/usr/bin/env python3
"""docs/lsp.md 契约：LSP 接入文档必须「11 能力/16 方法/8 MiB/utf-16/77 例与实现一致」。

为什么必须有：这页是编辑器接入的唯一说明——能力条数、协议方法、分帧上限、位置编码、写盘纪律，
任何一项漂移都会让编辑器配置或客户端假设失效。本轮补「§现状对照」（11 能力 / 16 个 M_* 方法 /
8 MiB / utf-16 / 不写盘 / 77 例）与「§复现与引用口径」，并同步 en/ja 译件后重签摘要。

范围：只判本文与 lsp 实现/判据/译件事实自洽（不改服务器）。
同族判据：test_lsp.py（60）/ test_lsp_guard.py（4）/ test_lsp_hardening.py（7）/
test_lsp_transcript.py（6）/ test_locales.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、11 条能力逐条在文、16 个 M_* 方法计数、8 MiB、utf-16、
「不自行写盘」、77 例、现状对照 + 复现两命令、en/ja 译件含现状小节。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import lsp  # noqa: E402

DOC = ROOT / "docs" / "lsp.md"
EN = ROOT / "docs" / "en" / "lsp.md"
JA = ROOT / "docs" / "ja" / "lsp.md"
SECTIONS = ("## 是什么", "## 三步接入", "## 现状对照", "## 复现与引用口径",
            "## 自测（无需编辑器）", "## 边界（诚实标注）")
CAPS = ("同步", "诊断", "修复", "补全", "悬停", "跳定义", "大纲", "工作区符号",
        "折叠", "引用", "位置编码")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"LSP 文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("LSP 文档为空")
    return text


def methods() -> list:
    return [n for n in dir(lsp) if n.startswith("M_")]


def lsp_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 编辑器接入（LSP）"):
        issues.append("缺标题「# 编辑器接入（LSP）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    for cap in CAPS:
        if cap not in text:
            issues.append(f"正文缺能力：{cap}")
    if "**11 条**" not in text:
        issues.append("未写 11 条能力")
    ms = methods()
    if len(ms) != 16:
        issues.append(f"M_* 方法数已变（{len(ms)}）")
    if "**16 个**" not in text:
        issues.append("未写 16 个协议方法")
    if "8 MiB" not in text:
        issues.append("缺 8 MiB 入站上限")
    if "utf-16" not in text:
        issues.append("缺 utf-16 位置编码")
    if "不自行写盘" not in text:
        issues.append("缺「不自行写盘」纪律")
    if "**77 例**" not in text:
        issues.append("未写 77 例判据")
    if "Content-Length" not in text:
        issues.append("缺 Content-Length 分帧口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py lsp --print-config neovim",
                "python -m pytest desktop/tests/test_lsp.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    en = EN.read_text(encoding="utf-8") if EN.is_file() else ""
    ja = JA.read_text(encoding="utf-8") if JA.is_file() else ""
    if "Status check" not in en:
        issues.append("en 译件缺现状小节")
    if "現状対照" not in ja:
        issues.append("ja 译件缺现状小节")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class LspDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_lsp_matches_contract(self):
        self.assertEqual([], lsp_issues(self.text), "LSP 文档不满足契约")

    def test_impl_live(self):
        self.assertEqual(16, len(methods()))
        self.assertIn("M_INITIALIZE", methods())
        self.assertIn("M_CODE_ACTION", methods())

    def test_contract_catches_mutations(self):
        """变异自证：缺能力 / 方法数回退 / 缺上限 / 缺编码 / 缺命令。"""
        no_cap = self.text.replace("工作区符号", "工作区")
        self.assertTrue(any("工作区符号" in i for i in lsp_issues(no_cap)))
        old_m = self.text.replace("**16 个**", "**12 个**")
        self.assertTrue(any("16 个" in i for i in lsp_issues(old_m)))
        no_cap8 = self.text.replace("8 MiB", "4 MiB")
        self.assertTrue(any("8 MiB" in i for i in lsp_issues(no_cap8)))
        no_enc = self.text.replace("utf-16", "utf-8")
        self.assertTrue(any("utf-16" in i for i in lsp_issues(no_enc)))
        no_cmd = self.text.replace("python scripts/nf.py lsp --print-config neovim",
                                   "打印配置")
        self.assertTrue(any("print-config" in i for i in lsp_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_lsp.md")


if __name__ == "__main__":
    unittest.main()
