#!/usr/bin/env python3
"""docs/interop.md 契约：互操作总览必须「12 种类/入仓 12 面/外部校验 14 行与实现一致」。

为什么必须有：这页是「纯派生、不新增真源」的对外说明——种类数、入仓面数、外部校验结果行数
任何一项漂移，读者就会拿错清单或误判「哪面没被上游接受」。本轮把外部校验表从「9 行混合」改为
**逐面 14 行**（12 导出面 + ccv3(E1) + mcp(E3)），并补「§现状对照」「§复现与引用口径」。
本判据把 KINDS（12）、入仓面（12）、校验报告（14 行 + ok/no-schema/unavailable 分布）、
六条判据、CLI 派生口径全部活绑定。

范围：只判本文与 interop_export / results/interop / 校验报告事实自洽（不改导出实现）。
同族判据：test_interop.py / test_interop_export.py / test_interop_schema_tool.py /
test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、KINDS 12 逐名在文、入仓 12 件、校验 14 行且分布 6/7/1 在文、
六条判据在文、现状对照 + 复现三命令。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import interop_export as ie  # noqa: E402

BT = chr(96)

DOC = ROOT / "docs" / "interop.md"
INTEROP = ROOT / "results" / "interop"
VALIDATION = ROOT / "results" / "interop-schema-validation.md"
SECTIONS = ("## 是什么", "## 怎么用", "## 判据", "## 与其他面关系",
            "## 外部权威校验", "## 现状对照", "## 复现与引用口径")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"互操作总览不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("互操作总览为空")
    return text


def validation_rows() -> list:
    rows = []
    for ln in VALIDATION.read_text(encoding="utf-8").splitlines():
        if ln.startswith("| ") and not ln.startswith("| 面") and not ln.startswith("|---"):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return rows


def interop_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 互操作导出（interop）"):
        issues.append("缺标题「# 互操作导出（interop）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    kinds = list(ie.KINDS)
    if len(kinds) != 12:
        issues.append(f"KINDS 已变（{len(kinds)}）")
    for k in kinds:
        if k not in text:
            issues.append(f"正文缺导出种类：{k}")
    files = sorted(p.stem for p in INTEROP.glob("*.json"))
    if sorted(kinds) != files:
        issues.append(f"入仓面与 KINDS 不一致：{sorted(set(files) ^ set(kinds))}")
    if "**12 件**" not in text:
        issues.append("未写入仓 12 件")
    rows = validation_rows()
    if len(rows) != 14:
        issues.append(f"校验报告行数已变（{len(rows)}）")
    dist = {}
    for r in rows:
        dist[r[3]] = dist.get(r[3], 0) + 1
    if dist != {"ok": 6, "no-schema": 7, "unavailable": 1}:
        issues.append(f"校验分布已变：{dist}")
    if "ok 6 / no-schema 7 / unavailable 1" not in text:
        issues.append("未写校验分布 7/6/1")
    for r in rows:
        fid = r[0].strip(BT)
        if fid not in text:
            issues.append(f"正文缺校验面：{fid}")
    for marker in ("逐字节一致", "fail-closed", "--check"):
        if marker not in text:
            issues.append(f"判据/复现缺要素：{marker}")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py interop --list",
                "python scripts/nf.py interop --check",
                "python -m pytest desktop/tests/test_interop.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "不新增真源" not in text:
        issues.append("缺「不新增真源」口径")
    if "TODO" in text or "待补" in text:
        issues.append("含 TODO/待补 占位")
    return issues


class InteropDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_interop_matches_contract(self):
        self.assertEqual([], interop_issues(self.text), "互操作总览不满足契约")

    def test_kinds_and_validation_live(self):
        self.assertEqual(12, len(ie.KINDS))
        self.assertEqual(sorted(ie.KINDS),
                         sorted(p.stem for p in INTEROP.glob("*.json")))
        rows = validation_rows()
        self.assertEqual(14, len(rows))
        dist = {}
        for r in rows:
            dist[r[3]] = dist.get(r[3], 0) + 1
        self.assertEqual({"ok": 6, "no-schema": 7, "unavailable": 1}, dist)

    def test_contract_catches_mutations(self):
        """变异自证：缺种类 / 分布回退 / 缺校验面 / 缺命令 / 缺不新增真源。"""
        no_kind = self.text.replace("cyclonedx", "cbor")
        self.assertTrue(any("cyclonedx" in i for i in interop_issues(no_kind)))
        bad = self.text.replace("ok 6 / no-schema 7 / unavailable 1", "ok 9 / no-schema 5")
        self.assertTrue(any("6/7/1" in i or "分布" in i for i in interop_issues(bad)))
        no_face = self.text.replace("ccv3", "ccv")
        self.assertTrue(any("ccv3" in i for i in interop_issues(no_face)))
        no_cmd = self.text.replace("python scripts/nf.py interop --check", "自检")
        self.assertTrue(any("--check" in i for i in interop_issues(no_cmd)))
        no_src = self.text.replace("不新增真源", "新增真源")
        self.assertTrue(any("不新增真源" in i for i in interop_issues(no_src)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_interop.md")


if __name__ == "__main__":
    unittest.main()
