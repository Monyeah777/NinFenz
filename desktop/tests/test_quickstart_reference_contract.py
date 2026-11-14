#!/usr/bin/env python3
"""skills/ninfenz/references/quickstart.md 契约：安装/自检/不克隆路径必须「可执行 + 真件在场」。

为什么必须有：这是外部用户看到的第一份操作指南——一条不存在的安装命令就会让人卡在第一步。
实测本轮抓到**真死命令**：文首写 scripts/install-skill-from-github.py 从 GitHub 安装，但仓库里
没有该脚本；另有环境前提（Python >= 3.11、Bash）缺失、raw 直链取件口径缺失。本轮改为「复制
自包含目录」的真实安装路径，并把「无死安装命令」「Python 版本 ↔ pyproject」「引用文件真件
在场」「命令全在册」立成机检断言。

范围：只判本文件与其引用事实的自洽（不改技能行为）。同族判据：
test_doc_truth.TestSkillCommandFace（skills/** 命令面）/ test_commands_reference_contract.py
（命令族）/ test_assembly_reference_contract.py（装配参考）/ test_skill_md_contract.py（入口）。
契约：五节按序 + 环境前提（>=3.11 ↔ pyproject）、无死安装脚本、安装=复制自包含目录（SKILL/
references/agents 真件在场）、自检命令全在册、不克隆路径含 raw 直链、接下来读三件 references。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import prose_lint as pl  # noqa: E402

REF = ROOT / "skills" / "ninfenz" / "references" / "quickstart.md"
SKILL_DIR = ROOT / "skills" / "ninfenz"
PYPROJECT = ROOT / "pyproject.toml"
HEADINGS = ("## 环境前提", "## 安装本 skill", "## 准备仓库", "## 最快跑通",
            "## 不克隆仓库的 AI 装配路径", "## 接下来读什么")
REQUIRED_FILES = ("SKILL.md", "references/assembly.md", "references/commands.md",
                  "references/quickstart.md", "agents/openai.yaml")
DOC_REFS = ("docs/agent/AGENT_START.md", "docs/agent/agent_组装指令包_v0.2.md",
            "01_核心协议.md", "02_联动注册表.md", "06_Agent执行协议.md",
            "07_官方核心出厂与社区预设导航.md")


def load_text(path: Path = REF) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"quickstart.md 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("quickstart.md 为空")
    return text


def cli_calls(text: str) -> list:
    found = []
    for snip in pl._command_snippets(text):
        for m in pl._NF_CALL.finditer(snip):
            found.append(m.group(1))
    return found


def quickstart_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NinFenz 快速开始"):
        issues.append("缺标题「# NinFenz 快速开始」")
    got = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("## ")]
    for want in HEADINGS:
        if not any(h.startswith(want) for h in got):
            issues.append(f"缺节：{want}")
    if got != sorted(got, key=lambda h: text.index(h)):
        pass
    positions = [text.find(s) for s in HEADINGS]
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if ("install-skill-from-github.py" in text.replace("没有「一键安装脚本」", "")
            and "scripts/install-skill-from-github.py" in text):
        issues.append("仍把不存在的脚本当安装命令")
    if "scripts/install-skill-from-github.py" in text:
        issues.append("死安装命令 scripts/install-skill-from-github.py 仍在")
    pyproject = PYPROJECT.read_text(encoding="utf-8")
    if ">=3.11" not in pyproject:
        issues.append("pyproject requires-python 漂移（应 >=3.11）")
    if "Python ≥ 3.11" not in text:
        issues.append("缺环境前提：Python 3.11")
    if "Bash" not in text:
        issues.append("缺环境前提：Bash（verify.sh 需要）")
    if "cp -r" not in text:
        issues.append("安装步骤缺「复制自包含目录」的真实做法")
    for rel in REQUIRED_FILES:
        if not (SKILL_DIR / rel).is_file():
            issues.append(f"技能目录缺件：{rel}")
    for rel in ("references/assembly.md", "references/commands.md", "SKILL.md"):
        if rel not in text and rel.split("/")[-1] not in text:
            issues.append(f"未指引阅读：{rel}")
    for rel in DOC_REFS:
        if not (ROOT / rel).is_file():
            issues.append(f"引用的文档不存在：{rel}")
        if rel.split("/")[-1] not in text:
            issues.append(f"正文未引用：{rel}")
    if "raw.githubusercontent.com" not in text:
        issues.append("不克隆路径缺 raw 直链口径")
    if "gitee.com" not in text:
        issues.append("缺国内镜像口径")
    cmds = pl.cli_commands(str(ROOT))
    if not cmds:
        issues.append("CLI 注册表读不到")
    bad = sorted({c for c in cli_calls(text) if c not in cmds})
    if bad:
        issues.append(f"本文件写了未注册的 nf 子命令：{bad}")
    for need in ("--version", "doctor", "demo", "market --list", "asset ls", "module ls",
                 "worldmodel --walk"):
        if need not in text:
            issues.append(f"自检步骤缺命令：nf {need}")
    return issues


class QuickstartReferenceContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_quickstart_matches_contract(self):
        self.assertEqual([], quickstart_issues(self.text), "quickstart.md 不满足契约")

    def test_no_dead_install_command(self):
        self.assertNotIn("scripts/install-skill-from-github.py", self.text)
        self.assertIn("cp -r", self.text)

    def test_install_paths_exist(self):
        for rel in REQUIRED_FILES:
            self.assertTrue((SKILL_DIR / rel).is_file(), rel)
        for rel in DOC_REFS:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_commands_registered(self):
        cmds = pl.cli_commands(str(ROOT))
        self.assertTrue(cmds)
        bad = sorted({c for c in cli_calls(self.text) if c not in cmds})
        self.assertEqual([], bad)

    def test_contract_catches_mutations(self):
        """变异自证：死安装命令 / Python 前提漂移 / 缺自检命令 / 缺 raw 口径 / 缺阅读指引。"""
        dead = self.text.replace("## 安装本 skill", "## 安装本 skill\n\nscripts/install-"
                                 + "skill-from-github.py --repo a/b", 1)
        self.assertTrue(any("死安装命令" in i for i in quickstart_issues(dead)))
        bad_py = self.text.replace("Python ≥ 3.11", "Python ≥ 3.8", 1)
        self.assertTrue(any("3.11" in i or "安装步骤" in i for i in quickstart_issues(bad_py)))
        no_cmd = self.text.replace("doctor", "healthcheck")
        self.assertTrue(any("doctor" in i for i in quickstart_issues(no_cmd)))
        no_raw = self.text.replace("raw.githubusercontent.com", "github.com/raw", 1)
        self.assertTrue(any("raw" in i for i in quickstart_issues(no_raw)))
        no_read = self.text.replace("references/assembly.md", "assembly 文档")
        self.assertTrue(any("assembly" in i for i in quickstart_issues(no_read)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_quickstart.md")


if __name__ == "__main__":
    unittest.main()
