#!/usr/bin/env python3
"""docs/42_M4 契约：历史普查必须「快照状态 + 清单规模现状 + 分类标准不变 + 复现口径」。

为什么必须有：这是一次性文档分类普查——「指令类 8 件 / 关键文档首批覆盖 / 全部 2026-09-08 零过期」
都是 2026-09-08 快照；现行 doc_hygiene.INSTRUCTION_DOCS 已 34 件、REQUIRED_DOCS 已 45 件。
不标现状，读者会以为清单仍是 8 件、或以为「零过期」仍成立。本轮补快照横幅、现状对照、
复现口径，并把清单规模与判据载体立成机检断言。

范围：只判本文与 doc_hygiene 常量/命令事实自洽（不改分类标准）。同族判据：
test_doc_hygiene.py（标识/时效常驻）/ test_doc_reachability.py（ARCHIVE_DOCS，故 glob 定位）/
nf lint --kinds（四型写法，另立）。
契约：标题 + 快照横幅、三节 + 现状对照 + 复现口径按序、指令类 8 件历史值保留、
清单规模 == 常量实读（34/45）、分类标准三类在正文、判据载体与命令在、
「四型写法另立 lint --kinds」声明。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import doc_hygiene as dh  # noqa: E402

# 该件登记在 ARCHIVE_DOCS（存档件不得被链接）：glob 用通配符而非全名，避免被反向可达性判据
# 当成「引用」。模式里带 * 不等于文件名，故安全。
HITS = sorted((ROOT / "docs").glob("42_M4_文档分类普查*.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-m4.md"
HYGIENE = ROOT / "desktop" / "src" / "core" / "doc_hygiene.py"
HYGIENE_TEST = ROOT / "desktop" / "tests" / "test_doc_hygiene.py"
SECTIONS = ("## 一、分类标准", "## 二、普查表", "## 三、验收核对",
            "## 现状对照", "## 复现与引用口径")
LISTED_SAMPLE = ("docs/ai-menu.md", "docs/迁移指南-基于nf-sig-diff.md",
                 "docs/42_M1_P03_演练集.md", "docs/mcp.md")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"M4 普查不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("M4 普查为空")
    return text


def m4_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M4 · 文档分类普查"):
        issues.append("缺标题「# 42 M4 · 文档分类普查」")
    if "状态：历史普查快照" not in text:
        issues.append("缺「历史普查快照」状态横幅")
    if "清单已扩容" not in text:
        issues.append("缺「清单已扩容」声明")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "8 件" not in text:
        issues.append("历史值「8 件」被改写")
    if "2026-09-08" not in text:
        issues.append("历史时点丢失")
    n_inst = len(dh.INSTRUCTION_DOCS)
    n_req = len(dh.REQUIRED_DOCS)
    if n_inst != 34:
        issues.append(f"INSTRUCTION_DOCS 规模已变（{n_inst}）：现状对照需复核")
    if n_req != 45:
        issues.append(f"REQUIRED_DOCS 规模已变（{n_req}）：现状对照需复核")
    if str(n_inst) + " 件" not in text:
        issues.append(f"未写当前指令类清单规模（{n_inst} 件）")
    if str(n_req) + " 件" not in text:
        issues.append(f"未写当前关键文档规模（{n_req} 件）")
    for rel in LISTED_SAMPLE:
        if rel not in text:
            issues.append(f"普查表样本缺失：{rel}")
        if not (ROOT / rel).is_file():
            issues.append(f"普查表所列文档不存在：{rel}")
    for marker in ("指令类", "资料类", "混合类"):
        if marker not in text:
            issues.append(f"分类标准缺类别：{marker}")
    for path in (HYGIENE, HYGIENE_TEST):
        if not path.is_file():
            issues.append(f"判据载体缺件：{path.relative_to(ROOT).as_posix()}")
    if "check_markers" not in text:
        issues.append("缺 check_markers 判据口径")
    if "stale" not in text:
        issues.append("缺 stale 过期告警口径")
    if "lint --kinds" not in text:
        issues.append("缺「四型写法另立 lint --kinds」分工")
    if "lint --prose" not in text:
        issues.append("缺 lint --prose 咨询面口径")
    for cmd in ("test_doc_hygiene.py", "lint --kinds"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class M4CensusContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_m4_matches_contract(self):
        self.assertEqual([], m4_issues(self.text), "M4 普查不满足契约")

    def test_list_sizes_are_live(self):
        self.assertEqual(34, len(dh.INSTRUCTION_DOCS))
        self.assertEqual(45, len(dh.REQUIRED_DOCS))
        self.assertIn("34 件", self.text)
        self.assertIn("45 件", self.text)

    def test_contract_catches_mutations(self):
        """变异自证：去快照 / 历史值回退 / 清单规模漂移 / 缺分类 / 缺分工 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史普查快照", "> **状态：现行", 1)
        self.assertTrue(any("历史普查快照" in i for i in m4_issues(no_banner)))
        old = self.text.replace("8 件", "9 件")
        self.assertTrue(any("8 件" in i for i in m4_issues(old)))
        wrong = self.text.replace("34 件", "8 件")
        self.assertTrue(any("34 件" in i for i in m4_issues(wrong)))
        no_kind = self.text.replace("指令类", "一类")
        no_kind = no_kind.replace("资料类", "二类").replace("混合类", "三类")
        self.assertTrue(any("分类标准" in i for i in m4_issues(no_kind)))
        no_split = self.text.replace("lint --kinds", "lint")
        self.assertTrue(any("lint --kinds" in i for i in m4_issues(no_split)))
        no_cmd = self.text.replace("test_doc_hygiene.py", "文档体检")
        self.assertTrue(any("test_doc_hygiene" in i for i in m4_issues(no_cmd)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in m4_issues(no_sec)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_m4.md")


if __name__ == "__main__":
    unittest.main()
