#!/usr/bin/env python3
"""docs/42_M5_工程收口 契约：收口记录必须「快照状态 + 交付物现状 + bench 边界澄清 + 复现口径」。

为什么必须有：这是 42 收口记录——五个交付面（覆盖率 CI / VERSION-MATRIX / quality_all /
gates_all / 设计自查+Release checklist）必须仍可核对；更关键的是**退役边界容易被误读**：
遗留段原文写「bench 已随 L3 端壳线退役移除」，但 nf bench（执行结果跑分台 CLI）今天仍在册——
端壳基准 ≠ CLI 跑分台。本轮补快照横幅、现状对照（交付物 + 门禁规模 + bench 澄清）、复现口径，
并把载体在场/CLI 注册/历史值保留立成机检断言。

范围：只判本文与交付物/CLI 事实自洽（不改收口结论）。同族判据：
test_version_matrix.py（矩阵常驻）/ test_release_checklist_contract.py（Release checklist）/
test_doc_reachability.py（ARCHIVE_DOCS，glob 用通配符）。
契约：快照横幅、交付明细 + 五维 + 遗留 + 现状对照 + 复现口径、历史值（check1-27/PASS=41/85%/
4065/605）保留、五个交付物在场、CLI nf bench 注册、bench 边界澄清（CLI 在册 / 端壳基准退役）、
L3_FROZEN 引用。
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HITS = sorted((ROOT / "docs").glob("42_M5_工程收口*.md"))
DOC = HITS[0] if HITS else ROOT / "docs" / "missing-closure.md"
NF = ROOT / "scripts" / "nf.py"
ARTIFACTS = (
    ".github/workflows/coverage.yml",
    "scripts/coverage_summary.sh",
    "scripts/quality_all.sh",
    "scripts/gates_all.sh",
    "docs/42_M5_设计自查清单.md",
    "docs/42_M5_Release-checklist.md",
    "docs/meta/VERSION-MATRIX.md",
    "desktop/tests/test_version_matrix.py",
    "docs/L3_FROZEN.md",
)
SECTIONS = ("## 交付明细", "## 五维总评", "## 遗留", "## 现状对照", "## 复现与引用口径")
HISTORICAL = ("check1-27", "PASS=41", "85%", "4065", "605")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"收口记录不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("收口记录为空")
    return text


def closure_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 42 M5 · 工程质量面补齐"):
        issues.append("缺标题「# 42 M5 · 工程质量面补齐」")
    if "状态：历史收口记录" not in text:
        issues.append("缺「历史收口记录」状态横幅")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for marker in HISTORICAL:
        if marker not in text:
            issues.append(f"历史值被改写：{marker}")
    for rel in ARTIFACTS:
        if not (ROOT / rel).is_file():
            issues.append(f"交付物不存在：{rel}")
    nf = NF.read_text(encoding="utf-8")
    if 'add_parser("bench"' not in nf:
        issues.append("CLI 缺 bench 子命令（澄清点失效）")
    if "nf bench" not in text:
        issues.append("缺 nf bench CLI 澄清")
    if "端壳基准" not in text:
        issues.append("缺「端壳基准」退役边界表述")
    if "L3_FROZEN.md" not in text:
        issues.append("缺 L3_FROZEN 引用")
    if "check1-42" not in text:
        issues.append("现状对照缺当前门禁规模（check1-42）")
    if "PASS=75" not in text:
        issues.append("现状对照缺现行 PASS=75 实跑值")
    for cmd in ("python scripts/nf.py bench --help", "bash scripts/gates_all.sh",
                "bash scripts/quality_all.sh", "bash verify.sh --checks-only"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class ClosureRecordContractTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_closure_matches_contract(self):
        self.assertEqual([], closure_issues(self.text), "收口记录不满足契约")

    def test_deliverables_and_bench_live(self):
        for rel in ARTIFACTS:
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertIn('add_parser("bench"', NF.read_text(encoding="utf-8"))

    def test_contract_catches_mutations(self):
        """变异自证：去快照 / 历史值回退 / bench 澄清 / 缺 L3 / 缺现状对照 / 缺复现命令。"""
        no_banner = self.text.replace("> **状态：历史收口记录", "> **状态：现行", 1)
        self.assertTrue(any("历史收口记录" in i for i in closure_issues(no_banner)))
        old = self.text.replace("PASS=75", "PASS=41")
        self.assertTrue(any("PASS=75" in i for i in closure_issues(old)))
        no_bench = self.text.replace("nf bench", "跑分台")
        self.assertTrue(any("bench" in i for i in closure_issues(no_bench)))
        no_l3 = self.text.replace("L3_FROZEN.md", "冻结说明")
        self.assertTrue(any("L3_FROZEN" in i for i in closure_issues(no_l3)))
        no_sec = self.text.replace("## 现状对照（2026-11-13 · 以实跑为准）", "## 表格")
        self.assertTrue(any("缺段" in i for i in closure_issues(no_sec)))
        no_cmd = self.text.replace("bash scripts/gates_all.sh", "跑闸门")
        self.assertTrue(any("gates_all" in i for i in closure_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_closure.md")


if __name__ == "__main__":
    unittest.main()
