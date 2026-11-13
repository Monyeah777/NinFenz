#!/usr/bin/env python3
"""patterns/error-message-guidance/PATTERN.md 契约：R4 规则、check27 接线、不钉命中数。

为什么必须有：这条 pattern 的「可检面」是 check27 里的 R4 审计——如果哪天 R4 被改名/摘掉，
或 check27 不再审计 raise 指引，pattern 就变成「只有道理、没有判据」。此前没有判据盯着这件事；
另有一类风险是把 `grep` 命中数写死（随提交漂）。本轮补「§现状对照」「§复现与引用口径」并加本判据。

范围：只判本文 frontmatter/正文与 purity_scan/check27 事实自洽（不改规则正文）。
同族判据：test_dependency_direction_pattern_doc_contract.py（同骨架）/
test_patterns_readme_doc_contract.py。
契约：6 必填键、3 条规则、applies_to 两条（目录 + verify.sh）在场、evidence 可解析、
为什么/怎么用/反例/已有实证/现状对照/复现口径六段、
R4 与 check27 在文且在实现中、不钉命中数、verify rc=0。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "error-message-guidance" / "PATTERN.md"
PURITY = ROOT / "desktop" / "src" / "core" / "purity_scan.py"
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
        if e["dir"] == "error-message-guidance":
            return e
    raise ValueError("patterns 里找不到 error-message-guidance")


def guidance_issues(text: str) -> list:
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
    verify_text = VERIFY.read_text(encoding="utf-8")
    for ev in pat._as_list(fm.get("evidence")):
        rel = str(ev).replace("\\", "/")
        if rel.startswith("check") and rel[5:].isdigit():
            if f"check{rel[5:]}()" not in verify_text:
                issues.append(f"evidence 的 check 不存在：{rel}")
            continue
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    purity = PURITY.read_text(encoding="utf-8")
    if "R4" not in purity:
        issues.append("purity_scan 里找不到 R4 规则（可检面消失）")
    if "修复指引" not in VERIFY.read_text(encoding="utf-8"):
        issues.append("verify.sh 里找不到修复指引审计表述（check27 未接线）")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 已有的实证",
                    "## 现状对照", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "R4" not in text or "check27" not in text:
        issues.append("正文未把 R4 与 check27 点名")
    if "不钉固定命中数" not in text:
        issues.append("缺「不钉固定命中数」口径")
    if "不等于全量门禁" not in text:
        issues.append("缺「check27 PASS ≠ 全量门禁」提醒")
    for cmd in ("python scripts/nf.py verify --only 27",
                "python scripts/nf.py patterns verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class ErrorMessageGuidancePatternTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], guidance_issues(self.text), "error-message-guidance 不满足契约")

    def test_r4_and_check27_live(self):
        self.assertIn("R4", PURITY.read_text(encoding="utf-8"))
        self.assertIn("修复指引", VERIFY.read_text(encoding="utf-8"))

    def test_patterns_verify_passes(self):
        issues, _warns, stats = pat.scan(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(7, stats.get("patterns"))

    def test_contract_catches_mutations(self):
        """变异自证：缺现状段 / 缺 R4 点名 / 钉死命中数 / 缺全量提醒。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in guidance_issues(no_sec)))
        no_r4 = self.text.replace("R4", "规则")
        self.assertTrue(any("R4" in i for i in guidance_issues(no_r4)))
        pinned = self.text.replace("不钉固定命中数", "命中数固定为 900")
        self.assertTrue(any("不钉固定命中数" in i for i in guidance_issues(pinned)))
        no_full = self.text.replace("不等于全量门禁", "即全量门禁")
        self.assertTrue(any("全量门禁" in i for i in guidance_issues(no_full)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_guidance.md")


if __name__ == "__main__":
    unittest.main()
