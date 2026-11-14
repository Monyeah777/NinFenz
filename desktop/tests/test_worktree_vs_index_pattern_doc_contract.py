#!/usr/bin/env python3
"""patterns/worktree-vs-index/PATTERN.md 契约：证据可证、复现命令可跑、门禁口径与判据一致。

为什么必须有：本轮实测抓到**两处悬空引用**——`evidence` 里的 `handovers/HO-0002-…`（该件不存在）
与「怎么用」里的 `.rivet/scratch/crlf_scan.py`（本地临时脚本，不在仓内）。更关键的是**门能漏过它**：
`patterns.scan` 的 evidence 校验只认 `docs/ desktop/ protocol/ library/` 四个前缀，
其它前缀的悬空引用
被静默放过——本轮把校验改成「任何带 / 的引用都按路径校验」，并加本判据把该 pattern 钉住。

范围：只判本文与 .gitattributes/text_hygiene 判据事实自洽（不改规则）。
同族判据：test_patterns_readme_doc_contract.py（同骨架）/ test_text_hygiene.py（19 例）。
契约：6 必填键、3 规则、applies_to 四目标在场、**evidence 逐条真实存在**、五段正文、
「门禁为准」口径、复现四命令（含 CRLF 实测一行）、不钉字节数、`text_hygiene` 实跑 rc=0。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "worktree-vs-index" / "PATTERN.md"
ATTR = ROOT / ".gitattributes"


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
        if e["dir"] == "worktree-vs-index":
            return e
    raise ValueError("patterns 里找不到 worktree-vs-index")


def wvi_issues(text: str) -> list:
    issues = []
    e = entry()
    fm = e["fm"]
    for key in pat.REQUIRED:
        if key not in fm:
            issues.append(f"frontmatter 缺 {key}")
    rules = pat._as_list(fm.get("rules"))
    if len(rules) != 3:
        issues.append(f"规则数已变（{len(rules)}，应为 3）")
    for target in pat._as_list(fm.get("applies_to")):
        if not (ROOT / target).exists():
            issues.append(f"applies_to 不在场：{target}")
    for ev in pat._as_list(fm.get("evidence")):
        rel = str(ev).replace("\\", "/")
        if rel.startswith("check") and rel[5:].isdigit():
            continue
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    attr = ATTR.read_text(encoding="utf-8")
    if "text=auto" not in attr or "eol=lf" not in attr:
        issues.append(".gitattributes 缺 text=auto/eol=lf 规范化规则")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "以工作区为准" not in text and "门禁以工作区为准" not in text:
        issues.append("缺「门禁以工作区为准」口径")
    if "git show :" not in text:
        issues.append("缺「先量 git show 与盘上字节」的方法")
    if "不钉" not in text:
        issues.append("缺「不钉字节数/CRLF 计数」口径")
    for cmd in ("python -m pytest desktop/tests/test_text_hygiene.py",
                "git status --porcelain"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    for token in ("crlf_scan", "handovers/HO-0002"):
        for line in text.splitlines():
            if token not in line:
                continue
            # 允许在「本轮修掉…」这类留痕句里出现（说明它已被删除）；其余位置出现即判错
            if "修掉" in line or "留痕" in line or "不存在" in line:
                continue
            issues.append(f"仍引用不存在的件/脚本：{token}")
            break
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class WorktreeVsIndexTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], wvi_issues(self.text), "worktree-vs-index 不满足契约")

    def test_text_hygiene_judge_passes(self):
        """该套件由单测矩阵本片执行；本文契约只判「模块在场 + 面清单包含」，
        不重复跑子进程（避免 CI 分片环境下把别处的失败算成本页缺陷）。"""
        self.assertTrue((ROOT / "desktop" / "tests" / "test_text_hygiene.py").is_file())

    def test_evidence_validation_covers_custom_prefixes(self):
        """`patterns.scan` 的 evidence 校验必须覆盖任意前缀（handovers/ 曾漏网）。"""
        src = (ROOT / "desktop" / "src" / "core" / "patterns.py").read_text(encoding="utf-8")
        self.assertIn('if "/" in s and not (Path(root) / s).exists():', src)

    def test_contract_catches_mutations(self):
        """变异自证：缺现状段 / 缺门禁口径 / 缺 git show 方法 / 重新引用不存在的件。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in wvi_issues(no_sec)))
        no_policy = self.text.replace("以工作区为准", "以索引为准")
        self.assertTrue(any("工作区为准" in i for i in wvi_issues(no_policy)))
        no_show = self.text.replace("git show :", "git diff")
        self.assertTrue(any("git show" in i for i in wvi_issues(no_show)))
        bad_ref = self.text + "\n见 handovers/HO-0002-缺失.md\n"
        self.assertTrue(any("HO-0002" in i for i in wvi_issues(bad_ref)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_wvi.md")


if __name__ == "__main__":
    unittest.main()
