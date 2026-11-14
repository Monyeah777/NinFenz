#!/usr/bin/env python3
"""docs/meta/VERSION-MATRIX.md 契约：版本矩阵必须「行数/状态口径/双源/基线不手写」自洽。

为什么必须有：这张表是「版本 ↔ 方案 ↔ 能力」的单点映射，靠 CHANGELOG 与编号方案双源核验。
本轮修真实陈旧：v0.92 行标 PENDING，而 CHANGELOG 已有 [0.92] - 2026-09-14 发布记录
（v0.93 亦已收口）→ 改标 DONE；并补「§现状对照」「§复现与引用口径」
（行数 29 / 基线来自 repo_stats / 3 例判据）。
本判据把行数、状态符号纪律、CHANGELOG 对应标题、repo_stats 两键、矩阵判据全部活绑定。

范围：只判本文与 CHANGELOG/repo_stats/矩阵判据事实自洽（不改历史行）。
同族判据：test_version_matrix.py（3 例）/ test_version_map.py / test_verifier_version.py /
test_doc_hygiene.py。
契约：最后更新位 + 复核、行数 29、无待定行、CHANGELOG 有对应标题、repo_stats 两键被点名、
现状对照 + 复现两命令、双源口径。
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "meta" / "VERSION-MATRIX.md"
CHANGELOG = ROOT / "CHANGELOG.md"
STATS = ROOT / "protocol" / "repo_stats.json"
SECTIONS = ("## 现状对照", "## 复现与引用口径")
DONE = chr(0x2705)
PENDING = chr(0x23F3)


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"版本矩阵不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("版本矩阵为空")
    return text


def rows(text: str) -> list:
    body = text.split("## 现状对照")[0]
    return [ln for ln in body.splitlines()
            if ln.startswith("| ") and not ln.startswith("| 版本")
            and not ln.startswith("| 面") and not ln.startswith("|---")]


def matrix_issues(text: str) -> list:
    issues = []
    if not text.startswith("# VERSION-MATRIX"):
        issues.append("缺标题「# VERSION-MATRIX · 版本 × 方案 × 能力」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    body = rows(text)
    if len(body) != 29:
        issues.append(f"行数已变（{len(body)}）")
    if "**29**" not in text:
        issues.append("未写 29 行")
    pending = [ln for ln in body if PENDING in ln]
    if pending:
        issues.append(f"仍有待定行（{len(pending)}）")
    if (PENDING + " 0") not in text:
        issues.append("未写「待定 0」")
    changelog = CHANGELOG.read_text(encoding="utf-8")
    for ver in ("## [0.92] - 2026-09-14", "## [0.93] - 2026-10-05"):
        if ver not in changelog:
            issues.append(f"CHANGELOG 缺标题：{ver}")
    if ("2026-09-14 " + DONE) not in text:
        issues.append("v0.92 行未改标 DONE")
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    for key in ("baseline_checks", "baseline_pass"):
        if key not in stats:
            issues.append(f"repo_stats 缺键：{key}")
        if key not in text:
            issues.append(f"正文未点名：{key}")
    if "**3 例**" not in text:
        issues.append("未写 3 例判据")
    if "CHANGELOG" not in text:
        issues.append("缺双源口径（CHANGELOG）")
    if "不在此手写" not in text and "不手写" not in text:
        issues.append("缺「基线不手写」纪律")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python -m pytest desktop/tests/test_version_matrix.py",
                "protocol/repo_stats.json"):
        if cmd not in text:
            issues.append(f"复现口径缺要素：{cmd}")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class VersionMatrixDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_matrix_matches_contract(self):
        self.assertEqual([], matrix_issues(self.text), "版本矩阵不满足契约")

    def test_matrix_live(self):
        self.assertEqual(29, len(rows(self.text)))
        changelog = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn("## [0.92] - 2026-09-14", changelog)
        stats = json.loads(STATS.read_text(encoding="utf-8"))
        self.assertEqual(42, int(stats["baseline_checks"]))
        self.assertEqual(76, int(stats["baseline_pass"]))

    def test_contract_catches_mutations(self):
        """变异自证：回退待定 / 行数回退 / 缺基线键 / 缺判据数 / 缺命令。"""
        back = self.text.replace("2026-09-14 " + DONE, "2026-09-14 " + PENDING)
        self.assertTrue(any("待定" in i for i in matrix_issues(back)))
        old = self.text.replace("**29**", "**27**")
        self.assertTrue(any("29" in i for i in matrix_issues(old)))
        no_s = self.text.replace("baseline_pass", "pass_count")
        self.assertTrue(any("baseline_pass" in i for i in matrix_issues(no_s)))
        no_c = self.text.replace("**3 例**", "**2 例**")
        self.assertTrue(any("3 例" in i for i in matrix_issues(no_c)))
        no_cmd = self.text.replace("python -m pytest desktop/tests/test_version_matrix.py",
                                   "跑矩阵")
        self.assertTrue(any("test_version_matrix" in i for i in matrix_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_matrix.md")


if __name__ == "__main__":
    unittest.main()
