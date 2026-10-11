#!/usr/bin/env python3
"""Markdown 表格列数一致性（审计 W4：断链 2 / 表格列数不齐 11）。

只扫**我方文档**（仓库根 *.md + docs/**/*.md），不扫 community/（第三方正文会持续误报——
CHANGELOG 自己就记着「这条不适合做成常驻判据」）。判据：同一表格块内，每个数据行的单元格数
必须等于表头；被反斜杠转义的竖线不算分隔。断链**不**做常驻判据（散文里的伪链接会误报），
此处只钉表格。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SEP_ROW = re.compile(r"^\|[\s:\-|]+\|?$")


def _cells(line: str) -> int:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return len(re.split(r"(?<!\\)\|", s))


def table_mismatches(root: Path) -> list:
    """→ ["文件:行 表头N列 vs 数据M列", ...]（纯函数，变异自证直接喂文本也行）。"""
    out = []
    files = sorted(list(root.glob("*.md")) + list((root / "docs").rglob("*.md")))
    for p in files:
        if ".rivet" in p.parts:
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
        in_table = False
        header_n = 0
        for i, ln in enumerate(lines, 1):
            st = ln.strip()
            if st.startswith("|") and st.count("|") >= 2:
                n = _cells(ln)
                if not in_table:
                    in_table, header_n = True, n
                elif _SEP_ROW.match(st) and set(st) <= set("|-: "):
                    continue
                elif n != header_n:
                    out.append("%s:%d 表头%d列 vs 数据%d列"
                               % (p.relative_to(root).as_posix(), i, header_n, n))
            else:
                in_table, header_n = False, 0
    return out


class MarkdownTableTest(unittest.TestCase):
    def test_repo_tables_are_consistent(self):
        bad = table_mismatches(ROOT)
        self.assertEqual([], bad[:10], "表格列数不齐（修复指引：补/删该行的 |，或转义字面竖线）")

    def test_mutation_is_caught(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "docs").mkdir()
            (d / "a.md").write_text(
                "| h1 | h2 |\n|---|---|\n| a | b |\n| c |\n", encoding="utf-8")
            bad = table_mismatches(d)
        self.assertEqual(1, len(bad), bad)


if __name__ == "__main__":
    unittest.main()
