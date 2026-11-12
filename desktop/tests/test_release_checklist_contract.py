#!/usr/bin/env python3
"""docs/42_M5_Release-checklist 契约：路径现行 + 自动化入口 + 退役项如实 + 复现口径。

为什么必须有：这份 Release Checklist 写着「VERSION-MATRIX / ROADMAP 同步」，但两件早已归拢到
docs/meta/（裸名失效）；同时它提醒「不钉死运行时计数」（曾停在 check1-32/PASS=51），而现行自动化
体检入口是 nf release / nf stats --check。不修路径，tag 前照抄会找不到文件。本轮修正路径、补
现状对照与复现口径，并把路径真件、命令注册、退役项立成机检断言。

范围：只判本文与 docs/meta / CLI 事实自洽（不改清单项语义）。同族判据：
test_doc_examples.py（文档命令块）/ test_doc_hygiene.py（指令档标识，本件不在清单内故不强制）/
test_doc_reachability.py（ARCHIVE_DOCS，glob 用通配符）。
契约：清单 9 项、Golden Master 已退役（2026-10-11）、路径 docs/meta 双件在文且文件在场、
coverage_summary.sh 在场、nf release / nf stats 子命令在册、quality_baseline EXPECTED_* 常量在、
docs/release.md 现行真源引用、历史提醒 check1-32/PASS=51 保留、现状对照 + 复现口径齐。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import quality_baseline as qb  # noqa: E402

HITS = sorted((ROOT / "docs").glob("42_M5_Release-checklist*.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-checklist.md"
NF = ROOT / "scripts" / "nf.py"
COVER = ROOT / "scripts" / "coverage_summary.sh"
META = (ROOT / "docs" / "meta" / "VERSION-MATRIX.md", ROOT / "docs" / "meta" / "ROADMAP.md")
RELEASE_DOC = ROOT / "docs" / "release.md"
SECTIONS = ("## Golden Master", "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Release Checklist 不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("Release Checklist 为空")
    return text


def checklist_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M5.6 · Release Checklist"):
        issues.append("缺标题「# 42 M5.6 · Release Checklist」")
    if "清单仍现行使用" not in text:
        issues.append("缺「清单仍现行使用」状态声明")
    items = [ln for ln in text.splitlines() if ln.strip().startswith("- [ ]")]
    if len(items) != 9:
        issues.append(f"核验项数应为 9（实测 {len(items)}）")
    if "已退役" not in text or "2026-10-11" not in text:
        issues.append("Golden Master 退役口径缺失（标 2026-10-11 已退役）")
    for rel, label in zip(META, ("VERSION-MATRIX", "ROADMAP"), strict=True):
        if not rel.is_file():
            issues.append(f"路径真件不存在：{rel.relative_to(ROOT).as_posix()}")
        if ("docs/meta/" + rel.name) not in text:
            issues.append(f"正文未写现行路径：docs/meta/{rel.name}（{label}）")
    if not COVER.is_file():
        issues.append("缺覆盖率脚本：scripts/coverage_summary.sh")
    if "bash scripts/coverage_summary.sh" not in text:
        issues.append("缺覆盖率命令引用")
    for name in ("EXPECTED_CHECKS", "EXPECTED_PASS"):
        if not hasattr(qb, name):
            issues.append(f"quality_baseline 缺常量：{name}")
    nf = NF.read_text(encoding="utf-8")
    for sub in ("release", "stats"):
        if "add_parser(" + chr(34) + sub + chr(34) not in nf:
            issues.append(f"CLI 缺子命令：nf {sub}")
    for cmd in ("python scripts/nf.py release --plan", "python scripts/nf.py stats --check",
                "bash verify.sh --checks-only"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "docs/release.md" not in text:
        issues.append("未指向发布流程真源 docs/release.md")
    if not RELEASE_DOC.is_file():
        issues.append("缺 docs/release.md")
    if "check1-32/PASS=51" not in text:
        issues.append("历史提醒（check1-32/PASS=51）被改写")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ReleaseChecklistContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_checklist_matches_contract(self):
        self.assertEqual([], checklist_issues(self.text), "Release Checklist 不满足契约")

    def test_paths_and_cli_live(self):
        for rel in META:
            self.assertTrue(rel.is_file(), rel)
        self.assertTrue(COVER.is_file())
        nf = NF.read_text(encoding="utf-8")
        for sub in ("release", "stats"):
            self.assertIn("add_parser(" + chr(34) + sub + chr(34), nf)

    def test_contract_catches_mutations(self):
        """变异自证：去状态声明 / 裸名回退 / 退役项翻案 / 缺复现命令 / 缺现状对照 / 缺真源引用。"""
        no_status = self.text.replace("清单仍现行使用", "清单已作废")
        self.assertTrue(any("现行使用" in i for i in checklist_issues(no_status)))
        bare = self.text.replace("docs/meta/VERSION-MATRIX.md", "VERSION-MATRIX.md")
        self.assertTrue(any("VERSION-MATRIX" in i for i in checklist_issues(bare)))
        revived = self.text.replace("已退役", "现行")
        self.assertTrue(any("退役" in i for i in checklist_issues(revived)))
        no_cmd = self.text.replace("python scripts/nf.py release --plan", "跑发布")
        self.assertTrue(any("release --plan" in i for i in checklist_issues(no_cmd)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in checklist_issues(no_sec)))
        no_ref = self.text.replace("docs/release.md", "发布文档")
        self.assertTrue(any("release.md" in i for i in checklist_issues(no_ref)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_checklist.md")


if __name__ == "__main__":
    unittest.main()
