#!/usr/bin/env python3
"""patterns/fail-closed-verification/PATTERN.md 契约：示例必须与实测一致、check33 接线在场。

为什么必须有：这条 pattern 的「怎么用」里写着两条命令与预期行为——本轮实测发现原文的
「缺允许签名者 → exit 1」**不符实际**（NF-1 未挂锚时是 exit 0 + 显式标注「真实性未验」）。
文档只要和实测分叉，读者就会按错的预期判断「验过了/没验过」。本轮校正示例并加判据：
示例命令必须可跑、输出口径必须与实测一致、check33 必须仍在场。

范围：只判本文与 nf_verify/attest/check33 事实自洽（不改工具行为）。
同族判据：test_error_message_guidance_pattern_doc_contract.py（同骨架）/ test_attest*.py。
契约：6 必填键、3 条规则、applies_to 四目标在场、evidence（check33 + 两篇 docs）可解析、
为什么/怎么用/反例/现状对照/复现口径五段、**exit 0 与「真实性未验」口径在文**、
check33 在 verify.sh、「该验而验不了」的精确含义在文。
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "fail-closed-verification" / "PATTERN.md"
VERIFY = ROOT / "verify.sh"


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
        if e["dir"] == "fail-closed-verification":
            return e
    raise ValueError("patterns 里找不到 fail-closed-verification")


def verify_run() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "scripts/nf_verify.py", "--entry", "NF-1"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180, check=False)


def pattern_issues(text: str) -> list:
    issues = []
    e = entry()
    fm = e["fm"]
    for key in pat.REQUIRED:
        if key not in fm:
            issues.append(f"frontmatter 缺 {key}")
    rules = pat._as_list(fm.get("rules"))
    if len(rules) != 3:
        issues.append(f"规则数已变（{len(rules)}，应为 3）")
    verify_text = VERIFY.read_text(encoding="utf-8")
    for target in pat._as_list(fm.get("applies_to")):
        if not (ROOT / target).exists():
            issues.append(f"applies_to 不在场：{target}")
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
    if "exit 0" not in text:
        issues.append("缺「exit 0」的实测行为说明")
    if "真实性" not in text or "未验" not in text:
        issues.append("缺「真实性未验」口径")
    if "该验而验不了" not in text:
        issues.append("缺 fail-closed 的精确含义（该验而验不了）")
    if "check33" not in text:
        issues.append("正文未点名 check33")
    if "2026-11-14 实测校正" not in text:
        issues.append("缺实测校正说明（历史留痕）")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class FailClosedPatternTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], pattern_issues(self.text), "fail-closed-verification 不满足契约")

    def test_example_output_matches_live(self):
        proc = verify_run()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("真实性", proc.stdout)
        self.assertIn("未验", proc.stdout)

    def test_check33_live(self):
        self.assertIn("check33()", VERIFY.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：删校正说明 / 删 exit 0 / 删精确含义 / 删 check33 点名。"""
        no_fix = self.text.replace("2026-11-14 实测校正", "怎么写")
        self.assertTrue(any("实测校正" in i for i in pattern_issues(no_fix)))
        no_exit = self.text.replace("exit 0", "exit 1")
        self.assertTrue(any("exit 0" in i for i in pattern_issues(no_exit)))
        no_meaning = self.text.replace("该验而验不了", "验不了")
        self.assertTrue(any("精确含义" in i for i in pattern_issues(no_meaning)))
        no_check = self.text.replace("check33", "check3")
        self.assertTrue(any("check33" in i for i in pattern_issues(no_check)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_fail_closed.md")


if __name__ == "__main__":
    unittest.main()
