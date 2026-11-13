#!/usr/bin/env python3
"""ST 清单契约：29 规则 / M6 S17 R6 / W1=M / 自动面 1 / 待定 3 必须与真源一致。

为什么必须有：这是 ST 制卡的勾选面，规则真源是 protocol/st_quality.json——清单**不重述规则**，
所以一旦清单里的级别与真源不一致（本轮实测 W1 标 S 而真源判 M），M 级硬缺口就会被当成建议项放过。
本轮修该漂移，并补「§现状对照」「§复现与引用口径」：29 条、M 6 / S 17 / R 6、4 个 scope、
自动面仅 V2、待作者定 3 项、A-S3 校验器已有原型 nf st-validate。

范围：只判本文与 st_quality 真源/扫描统计/CLI 事实自洽（不改规则）。
同族判据：test_quality_gate.py / test_quality_45.py / test_doc_hygiene.py / test_doc_examples.py。
契约：最后更新位 + 复核、29 条、级别分布逐值、W1 行级别为 M、4 scope、自动面 1、待定 3、draft、
st-validate 原型口径、现状对照 + 复现两命令（首行须为 nf 形态，避免 doc-examples 普查误报）。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import st_quality as st  # noqa: E402

DOC = ROOT / "docs" / "st-quality-checklist.md"
DECL = ROOT / "protocol" / "st_quality.json"
SECTIONS = ("## 现状对照", "## 复现与引用口径", "## 1. 角色卡（C）",
            "## 2. 世界书（W）", "## 3. MVU 变量（V）", "## 4. 跨类（X）")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"ST 质量清单不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("ST 质量清单为空")
    return text


def facts() -> dict:
    d = json.loads(DECL.read_text(encoding="utf-8"))
    rules = d["rules"]
    levels = {}
    for r in rules:
        levels[r["level"]] = levels.get(r["level"], 0) + 1
    w1 = next(r for r in rules if r["id"] == "W1")
    _i, _w, stats = st.scan(str(ROOT))
    return {"rules": len(rules), "levels": levels, "w1": w1["level"],
            "scopes": len(d["scope_vocabulary"]), "status": d["status"],
            "pending": len(d["pending"]), "auto": stats["artifact_checked"]}


def checklist_issues(text: str) -> list:
    issues = []
    if not text.startswith("# ST 制卡质量自查清单"):
        issues.append("缺标题「# ST 制卡质量自查清单（v0 · 人工版）」")
    if "最后更新：" not in text:
        issues.append("缺「最后更新」位")
    if "复核" not in text:
        issues.append("缺「复核」说明")
    f = facts()
    if f["rules"] != 29:
        issues.append(f"规则数已变（{f['rules']}）")
    if f["levels"] != {"M": 6, "S": 17, "R": 6}:
        issues.append(f"级别分布已变：{f['levels']}")
    if f["w1"] != "M":
        issues.append(f"真源 W1 级别已变（{f['w1']}）")
    if "| W1 | M |" not in text:
        issues.append("清单 W1 行级别不是 M（与真源不一致）")
    if f["scopes"] != 4:
        issues.append(f"scope 数已变（{f['scopes']}）")
    if f["pending"] != 3:
        issues.append(f"待作者定项已变（{f['pending']}）")
    if f["status"] != "draft":
        issues.append(f"规范状态已变（{f['status']}）")
    for label in ("**29**", "**M 6 / S 17 / R 6**", "**1 项**", "**3 项**", "**draft**"):
        if label not in text:
            issues.append(f"现状缺要素：{label}")
    if "st-validate" not in text:
        issues.append("缺 A-S3 校验器原型口径")
    if "尚未" not in text:
        issues.append("缺「尚未全机检」边界")
    positions = [text.find(s) for s in SECTIONS]
    for section, pos in zip(SECTIONS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺段：{section}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("节顺序不对")
    for cmd in ("python scripts/nf.py st-validate",
                "python -m pytest desktop/tests/test_quality_gate.py"):
        if cmd not in text:
            issues.append(f"复现口径缺命令：{cmd}")
    if "唯一真源" not in text:
        issues.append("缺「规则真源唯一」口径")
    if "TODO" in text:
        issues.append("含 TODO 占位")
    return issues


class StChecklistDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_checklist_matches_contract(self):
        self.assertEqual([], checklist_issues(self.text), "ST 质量清单不满足契约")

    def test_rules_live(self):
        f = facts()
        self.assertEqual(29, f["rules"])
        self.assertEqual({"M": 6, "S": 17, "R": 6}, f["levels"])
        self.assertEqual("M", f["w1"])
        self.assertEqual("draft", f["status"])
        self.assertEqual(1, f["auto"])

    def test_contract_catches_mutations(self):
        """变异自证：W1 级别回退 / 级别分布回退 / 待定数回退 / 缺校验器 / 缺命令。"""
        old_w1 = self.text.replace("| W1 | M |", "| W1 | S |")
        self.assertTrue(any("W1" in i for i in checklist_issues(old_w1)))
        old_lv = self.text.replace("**M 6 / S 17 / R 6**", "**M 5 / S 18 / R 6**")
        self.assertTrue(any("M 6" in i for i in checklist_issues(old_lv)))
        old_pd = self.text.replace("**3 项**", "**2 项**")
        self.assertTrue(any("3 项" in i for i in checklist_issues(old_pd)))
        no_cli = self.text.replace("st-validate", "st-check")
        self.assertTrue(any("st-validate" in i for i in checklist_issues(no_cli)))
        no_cmd = self.text.replace("python scripts/nf.py st-validate <卡.json> --json", "自检")
        self.assertTrue(any("st-validate" in i for i in checklist_issues(no_cmd)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_st.md")


if __name__ == "__main__":
    unittest.main()
