#!/usr/bin/env python3
"""docs/patterns.md 契约：实践包文档必须「7 条全 active/6 必填键/2 值词表」与注册表一致。

为什么必须有：这页是「实践包货架」的唯一说明——pattern 条数、必填键、status 词表、
投影件与真源的关系，任何一项漂移都会让新增/审阅 pattern 的人判错口径。
本轮补「§现状对照」「§复现与引用口径」，并把 7 个 id 逐条与注册表活绑定
（例：single-source-truth 的投影件就是 patterns/INDEX.md 本身）。

范围：只判本文与 core/patterns/INDEX 投影事实自洽（不改 pattern 件）。
同族判据：test_governance_faces.py / test_package_index.py / test_doc_hygiene.py。
契约：最后更新位 + 复核、7 条 id 全列、全 active、6 必填键、2 值词表、INDEX 投影对账、
现状对照 + 复现三命令、INDEX 生成物纪律、MCP 面两口径。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import patterns as pt  # noqa: E402

DOC = ROOT / "docs" / "patterns.md"
SECTIONS = ("## 是什么", "## 入库铁律（可证性）", "## 怎么用", "## 现状对照",
            "## 复现与引用口径")
IDS = ("dependency-direction", "error-message-guidance", "fail-closed-verification",
       "predicate-single-source", "single-source-truth", "verifier-must-run",
       "worktree-vs-index")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"实践包文档不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("实践包文档为空")
    return text


def registry() -> dict:
    _issues, _warns, stats = pt.scan(str(ROOT))
    return stats


def patterns_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 实践包（patterns）"):
        issues.append("缺标题「# 实践包（patterns）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    stats = registry()
    if stats.get("patterns") != 7:
        issues.append(f"pattern 数已变（{stats.get('patterns')}）")
    if sorted(stats.get("ids") or []) != sorted(IDS):
        issues.append(f"pattern id 集合已变：{stats.get('ids')}")
    for pid in IDS:
        if pid not in text:
            issues.append(f"正文缺 pattern：{pid}")
    for e in pt.entries(str(ROOT)):
        fm = e.get("fm") or {}
        if fm.get("status") != "active":
            issues.append(f"{fm.get('id')} 非 active（{fm.get('status')}）")
    if "**7 条 pattern 全部 active**" not in text:
        issues.append("未写 7 条全 active")
    keys = tuple(pt.REQUIRED)
    if len(keys) != 6:
        issues.append(f"必填键数已变（{len(keys)}）")
    for key in keys:
        if key not in text:
            issues.append(f"正文缺必填键：{key}")
    if "**6 键**" not in text:
        issues.append("未写 6 必填键")
    if tuple(pt.STATUSES) != ("active", "deprecated"):
        issues.append(f"status 词表已变：{pt.STATUSES}")
    if "**2**：active / deprecated" not in text:
        issues.append("未写 2 值词表")
    if str(pt.INDEX_REL) not in text:
        issues.append("缺投影件路径")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py patterns verify",
                "python scripts/nf.py patterns reindex",
                "python scripts/nf.py patterns for"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "生成物" not in text:
        issues.append("缺「INDEX 是生成物」纪律")
    if "pattern_read" not in text or "nf://repo/pattern/" not in text:
        issues.append("缺 MCP 两口径（pattern_read / 资源 uri）")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class PatternsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_patterns_matches_contract(self):
        self.assertEqual([], patterns_issues(self.text), "实践包文档不满足契约")

    def test_registry_live(self):
        stats = registry()
        self.assertEqual(7, stats["patterns"])
        self.assertEqual(sorted(IDS), sorted(stats["ids"]))
        self.assertTrue(all((e.get("fm") or {}).get("status") == "active"
                            for e in pt.entries(str(ROOT))))
        self.assertEqual(("active", "deprecated"), tuple(pt.STATUSES))

    def test_contract_catches_mutations(self):
        """变异自证：缺 pattern / 缺必填键 / 词表回退 / 缺命令 / 缺生成物纪律。"""
        no_id = self.text.replace("verifier-must-run", "verifier-runs")
        self.assertTrue(any("verifier-must-run" in i for i in patterns_issues(no_id)))
        no_key = self.text.replace("applies_to", "applies")
        self.assertTrue(any("applies_to" in i for i in patterns_issues(no_key)))
        bad_st = self.text.replace("active / deprecated", "active / retired")
        self.assertTrue(any("词表" in i for i in patterns_issues(bad_st)))
        no_cmd = self.text.replace("python scripts/nf.py patterns reindex", "重建索引")
        self.assertTrue(any("reindex" in i for i in patterns_issues(no_cmd)))
        no_gen = self.text.replace("生成物", "文件")
        self.assertTrue(any("生成物" in i for i in patterns_issues(no_gen)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_patterns.md")


if __name__ == "__main__":
    unittest.main()
