#!/usr/bin/env python3
"""postmortems/PO-9000-示例-复盘模板.md 契约：模板可机检、四段/行动项口径与 check 一致。

为什么必须有：这是公开仓唯一的复盘模板（真实复盘在私有 Plan 仓）。本轮实测踩到一个真问题：
`nf postmortem check` 把**全文所有** `- ` 开头的行当作行动项——我在文末追加的说明用列表写，
立刻被判「行动项缺判据」。这正是模板要防的坑，却没写在模板里。本轮补「§现状对照」「§复现与引用口径」、
把「除行动项段外不要用项目符号」写清，并加判据把这层钉住（含子进程实跑 check）。

范围：只判模板与 postmortem 实现/发布边界事实自洽（不改模板结构）。
同族判据：test_postmortem.py / test_publish_boundary.py。
契约：frontmatter 六键、四段齐全且顺序正确、行动项恰 1 条带负责人+判据、
「除行动项段外不用列表」提示在文、现状对照段、复现三命令、公开面只两件、check 实跑 rc=0。
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "postmortems" / "PO-9000-示例-复盘模板.md"
DIR = ROOT / "postmortems"
SECTIONS = ("## 现象", "## 影响", "## 根因", "## 行动项")
FIELDS = ("id:", "title:", "date:", "trigger:", "status:", "refs:")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"复盘模板不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("复盘模板为空")
    return text


def cli_check() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf.py", "postmortem", "check",
                           "postmortems/PO-9000-示例-复盘模板.md"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=False)


def template_issues(text: str) -> list:
    issues = []
    if not text.startswith("---\n"):
        issues.append("缺 frontmatter（--- 包裹）")
    for field in FIELDS:
        if field not in text:
            issues.append(f"frontmatter 缺字段：{field}")
    if not re.search(r"(?m)^id: PO-9\d{3}$", text):
        issues.append("id 不符合 PO-9xxx")
    positions = [text.find(sec) for sec in SECTIONS]
    for sec, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{sec}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("四段顺序不对（现象 → 影响 → 根因 → 行动项）")
    bullets = [ln for ln in text.splitlines() if ln.startswith("- ")]
    if len(bullets) != 1:
        issues.append(f"项目符号行 {len(bullets)} 条（check 会把它们全当行动项，应恰 1 条）")
    if "负责人" not in text or "判据" not in text:
        issues.append("行动项缺「负责人 / 判据」")
    if "不要" not in text or "项目符号" not in text:
        issues.append("缺「除行动项段外不要用项目符号」的机检提示")
    if "## 现状对照" not in text:
        issues.append("缺「§现状对照」段")
    if "## 复现与引用口径" not in text:
        issues.append("缺「§复现与引用口径」段")
    for cmd in ("python scripts/nf.py postmortem check",
                "python scripts/nf.py postmortem verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    names = sorted(p.name for p in DIR.iterdir() if p.is_file())
    if names != ["PO-9000-示例-复盘模板.md", "README.md"]:
        issues.append(f"公开目录出现非模板件：{names}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PostmortemTemplateTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_template_matches_contract(self):
        self.assertEqual([], template_issues(self.text), "复盘模板不满足契约")

    def test_cli_check_passes(self):
        proc = cli_check()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("行动项 1 条", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：多一条项目符号 / 缺四段 / 缺提示 / id 不合式。"""
        extra = self.text + "\n- 额外一条项目符号\n"
        self.assertTrue(any("项目符号行" in i for i in template_issues(extra)))
        no_sec = self.text.replace("## 根因", "## 原因")
        self.assertTrue(any("根因" in i for i in template_issues(no_sec)))
        no_hint = self.text.replace("项目符号", "列表")
        self.assertTrue(any("提示" in i for i in template_issues(no_hint)))
        bad_id = self.text.replace("id: PO-9000", "id: PO-9x")
        self.assertTrue(any("PO-9xxx" in i for i in template_issues(bad_id)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_po.md")


if __name__ == "__main__":
    unittest.main()
