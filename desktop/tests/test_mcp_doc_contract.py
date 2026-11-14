#!/usr/bin/env python3
"""docs/mcp.md 契约：MCP 接入文档必须「12 工具/1 prompt/版本口径与 mcp_runtime 一致」。

为什么必须有：这页是 agent 接入 MCP 的唯一入口——工具清单、数量、prompt、协议版本、入站上限，
任何一项漂移都会让接入方少调或多调工具。本轮修真实缺口：能力表只点名 **7** 个工具
（检索 4 + 内容 3），而 mcp_runtime 实有 **12** 个（检索 7 + 内容 5，含 library_read /
pattern_list / pattern_read / asset_list / knowledge_order_read）；
同页别处又写「12 个工具」自相矛盾。
已按真源补全两张工具行，并补「§现状对照」「§复现与引用口径」；en/ja 译件同步后重签。

范围：只判本文与 mcp_runtime/协议口径/译件事实自洽（不改运行时）。
同族判据：test_mcp_runtime.py / test_mcp_package_contract.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、12 工具逐名（7+5）、1 prompt、dual-era 两版本、8 MiB、白名单与写路径口径、
现状对照 + 复现两命令、en/ja 译件含现状小节。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime  # noqa: E402

DOC = ROOT / "docs" / "mcp.md"
EN = ROOT / "docs" / "en" / "mcp.md"
JA = ROOT / "docs" / "ja" / "mcp.md"
SECTIONS = ("## 这是什么", "## 三步接入", "## 能力表", "## 现状对照",
            "## 复现与引用口径", "## E3 实测记录")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"MCP 接入文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("MCP 接入文档为空")
    return text


def mcp_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NinFenz MCP 接入"):
        issues.append("缺标题「# NinFenz MCP 接入（nf serve ...）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    names = [t["name"] for t in mcp_runtime.TOOL_DEFS]
    if len(names) != 12:
        issues.append(f"工具数已变（{len(names)}）")
    for n in names:
        if n not in text:
            issues.append(f"正文缺工具：{n}")
    if "**12 个**" not in text and "12 个工具" not in text:
        issues.append("未写 12 个工具")
    if "检索面 7" not in text or "内容通道 5" not in text:
        issues.append("未写 7+5 分档")
    prompts = [p["name"] for p in mcp_runtime.PROMPT_DEFS]
    if prompts != ["assemble_guide"]:
        issues.append(f"prompt 清单已变：{prompts}")
    for p in prompts:
        if p not in text:
            issues.append(f"正文缺 prompt：{p}")
    for v in ("2026-07-28", "2025-11-25"):
        if v not in text:
            issues.append(f"正文缺协议版本：{v}")
    if "dual-era" not in text:
        issues.append("缺 dual-era 口径")
    if "8 MiB" not in text:
        issues.append("缺入站上限 8 MiB")
    if "-32602" not in text or "白名单" not in text:
        issues.append("缺白名单/错误码口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py serve --help",
                "python -m pytest desktop/tests/test_mcp_runtime.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    en = EN.read_text(encoding="utf-8") if EN.is_file() else ""
    ja = JA.read_text(encoding="utf-8") if JA.is_file() else ""
    if "Status check" not in en:
        issues.append("en 译件缺现状对照小节")
    if "現状対照" not in ja:
        issues.append("ja 译件缺现状对照小节")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class McpDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_mcp_matches_contract(self):
        self.assertEqual([], mcp_issues(self.text), "MCP 接入文档不满足契约")

    def test_runtime_live(self):
        self.assertEqual(12, len(mcp_runtime.TOOL_DEFS))
        self.assertEqual(["assemble_guide"],
                         [p["name"] for p in mcp_runtime.PROMPT_DEFS])
        for t in mcp_runtime.TOOL_DEFS:
            self.assertTrue(t.get("readOnlyHint") is not False)

    def test_contract_catches_mutations(self):
        """变异自证：缺工具 / 分档回退 / 缺版本 / 缺上限 / 缺命令。"""
        no_tool = self.text.replace("knowledge_order_read", "knowledge_read")
        self.assertTrue(any("knowledge_order_read" in i for i in mcp_issues(no_tool)))
        bad = self.text.replace("检索面 7", "检索面 4")
        self.assertTrue(any("7+5" in i for i in mcp_issues(bad)))
        no_v = self.text.replace("2025-11-25", "2024-11-05")
        self.assertTrue(any("2025-11-25" in i for i in mcp_issues(no_v)))
        no_cap = self.text.replace("8 MiB", "4 MiB")
        self.assertTrue(any("8 MiB" in i for i in mcp_issues(no_cap)))
        no_cmd = self.text.replace("python scripts/nf.py serve --help", "看帮助")
        self.assertTrue(any("serve --help" in i for i in mcp_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_mcp.md")


if __name__ == "__main__":
    unittest.main()
