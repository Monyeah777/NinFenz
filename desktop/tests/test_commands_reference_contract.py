#!/usr/bin/env python3
"""skills/ninfenz/references/commands.md 契约：命令全在册 + 契约数不漂移 + 退出码语义对得上。

为什么必须有：这是外部 agent 查命令的速查表——写了死命令或过期数字，外部 agent 会照错执行
（prose_lint 的扫描面不含 skills/**，门禁不一定会红）。实测本轮抓到两处：① nf conformance
注释仍写「16 契约」（实为 27）；② 文首有一处空「## 补全」重复段。本轮修掉并把「本文件内每条
nf 命令都在 CLI 注册表」「契约数与实况同源」「语义化 exit 2 两条口径」「library 生命周期三命令
分行」立成机检断言。

范围：只判本文件与其引用真源的自洽（不改命令行为）。同族判据：
test_doc_truth.TestSkillCommandFace（skills/** 命令面，全文件扫）/
test_assembly_reference_contract.py（装配参考，exit 2 口径同源）/
test_skill_md_contract.py（SKILL 入口）。
契约：十节按序无重复、无「16 契约」且含实况条数、本文件所有 nf 子命令均在 CLI 注册表、
library 生命周期三命令分行且 supersede 顺序有说明、退出码 0/1/2 + 两条语义化 exit 2 在场、
命令统一 python scripts/nf.py 前缀。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import conformance_report as cr  # noqa: E402
from core import prose_lint as pl  # noqa: E402

REF = ROOT / "skills" / "ninfenz" / "references" / "commands.md"
NF_VERIFY = ROOT / "scripts" / "nf_verify.py"
HEADINGS = ("## 装配与运行", "## 市场与协议", "## 资产 / 模块 / 管线",
            "## 导出 / MCP / 治理", "## 质检与发布", "## 图书馆（library）",
            "## 抽象执行与治理", "## 治理声明与机器面", "## 质量与遥测", "## 补全")
TICK = chr(96)
EXIT_MARKERS = ("0" + TICK + " 成功", "1" + TICK + " 运行/校验失败", "2" + TICK + " 用法错误")


def load_text(path: Path = REF) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"commands.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("commands.md 为空")
    return text


def headings(text: str) -> list:
    return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("## ")]


def cli_calls(text: str) -> list:
    found = []
    for snip in pl._command_snippets(text):
        for m in pl._NF_CALL.finditer(snip):
            found.append(m.group(1))
    return found


def top_note(text: str) -> str:
    return text.split("\n## ", 1)[0]


def commands_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NinFenz CLI 命令族"):
        issues.append("缺标题「# NinFenz CLI 命令族」")
    note = top_note(text)
    for marker in ("test_doc_truth", "退出码", "未执行验收", "未执行漂移断言", "--help"):
        if marker not in note:
            issues.append(f"文首说明缺要素：{marker}")
    got = headings(text)
    for want in HEADINGS:
        if not any(h.startswith(want) for h in got):
            issues.append(f"缺节：{want}")
    dupes = {h for h in got if got.count(h) > 1}
    if dupes:
        issues.append(f"重复标题：{sorted(dupes)}")
    if len(got) != len(HEADINGS):
        issues.append(f"节数应十节（实测 {len(got)}）：{got}")
    if "16 契约" in text:
        issues.append("残留过期契约数「16 契约」")
    count = len(cr.CONTRACTS)
    if str(count) + " 契约" not in text:
        issues.append(f"未写当前契约数（{count}）")
    cmds = pl.cli_commands(str(ROOT))
    if not cmds:
        issues.append("CLI 注册表读不到")
    bad = sorted({c for c in cli_calls(text) if c not in cmds})
    if bad:
        issues.append(f"本文件写了未注册的 nf 子命令：{bad}")
    for sub in ("library deprecate", "library restore", "library supersede"):
        if sub not in text:
            issues.append(f"library 生命周期缺命令：nf {sub}")
    if "entry by 顺序" not in text:
        issues.append("supersede 缺入参顺序说明（entry by）")
    if not NF_VERIFY.is_file():
        issues.append("缺读者侧验证脚本：scripts/nf_verify.py")
    if "nf_verify.py --entry" not in text:
        issues.append("缺读者侧独立验证命令示例")
    if text.count("python scripts/nf.py") < 40:
        issues.append("命令前缀不统一或命令过少（应统一 python scripts/nf.py）")
    for token in EXIT_MARKERS:
        if token not in text:
            issues.append(f"退出码约定缺口径：{token}")
    return issues


class CommandsReferenceContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_commands_reference_matches_contract(self):
        self.assertEqual([], commands_issues(self.text), "commands.md 不满足契约")

    def test_all_commands_registered(self):
        cmds = pl.cli_commands(str(ROOT))
        self.assertTrue(cmds)
        bad = sorted({c for c in cli_calls(self.text) if c not in cmds})
        self.assertEqual([], bad)

    def test_conformance_count_is_live(self):
        self.assertIn(str(len(cr.CONTRACTS)) + " 契约", self.text)
        self.assertNotIn("16 契约", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：契约数回退 / 重复标题 / 死命令 / 缺 supersede 顺序 / 缺 exit 2 口径。"""
        stale = self.text.replace("27 契约", "16 契约", 1)
        self.assertTrue(any("16 契约" in i for i in commands_issues(stale)))
        dup = self.text + "\n## 补全\n"
        self.assertTrue(any("重复" in i or "节数" in i for i in commands_issues(dup)))
        dead = self.text.replace("python scripts/nf.py asset ls",
                                 "python scripts/nf.py assetzz ls", 1)
        self.assertTrue(any("未注册" in i for i in commands_issues(dead)))
        no_order = self.text.replace("entry by 顺序", "参数顺序", 1)
        self.assertTrue(any("supersede" in i for i in commands_issues(no_order)))
        no_exit = self.text.replace("未执行漂移断言", "漂移断言")
        self.assertTrue(any("未执行漂移断言" in i for i in commands_issues(no_exit)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_commands.md")


if __name__ == "__main__":
    unittest.main()
