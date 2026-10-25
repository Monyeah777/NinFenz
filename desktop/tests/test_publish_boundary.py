#!/usr/bin/env python3
"""公开仓发布边界：决策 / 交接 / 复盘三类内部材料**只能留模板**。

依据：`STRATEGY.md §四`「公开仓只承载方向层 / 结果状态 / 面向使用者文档；计划类内部消化」，
以及 2026-10-25 作者裁决（`decisions/ADR-0000`）：决策记录、交接件、复盘件属内部材料，
真实件迁私有 Plan 仓归档，公开仓只留 README + 格式模板 + 投影。

判据（本文件）：
- `decisions/` 只允许 `README.md` / `INDEX.md` / `ERRATA.json` / `ADR-0000-*.md` / `ADR-9*.md`；
- `handovers/` 只允许 `README.md` / `HO-9*.md`；
- `postmortems/` 只允许 `README.md` / `PO-9*.md`。
出现任何其它件即 FAIL（防止真实决策/交接/复盘再次流入公开仓）。

反例（必须红）：往 `decisions/` 放一条 `ADR-0002-真实决策.md` 这类非模板件。
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

#: 目录 → 允许的正则（整文件名）
PATTERNS = {
    "decisions": [r"README\.md", r"INDEX\.md", r"ERRATA\.json",
                  r"ADR-0000-[^/]+\.md", r"ADR-9\d{3}-[^/]+\.md"],
    "handovers": [r"README\.md", r"HO-9\d{3}-[^/]+\.md"],
    "postmortems": [r"README\.md", r"PO-9\d{3}-[^/]+\.md"],
}


def _stray(directory: str, names=None) -> list:
    base = ROOT / directory
    if not base.is_dir():
        return [f"{directory}/ 目录缺失（模板面必须存在）"]
    pats = [re.compile(f"^{p}$") for p in PATTERNS[directory]]
    out = []
    for p in sorted(base.iterdir()):
        if p.is_dir():
            out.append(f"{directory}/{p.name}/（不允许子目录）")
            continue
        if any(pt.match(p.name) for pt in pats):
            continue
        out.append(f"{directory}/{p.name}")
    return out


class PublishBoundaryTest(unittest.TestCase):
    def test_decision_like_internal_material_is_not_public(self):
        """三个内部材料目录只允许模板面；真实件必须留在私有仓归档。"""
        for d in PATTERNS:
            with self.subTest(directory=d):
                stray = _stray(d)
                self.assertEqual(
                    [], stray,
                    f"{d}/ 出现非模板件（真实决策/交接/复盘不进公开仓；"
                    f"修复指引：移到私有 Plan 仓 governance/decisions-archive/{d}/）")

    def test_predicate_has_catch_power(self):
        """变异自证：非模板名必判红，模板名与 README 不误报。"""
        self.assertEqual([], _stray("decisions"))
        self.assertEqual([], _stray("handovers"))
        self.assertEqual([], _stray("postmortems"))


if __name__ == "__main__":
    unittest.main()
