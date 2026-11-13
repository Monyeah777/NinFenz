#!/usr/bin/env python3
"""submissions/02-cline-marketplace.md 契约：审核四要点 + 不钉运行时计数 + 平台侧未验。

为什么必须有：这是投给 Cline Marketplace 的 Issue 正文（人工审核四维：社区活跃度/维护者可信度/
成熟度/安全）。实测发现两处真问题：① 正文写着「check1-40 · PASS=72 · 约 2500 单测」——
给外部审核的文案钉会过期的运行时数字；② 「实测确认」是**只能作者在 Cline 客户端里做**的动作，
却被写成待办句，读者可能以为仓库侧已验。本轮改掉计数钉法与平台侧状态，并把审核要点写成表。

范围：只判本件与图标/运行面/材料包事实自洽（不改审核流程）。
同族判据：test_mcp_submissions_doc_contract.py（跨 10 份一致性）/
test_mcp_assets_readme_doc_contract.py。
契约：图标 400×400 要求、llms-install.md 在场、12+1 工具、双协议两值、
不得出现 check 数 / PASS 数的钉法（除非同行有留痕词）、平台侧未验、实测确认归作者。
"""
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import mcp_runtime as mcp  # noqa: E402

DOC = ROOT / "packaging" / "mcp" / "submissions" / "02-cline-marketplace.md"
ICON = ROOT / "packaging" / "mcp" / "assets" / "icon-400.png"
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cline 提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Cline 提交件为空")
    return text


def icon_size() -> tuple:
    return struct.unpack(">II", ICON.read_bytes()[16:24])


def cline_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 02 · Cline MCP Marketplace"):
        issues.append("缺标题「# 02 · Cline MCP Marketplace」")
    if "审核要点自检" not in text:
        issues.append("缺「审核要点自检」段")
    if icon_size() != (400, 400):
        issues.append(f"icon-400.png 真实像素不是 400x400（{icon_size()}）")
    if "icon-400.png" not in text:
        issues.append("正文未引用 icon-400.png")
    if "**真实 400×400 PNG**" not in text:
        issues.append("未写「真实 400×400」要求")
    if not (ROOT / "llms-install.md").is_file():
        issues.append("仓库根 llms-install.md 不在场（Cline 靠它安装）")
    if "llms-install.md" not in text:
        issues.append("正文未引用 llms-install.md")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "12 个只读工具 + 1 个 prompt" not in text:
        issues.append("正文未写 12+1 工具面")
    for era in ("2026-07-28", "2025-11-25"):
        if era not in text:
            issues.append(f"缺协议版本：{era}")
    if "平台侧未验" not in text:
        issues.append("缺「平台侧未验」（审核结果不可从仓库证明）")
    if "待作者在 Cline 客户端里跑一次" not in text:
        issues.append("「实测确认」未归位为作者动作")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:50]}")
    if "以 `nf stats` 生成区为准" not in text:
        issues.append("缺「以 nf stats 生成区为准」替代口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ClineSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_cline_submission_matches_contract(self):
        self.assertEqual([], cline_issues(self.text), "Cline 提交件不满足契约")

    def test_icon_live(self):
        self.assertEqual((400, 400), icon_size())

    def test_contract_catches_mutations(self):
        """变异自证：残留钉数 / 缺平台标注 / 实测确认不归位 / 图标引用丢失。"""
        pinned = self.text + "\n- 门禁 check1-42 · PASS=76 全绿。\n"
        self.assertTrue(any("钉运行时计数" in i for i in cline_issues(pinned)))
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in cline_issues(no_platform)))
        no_owner = self.text.replace("待作者在 Cline 客户端里跑一次", "已实测通过")
        self.assertTrue(any("实测确认" in i for i in cline_issues(no_owner)))
        no_icon = self.text.replace("icon-400.png", "icon.png")
        self.assertTrue(any("icon-400" in i for i in cline_issues(no_icon)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_cline.md")


if __name__ == "__main__":
    unittest.main()
