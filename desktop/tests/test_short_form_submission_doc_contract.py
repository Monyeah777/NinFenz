#!/usr/bin/env python3
"""submissions/07-mcpservers-org.md 契约：短表单族字段正文必须逐字一致（07/08 现成两份）。

为什么必须有：07 与 08 是同一套字段、两个轻量目录。它们正文此前**逐字相同**，但没有任何判据——
改一份忘另一份，就会有两个目录站拿到两套描述（且没人会比）。本轮在 07 补「§字段自检」，
并加判据把「字段正文逐字一致」写成可机检事实；后续 09/10 的通用块也按同一口径加入。

范围：只判 07 与同族短表单件（08）的字段块一致 + 与材料包/运行面事实自洽。
同族判据：test_mcp_submissions_doc_contract.py（跨 10 份）/
test_pulsemcp_submission_doc_contract.py。
契约：字段块（** 开头的行）07 == 08、标题与入口不同、八字段齐全、12+1 工具、
图标真 400x400、MIT、平台侧未验、不钉 check/PASS（无留痕词时）、无邮箱泄漏。
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

SUB = ROOT / "packaging" / "mcp" / "submissions"
DOC = SUB / "07-mcpservers-org.md"
PEER = SUB / "08-mcpmarket.md"
ICON = ROOT / "packaging" / "mcp" / "assets" / "icon-400.png"
PIN = re.compile(r"check1-\d+|PASS=\d+")
TRACE = ("此前", "历史", "实测", "2026-", "漂移", "快照")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"轻量目录提交件不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("轻量目录提交件为空")
    return text


def field_block(text: str) -> list:
    """** 开头的字段行（到 §字段自检 之前为止）。"""
    head = text.split("## 字段自检")[0]
    return [ln for ln in head.splitlines() if ln.startswith("**")]


def short_form_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 07 · mcpservers.org"):
        issues.append("缺标题「# 07 · mcpservers.org」")
    if "## 字段自检" not in text:
        issues.append("缺「§字段自检」段")
    mine = field_block(text)
    if len(mine) < 10:
        issues.append(f"字段行不足 10（{len(mine)}）")
    if PEER.is_file():
        peer = field_block(PEER.read_text(encoding="utf-8"))
        if mine != peer:
            issues.append(f"字段正文与 08 不一致（{len(mine)} vs {len(peer)}）")
    for token in ("**名称 / Name**", "**仓库 / Repo**", "**站点 / Site**",
                  "**安装 / Install**", "**许可 / License**", "**图标 / Icon**"):
        if token not in text:
            issues.append(f"字段缺项：{token}")
    if len(mcp.TOOL_DEFS) != 12 or len(mcp.PROMPT_DEFS) != 1:
        issues.append("工具面已变（应为 12 + 1）")
    if "12 个只读工具 + 1 个 prompt" not in text:
        issues.append("正文未写 12+1 工具面")
    if struct.unpack(">II", ICON.read_bytes()[16:24]) != (400, 400):
        issues.append("icon-400.png 真实像素不是 400x400")
    if "**真实 400×400**" not in text:
        issues.append("自检段未写真实 400x400")
    if "MIT" not in text:
        issues.append("缺许可 MIT")
    if "平台侧未验" not in text:
        issues.append("缺平台侧未验")
    if "短表单族" not in text:
        issues.append("缺「短表单族逐字一致」提醒")
    leaked = EMAIL.search(text)
    if leaked:
        issues.append(f"正文出现邮箱地址：{leaked.group(0)}")
    for line in text.splitlines():
        if PIN.search(line) and not any(w in line for w in TRACE):
            issues.append(f"钉运行时计数且无留痕词：{line.strip()[:40]}")
    if "不钉运行时计数" not in text:
        issues.append("缺「不钉运行时计数」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ShortFormSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_short_form_matches_contract(self):
        self.assertEqual([], short_form_issues(self.text), "轻量目录提交件不满足契约")

    def test_peer_field_block_identical(self):
        self.assertEqual(field_block(self.text),
                         field_block(PEER.read_text(encoding="utf-8")))

    def test_contract_catches_mutations(self):
        """变异自证：字段行被改 / 缺自检段 / 残留钉数 / 邮箱泄漏。"""
        changed = self.text.replace("**安装 / Install**：`npx -y ninfenz serve`",
                                    "**安装 / Install**：npm i -g ninfenz")
        self.assertTrue(any("与 08 不一致" in i for i in short_form_issues(changed)))
        no_sec = self.text.replace("## 字段自检", "## 附注")
        self.assertTrue(any("字段自检" in i for i in short_form_issues(no_sec)))
        pinned = self.text + "\n- check1-42 · PASS=76\n"
        self.assertTrue(any("钉运行时计数" in i for i in short_form_issues(pinned)))
        leak = self.text + "\n- 联系：ops@example.com\n"
        self.assertTrue(any("邮箱地址" in i for i in short_form_issues(leak)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_short_form.md")


if __name__ == "__main__":
    unittest.main()
