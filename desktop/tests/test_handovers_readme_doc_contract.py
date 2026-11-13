#!/usr/bin/env python3
"""handovers/README.md 契约：三个内部治理目录的公开面政策必须同构、白名单可机检。

为什么必须有：`decisions/` / `handovers/` / `postmortems/` 是同一类（内部材料、公开面只留模板），
但 `decisions/README.md` 有「本文件怎么读 / 怎么验 / 为什么这么定」与白名单表，`handovers/README.md`
此前只有 4 行——同一政策没有同等说明，读的人只能猜。本轮补齐同构，并把「目录白名单/命令/私有仓路径」
写成判据，避免两份 README 再次分叉。

范围：只判本目录说明与协议/判据/发布边界事实自洽（不改政策）。
同族判据：test_publish_boundary.py / test_handover_template_doc_contract.py。
契约：四小节（怎么读/白名单/为什么）在同、白名单两行、三命令、私有仓路径、
`protocol/handover.json` 与两个判据文件点名、姊妹目录规则并列、复核位。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "handovers" / "README.md"
DIR = ROOT / "handovers"
PROTO = ROOT / "protocol" / "handover.json"
SIBLINGS = ("decisions", "postmortems")
CMDS = ("handover check", "handover verify", "handover ls")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"handovers README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("handovers README 为空")
    return text


def cli_ls() -> str:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "handover", "ls"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, check=False)
    return proc.stdout + proc.stderr + f"[rc={proc.returncode}]"


def readme_issues(text: str) -> list:
    issues = []
    if not text.startswith("# handovers/ · 接力件"):
        issues.append("缺标题「# handovers/ · 接力件（公开面只留模板）」")
    for section in ("## 本文件怎么读", "## 目录白名单", "## 为什么这么定"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核位")
    for token in ("README.md", "HO-9xxx"):
        if token not in text:
            issues.append(f"白名单缺条目：{token}")
    for sib in SIBLINGS:
        if sib not in text:
            issues.append(f"未并列姊妹目录规则：{sib}")
    if "governance/decisions-archive/handovers/" not in text:
        issues.append("缺私有仓真源路径")
    for cmd in CMDS:
        if cmd not in text:
            issues.append(f"缺命令：{cmd}")
    for judge in ("test_publish_boundary.py", "test_handover_template_doc_contract.py",
                  "protocol/handover.json"):
        if judge not in text:
            issues.append(f"缺判据/协议点名：{judge}")
    if "白名单" not in text or "FAIL" not in text:
        issues.append("缺「白名单 / FAIL」口径")
    names = sorted(p.name for p in DIR.iterdir() if p.is_file())
    if names != ["HO-9000-示例-接力模板.md", "README.md"]:
        issues.append(f"目录出现非模板件：{names}")
    if "rc=0" not in cli_ls():
        issues.append("nf handover ls 未成功")
    for sib in SIBLINGS:
        if not (ROOT / sib / "README.md").is_file():
            issues.append(f"姊妹目录说明缺失：{sib}/README.md")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class HandoversReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "handovers README 不满足契约")

    def test_protocol_live(self):
        proto = json.loads(PROTO.read_text(encoding="utf-8"))
        self.assertEqual(["情境", "背景", "评估", "建议", "未决项"], proto["sections"])
        self.assertIn("rc=0", cli_ls())

    def test_contract_catches_mutations(self):
        """变异自证：缺小节 / 缺白名单 / 缺命令 / 缺私有仓路径 / 目录混入真实件。"""
        no_sec = self.text.replace("## 目录白名单", "## 白名单")
        self.assertTrue(any("目录白名单" in i for i in readme_issues(no_sec)))
        no_tpl = self.text.replace("HO-9xxx", "HO-XXXX")
        self.assertTrue(any("HO-9xxx" in i for i in readme_issues(no_tpl)))
        no_cmd = self.text.replace("handover verify", "看验证")
        self.assertTrue(any("handover verify" in i for i in readme_issues(no_cmd)))
        no_path = self.text.replace("governance/decisions-archive/handovers/", "私有仓")
        self.assertTrue(any("私有仓真源" in i for i in readme_issues(no_path)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_handovers_readme.md")


if __name__ == "__main__":
    unittest.main()
