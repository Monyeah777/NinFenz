#!/usr/bin/env python3
"""终端文档契约：77 命令 / 8 族 / 203 索引 / 9 区 / 13 表单 / 139 例必须与实读一致。

为什么必须有：这是端壳退役后唯一的人机入口说明——命令数、能力族、索引条数、能力区、写盘表单、
会话内阻塞命令与写盘确认动词，任何一项漂移都会让读者对「终端到底能做什么、拦什么」判断错。
本轮补「§现状对照」「§复现与引用口径」，并把数字与 core/terminal 常量、nf shell --verify 实读绑定。

范围：只判本文与 terminal 实现/判据事实自洽（不改实现）。
同族判据：test_terminal.py（139 例）/ check39（同源判据）/ test_doc_hygiene.py。
契约：最后更新位 + 复核、九个能力区、8 族、13 表单、42 斜杠词、4 阻塞命令、24 确认动词、
--verify 五项计数、139 例、现状对照 + 复现三命令、菜单只许指向真实命令口径。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import terminal as tm  # noqa: E402

DOC = ROOT / "docs" / "terminal.md"
SECTIONS = ("## 这个终端是什么", "## 最快上手（两条命令）", "## 能力菜单",
            "## 交互语法", "## 现状对照", "## 复现与引用口径", "## 边界")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"终端文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("终端文档为空")
    return text


def verify_out() -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "shell", "--verify"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)
    return proc.stdout + proc.stderr


def counts() -> dict:
    out = verify_out()
    nums = {}
    for label, key in (("命令", "cmds"), ("能力族", "families"),
                       ("索引条目", "index"), ("菜单示例", "examples"),
                       ("动作", "actions")):
        m = re.search(label + r"\s*(\d+)", out)
        if m:
            nums[key] = int(m.group(1))
    return nums


def terminal_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 终端"):
        issues.append("缺标题「# NF 终端——端壳退役后的人机入口」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    if len(tm.ZONES) != 9:
        issues.append(f"能力区数已变（{len(tm.ZONES)}）")
    if len(tm.FAMILIES) != 8:
        issues.append(f"能力族数已变（{len(tm.FAMILIES)}）")
    if len(tm.FORMS) != 13:
        issues.append(f"写盘表单数已变（{len(tm.FORMS)}）")
    if len(tm.SLASH_WORDS) != 42:
        issues.append(f"斜杠词数已变（{len(tm.SLASH_WORDS)}）")
    if len(tm.BLOCKED_IN_SHELL) != 4:
        issues.append(f"阻塞命令数已变（{len(tm.BLOCKED_IN_SHELL)}）")
    if len(tm.CONFIRM_VERBS) != 24:
        issues.append(f"确认动词数已变（{len(tm.CONFIRM_VERBS)}）")
    for label in ("**77**", "**203**", "**8**", "**9**", "**15**", "**34**",
                  "**13**", "**42**", "**4**", "**24**", "**139 例**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    c = counts()
    if c.get("cmds") != 77:
        issues.append(f"命令数已变（{c.get('cmds')}）")
    if c.get("index") != 203:
        issues.append(f"索引条目已变（{c.get('index')}）")
    if "example_resolves" not in text:
        issues.append("缺「菜单只许指向真实命令」判据名 example_resolves")
    if "写盘" not in text or "拒跑" not in text:
        issues.append("缺写盘闸门口径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py shell --verify",
                "python scripts/nf.py shell --commands --json",
                "python -m pytest desktop/tests/test_terminal.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class TerminalDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_terminal_matches_contract(self):
        self.assertEqual([], terminal_issues(self.text), "终端文档不满足契约")

    def test_impl_live(self):
        self.assertEqual(9, len(tm.ZONES))
        self.assertEqual(8, len(tm.FAMILIES))
        self.assertEqual(13, len(tm.FORMS))
        self.assertEqual(42, len(tm.SLASH_WORDS))
        self.assertEqual(4, len(tm.BLOCKED_IN_SHELL))
        self.assertEqual(24, len(tm.CONFIRM_VERBS))
        self.assertIn("通过", verify_out())

    def test_contract_catches_mutations(self):
        """变异自证：命令数回退 / 区数回退 / 表单数回退 / 缺判据名 / 缺命令。"""
        old = self.text.replace("**77**", "**70**")
        self.assertTrue(any("77" in i for i in terminal_issues(old)))
        old_z = self.text.replace("**9**", "**7**")
        self.assertTrue(any("9" in i for i in terminal_issues(old_z)))
        old_f = self.text.replace("**13**", "**10**")
        self.assertTrue(any("13" in i for i in terminal_issues(old_f)))
        no_name = self.text.replace("example_resolves", "cursor")
        self.assertTrue(any("example_resolves" in i for i in terminal_issues(no_name)))
        no_cmd = self.text.replace("python scripts/nf.py shell --verify", "自检")
        self.assertTrue(any("--verify" in i for i in terminal_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_terminal.md")


if __name__ == "__main__":
    unittest.main()
