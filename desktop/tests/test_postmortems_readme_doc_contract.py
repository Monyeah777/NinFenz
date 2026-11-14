#!/usr/bin/env python3
"""postmortems/README.md 契约：三个内部治理目录的公开面政策必须同构、白名单可机检。

为什么必须有：`decisions/` / `handovers/` / `postmortems/` 是同一类（内部材料、公开面只留模板），
但 `decisions/README.md` 与 `handovers/README.md` 都有「怎么读 / 白名单 / 为什么 / 怎么验」，
`postmortems/README.md` 此前只有 4 行。本轮补齐同构，并把「白名单 / 命令 / 私有仓路径」写成判据，
避免三份 README 再次分叉（此前 handovers 那份就是这样被落下的）。

范围：只判本目录说明与协议/判据/发布边界事实自洽（不改政策）。
同族判据：test_publish_boundary.py /
test_postmortem_template_doc_contract.py / test_handovers_readme_doc_contract.py。
契约：四小节（怎么读/白名单/为什么/怎么验）在场、白名单两条目、三条命令、私有仓路径、
两个判据文件点名、姊妹目录规则并列、复核位、目录只两件、`nf postmortem verify` rc=0。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "postmortems" / "README.md"
DIR = ROOT / "postmortems"
SIBLINGS = ("decisions", "handovers")
CMDS = ("postmortem check", "postmortem verify")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"postmortems README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("postmortems README 为空")
    return text


def cli_verify() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf.py", "postmortem", "verify"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=False)


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# postmortems/ · 复盘件"):
        issues.append("缺标题「# postmortems/ · 复盘件（公开面只留模板）」")
    for section in ("## 本文件怎么读", "## 目录白名单", "## 为什么这么定", "## 怎么验"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for token in ("README.md", "PO-9xxx"):
        if token not in text:
            issues.append(f"白名单缺条目：{token}")
    for sib in SIBLINGS:
        if sib not in text:
            issues.append(f"未并列姊妹目录规则：{sib}")
    if "governance/decisions-archive/postmortems/" not in text:
        issues.append("缺私有仓真源路径")
    for cmd in CMDS:
        if cmd not in text:
            issues.append(f"缺命令：{cmd}")
    for judge in ("test_publish_boundary.py", "test_postmortem_template_doc_contract.py"):
        if judge not in text:
            issues.append(f"缺判据点名：{judge}")
    if "项目符号恰 1 条" not in text:
        issues.append("缺「模板项目符号恰 1 条」的机检提示")
    names = sorted(p.name for p in DIR.iterdir() if p.is_file())
    if names != ["PO-9000-示例-复盘模板.md", "README.md"]:
        issues.append(f"目录出现非模板件：{names}")
    for sib in SIBLINGS:
        if not (ROOT / sib / "README.md").is_file():
            issues.append(f"姊妹目录说明缺失：{sib}/README.md")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PostmortemsReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "postmortems README 不满足契约")

    def test_postmortem_verify_passes(self):
        proc = cli_verify()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("声明与全部复盘件一致", proc.stdout)

    def test_contract_catches_mutations(self):
        """变异自证：缺小节 / 缺白名单 / 缺命令 / 缺私有仓路径 / 缺机检提示。"""
        no_sec = self.text.replace("## 目录白名单", "## 白名单")
        self.assertTrue(any("目录白名单" in i for i in readme_issues(no_sec)))
        no_tpl = self.text.replace("PO-9xxx", "PO-XXXX")
        self.assertTrue(any("PO-9xxx" in i for i in readme_issues(no_tpl)))
        no_cmd = self.text.replace("postmortem verify", "看验证")
        self.assertTrue(any("postmortem verify" in i for i in readme_issues(no_cmd)))
        no_path = self.text.replace("governance/decisions-archive/postmortems/", "私有仓")
        self.assertTrue(any("私有仓真源" in i for i in readme_issues(no_path)))
        no_hint = self.text.replace("项目符号恰 1 条", "符号提示")
        self.assertTrue(any("项目符号" in i for i in readme_issues(no_hint)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_postmortems_readme.md")


if __name__ == "__main__":
    unittest.main()
