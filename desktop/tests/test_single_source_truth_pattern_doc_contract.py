#!/usr/bin/env python3
"""patterns/single-source-truth/PATTERN.md 契约：五个投影件都在、标记与重算判据真实成立。

为什么必须有：这条 pattern 的可检面是「在盘投影 == 实时重算」——一旦某个投影件被手改、或标记丢了，
pattern 就失效。此前没有判据把它们逐个盯住（只有零散的 library/patterns 单测）。
本轮补「§现状对照」「§复现与引用口径」，并加判据：五个投影件逐件在场、Markdown 件带生成标记、
**子进程实跑 library verify 与 patterns verify 都必须零缺口**、两个 JSON 工件靠摘要绑定（不手改）。

范围：只判本文与投影件/判据事实自洽（不改投影机制）。
同族判据：test_patterns_readme_doc_contract.py（同骨架）/ test_library_*.py / check34/35。
契约：6 必填键、3 规则、applies_to **五目标**在场、evidence（check34/check35/library.py）可解析、
为什么/怎么用/反例/现状对照/复现口径五段、「两类工件两种锁」口径、复现三命令、不钉条目数。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "single-source-truth" / "PATTERN.md"
PROJECTIONS = ("library/INDEX.md", "library/ALIAS.md", "patterns/INDEX.md",
               "protocol/conformance_report.json", "protocol/RECEIPTS.json")
MARKED = ("library/INDEX.md", "patterns/INDEX.md")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"pattern 正文不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("pattern 正文为空")
    return text


def entry() -> dict:
    for e in pat.entries(str(ROOT)):
        if e["dir"] == "single-source-truth":
            return e
    raise ValueError("patterns 里找不到 single-source-truth")


def run(*args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=cwd or str(ROOT),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)


def truth_issues(text: str) -> list:
    issues = []
    e = entry()
    fm = e["fm"]
    for key in pat.REQUIRED:
        if key not in fm:
            issues.append(f"frontmatter 缺 {key}")
    rules = pat._as_list(fm.get("rules"))
    if len(rules) != 3:
        issues.append(f"规则数已变（{len(rules)}，应为 3）")
    verify_text = (ROOT / "verify.sh").read_text(encoding="utf-8")
    for target in pat._as_list(fm.get("applies_to")):
        if not (ROOT / target).exists():
            issues.append(f"applies_to 不在场：{target}")
    for rel in PROJECTIONS:
        if not (ROOT / rel).exists():
            issues.append(f"投影件不在场：{rel}")
    for rel in MARKED:
        body = (ROOT / rel).read_text(encoding="utf-8")
        if "BEGIN GENERATED" not in body:
            issues.append(f"投影件缺生成标记：{rel}")
    for ev in pat._as_list(fm.get("evidence")):
        rel = str(ev).replace("\\", "/")
        if rel.startswith("check") and rel[5:].isdigit():
            if f"check{rel[5:]}()" not in verify_text:
                issues.append(f"evidence 的 check 不存在：{rel}")
            continue
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "两类工件两种锁" not in text:
        issues.append("缺「两类工件两种锁」口径")
    if "以命令实读为准" not in text and "不钉条目数" not in text:
        issues.append("缺不钉运行时数字的口径")
    for cmd in ("python scripts/nf.py library verify",
                "python scripts/nf.py patterns verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class SingleSourceTruthTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], truth_issues(self.text), "single-source-truth 不满足契约")

    def test_projections_recompute_clean(self):
        lib = run("scripts/nf.py", "library", "verify")
        self.assertEqual(0, lib.returncode, lib.stdout[-400:])
        pats = run("scripts/nf.py", "patterns", "verify")
        self.assertEqual(0, pats.returncode, pats.stdout[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺现状段 / 缺两种锁口径 / 缺复现命令 / 缺不钉口径。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in truth_issues(no_sec)))
        no_lock = self.text.replace("两类工件两种锁", "工件靠摘要")
        self.assertTrue(any("两种锁" in i for i in truth_issues(no_lock)))
        no_cmd = self.text.replace("python scripts/nf.py library verify", "library 检查")
        self.assertTrue(any("library verify" in i for i in truth_issues(no_cmd)))
        no_pin = self.text.replace("以命令实读为准", "已固定").replace("不钉条目数", "钉死")
        self.assertTrue(any("不钉" in i for i in truth_issues(no_pin)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_truth.md")


if __name__ == "__main__":
    unittest.main()
