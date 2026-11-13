#!/usr/bin/env python3
"""submissions/03-mcp-so.md 契约：字段值与材料包同源；对外文案不钉运行时计数；平台侧不冒充判据。

为什么必须有：这 10 份提交件的**价值全在「直接粘」**——一旦某个字段与材料包分叉，投出去就是错的。
03 号（mcp.so 表单）此前只有 10 行字段，没有任何自检：字段真源、图标真实像素、文案里能不能带
check/PASS 数字，全靠人记。本轮补「§字段自检」并加本判据，把字段 ↔ 真源 ↔ 诚实边界钉住。

范围：只判本件与材料包/运行面/图标事实自洽（不改表单内容）。
同族判据：test_mcp_submissions_doc_contract.py（跨 10 份）/ test_cline_submission_doc_contract.py。
契约：八字段逐项在场且与共享值一致、工具面 12+1、图标真实 400×400、许可 MIT、
平台侧未验、不钉 check/PASS（无留痕词时）、403 提示在场。
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

DOC = ROOT / "packaging" / "mcp" / "submissions" / "03-mcp-so.md"
ICON = ROOT / "packaging" / "mcp" / "assets" / "icon-400.png"
SHARED = {
    "repo": "https://github.com/Monyeah777/NinFenz",
    "site": "https://ninfenz.dev/",
    "install": "npx -y ninfenz serve",
    "name": "NinFenz Content Gate",
}
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移", "快照")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"mcp.so 提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("mcp.so 提交件为空")
    return text


def mcpso_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 03 · mcp.so"):
        issues.append("缺标题「# 03 · mcp.so」")
    if "## 字段自检" not in text:
        issues.append("缺「§字段自检」段")
    for key, val in SHARED.items():
        if val not in text:
            issues.append(f"缺共享值 {key}：{val}")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "12 个只读工具 + 1 个 prompt" not in text:
        issues.append("正文未写 12+1 工具面")
    if struct.unpack(">II", ICON.read_bytes()[16:24]) != (400, 400):
        issues.append("icon-400.png 真实像素不是 400x400")
    if "**真实 400×400**" not in text:
        issues.append("自检段未写「真实 400×400」")
    if "MIT" not in text:
        issues.append("缺许可 MIT")
    if "平台侧未验" not in text:
        issues.append("缺「平台侧未验」")
    if "403" not in text:
        issues.append("缺「该站拦脚本 403」提示")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:40]}")
    if "不钉运行时计数" not in text:
        issues.append("缺「不钉运行时计数」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class McpSoSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_mcpso_matches_contract(self):
        self.assertEqual([], mcpso_issues(self.text), "mcp.so 提交件不满足契约")

    def test_shared_values_live(self):
        for val in SHARED.values():
            self.assertIn(val, self.text)

    def test_contract_catches_mutations(self):
        """变异自证：仓库地址写错 / 残留钉数 / 缺平台标注 / 缺 403 提示。"""
        bad = self.text.replace(SHARED["repo"], "https://github.com/X/Y")
        self.assertTrue(any("仓库" in i or "repo" in i for i in mcpso_issues(bad)))
        pinned = self.text + "\n- 门禁 check1-42 · PASS=76 全绿\n"
        self.assertTrue(any("钉运行时计数" in i for i in mcpso_issues(pinned)))
        no_platform = self.text.replace("平台侧未验", "平台侧已验")
        self.assertTrue(any("平台侧" in i for i in mcpso_issues(no_platform)))
        no_403 = self.text.replace("403", "阻断")
        self.assertTrue(any("403" in i for i in mcpso_issues(no_403)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_mcpso.md")


if __name__ == "__main__":
    unittest.main()
