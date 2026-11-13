#!/usr/bin/env python3
"""CHANGELOG.md 契约：历史只追加不重写；节序从新到旧、日期单调不增；生成器自检无 issue。

为什么必须有：这是全仓最长的历史文件，也是「最容易被人顺手改」的文件——重写既有节、改旧日期
都是史实造假，而且不会立刻报错。本轮补三段「怎么产生 / 纪律 / 现状」说明，并把三条不变量写成判据：
① 节序从新到旧；② 版本节日期单调不增；③ 生成器 nf changelog --json 的 issues 为空。

范围：只判本文结构与生成器自检（不改历史内容）。
同族判据：test_changelog_gen.py / test_doc_hygiene.py（CHANGELOG 豁免活文档计数）。
契约：标题 + 三段说明、未发布唯一且在最前、已发布节 4 个且序为 0.93/0.92/0.82/0.72、
日期单调不增、生成器 issues 空、不重写纪律在场。
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "CHANGELOG.md"
SECTION = re.compile(r"(?m)^## \[(未发布|\d+\.\d+(?:\.\d+)?)\](?: - (\d{4}-\d{2}-\d{2}))?")
VERSIONS = ("未发布", "0.93", "0.92", "0.82", "0.72")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"CHANGELOG 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("CHANGELOG 为空")
    return text


def sections(text: str) -> list:
    return [(m.group(1), m.group(2)) for m in SECTION.finditer(text)]


def gen_out() -> dict:
    proc = subprocess.run([sys.executable, "scripts/nf.py", "changelog", "--json",
                           "--no-commits"],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, check=False)
    body = proc.stdout[proc.stdout.index("{"):]
    return json.loads(body)


def changelog_issues(text: str) -> list:
    issues = []
    if not text.startswith("# Changelog"):
        issues.append("缺标题「# Changelog」")
    for marker in ("怎么产生", "只**追加**", "重写历史"):
        if marker not in text:
            issues.append(f"缺说明要素：{marker}")
    secs = sections(text)
    got = [s[0] for s in secs]
    if got != list(VERSIONS):
        issues.append(f"节序/节集已变：{got}")
    if got.count("未发布") != 1:
        issues.append(f"「未发布」节数为 {got.count('未发布')}（应为 1）")
    dates = [s[1] for s in secs if s[1]]
    if dates != sorted(dates, reverse=True):
        issues.append(f"版本节日期非单调不增：{dates}")
    if "**4**" not in text or "**1**" not in text:
        issues.append("说明段未写「已发布 4 节 + 未发布 1 节」")
    out = gen_out()
    if out.get("issues"):
        issues.append(f"生成器自检 issue 非空：{out['issues']}")
    if not out.get("section"):
        issues.append("生成器未渲染出版本节")
    return issues


class ChangelogDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_changelog_matches_contract(self):
        self.assertEqual([], changelog_issues(self.text), "CHANGELOG 不满足契约")

    def test_structure_live(self):
        secs = sections(self.text)
        self.assertEqual(list(VERSIONS), [s[0] for s in secs])
        dates = [s[1] for s in secs if s[1]]
        self.assertEqual(sorted(dates, reverse=True), dates)
        self.assertEqual([], gen_out()["issues"])

    def test_contract_catches_mutations(self):
        """变异自证：改旧日期 / 节序缺失 / 删纪律 / 重复未发布。"""
        flipped = self.text.replace("## [0.93] - 2026-10-05",
                                    "## [0.93] - 2026-12-31", 1)
        self.assertTrue(any("日期非单调不增" in i for i in changelog_issues(flipped)))
        dropped = self.text.replace("## [0.72] - 2026-09-08", "## 0.72 - 2026-09-08", 1)
        self.assertTrue(any("节序" in i for i in changelog_issues(dropped)))
        no_note = self.text.replace("只**追加**", "可修改")
        self.assertTrue(any("只**追加**" in i for i in changelog_issues(no_note)))
        dup = self.text.replace("# Changelog", "# Changelog\n\n## [未发布] - 2026-11-10", 1)
        self.assertTrue(any("未发布" in i for i in changelog_issues(dup)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_changelog.md")


if __name__ == "__main__":
    unittest.main()
