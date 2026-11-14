#!/usr/bin/env python3
"""patterns/README.md 契约：品类说明的「包数 / 必填键 / 词表 / 投影纪律」必须与实现一致。

为什么必须有：这是「实践包货架」的入口说明（`docs/patterns.md` 是面向使用者的另一页，本页是
维护者视角的格式与流程）。它写着 6 必填键、2 值词表、7 个包、INDEX 是投影——此前没有任何判据，
新增 pattern 的人只能照着旧文本猜。本轮补「§现状对照」「§新增/审阅一条 pattern」「§复现与引用口径」
并加本判据，把 README 与 `core/patterns` 常量/`entries()` 活绑定。

范围：只判本页与实现/索引事实自洽（不新增 pattern）。
同族判据：test_patterns_index_doc_contract.py（INDEX 幂等）/
test_patterns_doc_contract.py（docs/patterns.md）。
契约：⛔ 紧跟标题（doc_hygiene 要求）、最后更新 + 复核位、现状对照 6 行、6 必填键逐名、
词表 2 值、7 包、INDEX 生成物纪律、四步流程、复现三命令、⛔ 行位置。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pat  # noqa: E402

DOC = ROOT / "patterns" / "README.md"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"patterns README 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("patterns README 为空")
    return text


def readme_issues(text: str) -> list:
    issues = []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# NF Patterns · 实践包品类"):
        issues.append("缺标题「# NF Patterns · 实践包品类」")
    elif len(lines) < 2 or "⛔" not in lines[1]:
        issues.append("⛔ 操作指令必须紧跟标题（doc_hygiene 判据）")
    if "最后更新：2026-11-14" not in text:
        issues.append("缺「最后更新：2026-11-14（复核）」")
    if "复核（2026-11-14）" not in text:
        issues.append("缺复核说明")
    for section in ("## 现状对照", "## 新增/审阅一条 pattern", "## 复现与引用口径"):
        if section not in text:
            issues.append(f"缺段落：{section}")
    for key in pat.REQUIRED:
        if key not in text:
            issues.append(f"缺必填键：{key}")
    if "**6 个**" not in text:
        issues.append("现状未写 6 必填键")
    for st in pat.STATUSES:
        if st not in text:
            issues.append(f"缺状态词：{st}")
    if "**2 值**" not in text:
        issues.append("现状未写状态词表 2 值")
    total = len(pat.entries(str(ROOT)))
    if f"| 实践包 | **{total}**" not in text:
        issues.append(f"现状包数与真源不一致（应为 {total}）")
    if "整页生成" not in text:
        issues.append("缺「INDEX 整页生成」纪律")
    if "deprecated" not in text or "不要直接删包" not in text:
        issues.append("缺退役口径（deprecated，不删包）")
    for cmd in ("python scripts/nf.py patterns verify",
                "python scripts/nf.py patterns reindex"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PatternsReadmeTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_patterns_readme_matches_contract(self):
        self.assertEqual([], readme_issues(self.text), "patterns README 不满足契约")

    def test_constants_live(self):
        self.assertEqual(6, len(pat.REQUIRED))
        self.assertEqual(("active", "deprecated"), tuple(pat.STATUSES))
        self.assertEqual(7, len(pat.entries(str(ROOT))))

    def test_contract_catches_mutations(self):
        """变异自证：⛔ 位置 / 包数改错 / 缺必填键 / 缺退役口径。"""
        first, second = self.text.splitlines()[0], self.text.splitlines()[1]
        broken = self.text.replace(first + "\n" + second, first + "\n\n" + second)
        self.assertTrue(any("紧跟标题" in i for i in readme_issues(broken)))
        bad = self.text.replace("| 实践包 | **7**", "| 实践包 | **5**")
        self.assertTrue(any("包数" in i for i in readme_issues(bad)))
        no_key = self.text.replace("applies_to", "paths")
        self.assertTrue(any("applies_to" in i for i in readme_issues(no_key)))
        no_retire = self.text.replace("不要直接删包", "可以直接删")
        self.assertTrue(any("退役" in i for i in readme_issues(no_retire)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_patterns_readme.md")


if __name__ == "__main__":
    unittest.main()
