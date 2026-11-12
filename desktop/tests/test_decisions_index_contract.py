#!/usr/bin/env python3
"""decisions/INDEX 契约：生成区必须与实时重算逐字节一致，人读指引只能待在标记外。

为什么必须有：INDEX 是决策表的**投影**——表格由各 ADR frontmatter 生成。人工改表格会让索引与
真源漂移（工具 check_projection 会红，但那是运行时才发现）；人工把「怎么用」写进生成区又会在
下一次 reindex 时被覆盖丢失。本轮在 BEGIN/END 标记**外**补「本文件怎么用」与修复指引，并把
「生成区 == dc.render_index(root)」「表格行 ↔ ADR frontmatter 逐行一致」立成文档级契约。

范围：只判索引文件与真源投影的自洽（不碰生成逻辑）。同族判据：
test_decisions.py（工具链语义，含 projection_drift 用例）/
test_adr_0000_contract.py / test_adr_9000_contract.py / test_adr_9001_contract.py（被索引的 ADR）。
契约：标记顺序、生成区逐字节等于 render_index、表格行与 ADR frontmatter 逐行一致、
人读指引在标记外且含修复指引、标记不重复、无漂移。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import decisions as dc  # noqa: E402

INDEX = ROOT / "decisions" / "INDEX.md"
FENCE_END = "<!-- END GENERATED: decisions-index -->"
GUIDANCE_MARKERS = ("本文件怎么用", "勿手改", "nf decisions reindex", "nf decisions verify",
                    "nf decisions show", "ADR-0000", "ADR-9000", "ADR-9001",
                    "ERRATA.json", "私有 Plan 仓")


def load_text(path: Path = INDEX) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"INDEX 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("INDEX 为空")
    return text


def block(text: str) -> str:
    if dc.BEGIN not in text or dc.END not in text:
        return ""
    return text[text.index(dc.BEGIN):text.index(dc.END) + len(dc.END)]


def table_rows(text: str) -> list:
    return [ln.strip() for ln in text.splitlines()
            if ln.strip().startswith("| ADR-")]


def adr_frontmatters() -> list:
    out = []
    for path in sorted((ROOT / "decisions").glob("ADR-*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        fm = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
        fm["path"] = path.name
        out.append(fm)
    return out


def index_issues(text: str) -> list:
    issues = []
    if not text.startswith("# NF 决策记录索引"):
        issues.append("缺标题「# NF 决策记录索引（INDEX）」")
    if text.count(dc.BEGIN) != 1 or text.count(dc.END) != 1:
        issues.append("生成区标记应各出现一次")
    if dc.BEGIN in text and dc.END in text and text.index(dc.BEGIN) > text.index(dc.END):
        issues.append("BEGIN/END 标记顺序颠倒")
    current = block(text)
    expected = dc.render_index(str(ROOT))
    if not current:
        issues.append("缺生成区")
    elif current != expected:
        issues.append("生成区与实时重算不一致（跑 nf decisions reindex）")
    for marker in GUIDANCE_MARKERS:
        if marker not in text:
            issues.append(f"缺人读指引：{marker}")
    before = text[:text.index(dc.BEGIN)] if dc.BEGIN in text else ""
    after = text[text.index(dc.END) + len(dc.END):] if dc.END in text else ""
    if "本文件怎么用" in current:
        issues.append("人读指引不能写在生成区内（reindex 会覆盖）")
    if "本文件怎么用" not in before:
        issues.append("「本文件怎么用」应在生成区之前")
    if "投影修复指引" not in after:
        issues.append("生成区之后缺投影修复指引")
    rows = table_rows(current)
    fms = adr_frontmatters()
    if len(rows) != len(fms):
        issues.append(f"表格行数应等于 ADR 数：{len(rows)} ≠ {len(fms)}")
    by_id = {fm.get("id"): fm for fm in fms}
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 5:
            issues.append(f"表格行列数不足：{row}")
            continue
        adr_id = cells[0]
        fm = by_id.get(adr_id)
        if not fm:
            issues.append(f"表格行引用了不存在的 ADR：{adr_id}")
            continue
        if cells[1] != fm.get("title"):
            issues.append(f"{adr_id} 标题与 frontmatter 不一致")
        if cells[2] != fm.get("status"):
            issues.append(f"{adr_id} 状态与 frontmatter 不一致")
        if cells[3] != fm.get("date"):
            issues.append(f"{adr_id} 日期与 frontmatter 不一致")
        expected_super = "—" if fm.get("superseded_by") in dc.DASH else fm.get("superseded_by")
        if cells[4] != expected_super:
            issues.append(f"{adr_id} 取代列与 frontmatter 不一致")
    if len(text.splitlines()) < 12:
        issues.append("INDEX 过短（缺人读指引）")
    return issues


class DecisionsIndexContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_index_matches_contract(self):
        self.assertEqual([], index_issues(self.text), "decisions/INDEX 不满足契约")

    def test_generated_block_equals_live_projection(self):
        self.assertEqual(dc.render_index(str(ROOT)), block(self.text))

    def test_rows_match_frontmatter(self):
        rows = table_rows(block(self.text))
        by_id = {fm.get("id"): fm for fm in adr_frontmatters()}
        self.assertEqual(len(by_id), len(rows))
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            fm = by_id[cells[0]]
            self.assertEqual(fm.get("title"), cells[1], cells[0])
            self.assertEqual(fm.get("status"), cells[2], cells[0])
            self.assertEqual(fm.get("date"), cells[3], cells[0])

    def test_contract_catches_mutations(self):
        """变异自证：表格行漂移 / 标记缺失 / 指引写进生成区 / 缺修复指引 / 行重复。"""
        drift = self.text.replace(
            "| ADR-9001 | （示例）evidence 字段只写可解析的仓库路径或 checkN |",
                                  "| ADR-9001 | 证据要可解析 |", 1)
        self.assertTrue(any("不一致" in i for i in index_issues(drift)))
        no_mark = self.text.replace(FENCE_END, "", 1)
        self.assertTrue(any("生成区" in i or "标记" in i for i in index_issues(no_mark)))
        inside = self.text.replace(dc.BEGIN, dc.BEGIN + "\n" + "本文件怎么用（错位）", 1)
        self.assertTrue(any("生成区内" in i for i in index_issues(inside)))
        no_hint = self.text.replace("投影修复指引", "修复", 1)
        self.assertTrue(any("修复指引" in i for i in index_issues(no_hint)))
        no_guide = self.text.replace("## 本文件怎么用", "## 用法", 1)
        self.assertTrue(any("本文件怎么用" in i for i in index_issues(no_guide)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_index.md")


if __name__ == "__main__":
    unittest.main()
