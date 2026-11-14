#!/usr/bin/env python3
"""标准答题卡契约：生成物必须「口径段齐 / 4 张卡 / 计数与真源一致 / --check 新鲜」。

为什么必须有：这是生成物（scripts/geo_export.py --write），禁止手改；它又是 GEO 出口里
「按问题形态聚合」的唯一入口——覆盖数、分层数、绑定总量、不可达清单，任何一项与真源不一致都说明
生成物陈旧或手改过。本轮在生成器里补了「§口径与复现」段（生成物纪律 / 计数来源 / 可达性口径 /
投影定位），并重新生成；判据把内容与两个真源双向绑定，并实跑 --check 验新鲜。

范围：只判本文与 geo_export 生成逻辑/两份真源事实自洽。
同族判据：geo_export --check（本判据会实跑）/ check40 / test_doc_hygiene.py。
契约：头部生成声明、§口径与复现 4 条、卡 1–4 齐、覆盖 370/332/38/194/206、分层 5 值、
绑定 1200、不可达 38 条披露、--check 无差异。
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOC = ROOT / "docs" / "standards" / "answer-cards.md"
CATALOG = ROOT / "protocol" / "standards_catalog.json"
BINDING = ROOT / "protocol" / "standards_binding.json"
CARDS = ("## 卡 1 · 哪些标准提供扩展点？", "## 卡 2 · 各层有哪些标准？",
         "## 卡 3 · 哪些标准被域包绑定、绑了多少次？", "## 卡 4 · 哪些标准本机不可达？（诚实披露）")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"标准答题卡不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("标准答题卡为空")
    return text


def facts() -> dict:
    c = json.loads(CATALOG.read_text(encoding="utf-8"))
    b = json.loads(BINDING.read_text(encoding="utf-8"))
    cov = c["coverage"]
    return {"standards": len(c["standards"]), "reachable": cov["reachable"],
            "unreachable": cov["unreachable"], "bodies": cov["bodies"],
            "depends": cov["depends_edges"], "by_layer": cov["by_layer"],
            "bindings": b["bindings_total"]}


def cards_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 标准目录 · 可引用卡（按问题形态）"):
        issues.append("缺标题「# 标准目录 · 可引用卡（按问题形态）」")
    if "禁止手改" not in text:
        issues.append("缺「生成物，禁止手改」声明")
    if "## 口径与复现" not in text:
        issues.append("缺「§口径与复现」段")
    for marker in ("--write", "--check", "check40", "投影"):
        if marker not in text:
            issues.append(f"口径段缺：{marker}")
    f = facts()
    labels = [f"**{f[key]}**" for key in
              ("standards", "reachable", "unreachable", "bodies", "depends")]
    for label in labels:
        if label not in text:
            issues.append(f"覆盖数缺：{label}")
    for layer, n in f["by_layer"].items():
        if f"{layer} {n}" not in text:
            issues.append(f"分层数缺：{layer} {n}")
    if f"绑定总量 **{f['bindings']}**" not in text:
        issues.append(f"绑定总量缺：{f['bindings']}")
    positions = [text.find(s) for s in CARDS]
    for card, pos in zip(CARDS, positions, strict=True):
        if pos < 0:
            issues.append(f"缺卡：{card}")
    if all(p >= 0 for p in positions) and positions != sorted(positions):
        issues.append("卡顺序不对")
    if f"不可达 **{f['unreachable']}**" not in text:
        issues.append("未写不可达数")
    return issues


class AnswerCardsDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_cards_match_contract(self):
        self.assertEqual([], cards_issues(self.text), "标准答题卡不满足契约")

    def test_freshness(self):
        proc = subprocess.run([sys.executable, "scripts/geo_export.py", "--check"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺口径段 / 计数回退 / 缺卡 / 缺生成声明。"""
        no_sec = self.text.replace("## 口径与复现", "## 说明")
        self.assertTrue(any("口径与复现" in i for i in cards_issues(no_sec)))
        old = self.text.replace("**370**", "**360**")
        self.assertTrue(any("370" in i for i in cards_issues(old)))
        no_card = self.text.replace("## 卡 4 · 哪些标准本机不可达？（诚实披露）", "## 卡 4")
        self.assertTrue(any("卡 4" in i for i in cards_issues(no_card)))
        no_gen = self.text.replace("禁止手改", "可以手改")
        self.assertTrue(any("禁止手改" in i for i in cards_issues(no_gen)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_cards.md")


if __name__ == "__main__":
    unittest.main()
