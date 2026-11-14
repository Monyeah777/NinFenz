#!/usr/bin/env python3
"""patterns/dependency-direction/PATTERN.md 契约：机制断言可核、数字不钉、基线只许收敛。

为什么必须有：这是 7 个实践包里最「有实测故事」的一条（Ca/I 数值、两条 SDP 违例、修复后归零），
但先前没有判据盯着：① `applies_to` / `evidence` 是否仍可证；② 正文里的历史数值是否被误读成当前值；
③ 基线文件是否还被引用。本轮补「§现状对照」「§复现与引用口径」，并加判据把这三点钉住。

范围：只判本文 frontmatter/正文与 coupling 实现事实自洽（不改 pattern 正文的结论）。
同族判据：test_patterns_readme_doc_contract.py / test_patterns_index_doc_contract.py。
契约：frontmatter 6 必填 + 3 条规则、applies_to 两通配真实匹配、evidence 逐条可解析、
正文含 为什么/怎么用/反例、现状对照段、「不钉当前 Ca/I」口径、复现三命令、verify rc=0。
"""
import glob
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "dependency-direction" / "PATTERN.md"
BASELINE = ROOT / "protocol" / "coupling_baseline.json"


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
        if e["dir"] == "dependency-direction":
            return e
    raise ValueError("patterns 里找不到 dependency-direction")


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
    applies = pat._as_list(fm.get("applies_to"))
    for pattern in applies:
        if not glob.glob(str(ROOT / pattern)):
            issues.append(f"applies_to 指向空气：{pattern}")
    evidence = pat._as_list(fm.get("evidence"))
    for item in evidence:
        rel = str(item).replace('\\', '/')
        if not (ROOT / rel).exists():
            issues.append(f"evidence 不在场：{rel}")
    if not BASELINE.is_file():
        issues.append("耦合基线文件不在场")
    for section in ("## 为什么", "## 怎么用", "## 反例", "## 现状对照",
                    "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    if "不钉具体 Ca/I" not in text:
        issues.append("缺「不钉当前 Ca/I 数值」口径")
    if "实测（2026-10-03）" not in text:
        issues.append("缺历史留痕（实测 2026-10-03）")
    for cmd in ("python scripts/coupling_metrics.py",
                "python scripts/nf.py patterns verify"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "只许收敛" not in text:
        issues.append("缺「基线只许收敛」纪律")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class DependencyDirectionPatternTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_pattern_matches_contract(self):
        self.assertEqual([], pattern_issues(self.text), "dependency-direction 不满足契约")

    def test_coupling_baseline_live(self):
        self.assertTrue(BASELINE.is_file())
        e = entry()
        self.assertEqual(3, len(pat._as_list(e["fm"].get("rules"))))

    def test_patterns_verify_passes(self):
        issues, _warns, stats = pat.scan(str(ROOT))
        self.assertEqual([], issues)
        self.assertEqual(7, stats.get("patterns"))

    def test_contract_catches_mutations(self):
        """变异自证：缺现状对照 / 缺不钉数值口径 / 缺历史留痕 / 缺复现命令。"""
        no_sec = self.text.replace("## 现状对照", "## 附注")
        self.assertTrue(any("现状对照" in i for i in pattern_issues(no_sec)))
        no_pin = self.text.replace("不钉具体 Ca/I", "已钉死当前 Ca/I")
        self.assertTrue(any("不钉" in i for i in pattern_issues(no_pin)))
        no_hist = self.text.replace("实测（2026-10-03）", "实测")
        self.assertTrue(any("留痕" in i for i in pattern_issues(no_hist)))
        no_cmd = self.text.replace("python scripts/coupling_metrics.py", "看耦合")
        self.assertTrue(any("coupling_metrics" in i for i in pattern_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_pattern.md")


if __name__ == "__main__":
    unittest.main()
