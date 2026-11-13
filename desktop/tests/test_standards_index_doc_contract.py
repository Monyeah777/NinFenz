#!/usr/bin/env python3
"""标准主索引契约：370 条逐条 / 每行七字段 / 口径段齐 / --check 新鲜。

为什么必须有：这是 GEO 出口的主索引——370 条标准各一个稳定锚，生成式引擎直接引用它。
覆盖数、层分布、逐行字段（可达·HTTP·探针日期·扩展点·绑定·URL）、以及「本页是生成物」纪律，
任何一项漂移都会让引用方拿到错锚或错数。本轮在生成器里补「§口径与复现」段（生成物纪律 /
每行字段释义 / 锚点用法 / 其它面指引 / 投影定位）并重新生成；判据把索引与真源双向绑定，
并以子进程实跑 --check 验新鲜度。

范围：只判本文与 geo_export 生成逻辑/两份真源事实自洽。
同族判据：geo_export --check（本判据会实跑）/ check40 / test_doc_hygiene.py。
契约：标题 + 生成声明、§口径与复现 5 条、370 个锚、覆盖数、层分布、逐行七字段结构、
--check 零差异、答案卡互指。
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BT = chr(96)

DOC = ROOT / "docs" / "standards" / "index.md"
CATALOG = ROOT / "protocol" / "standards_catalog.json"
ENTRY = re.compile("^### " + BT + "([a-z0-9][a-z0-9._-]*)" + BT + "$")
LAYER_RE = re.compile(
    r"^- .+ · .+ · 层 (data|eng|form|gov|iface) · 可达 (是|否)（.+）"
    r" · 扩展点 .* · 绑定 .* · .+$")


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"标准主索引不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("标准主索引为空")
    return text


def facts() -> dict:
    c = json.loads(CATALOG.read_text(encoding="utf-8"))
    cov = c["coverage"]
    return {"standards": len(c["standards"]), "reachable": cov["reachable"],
            "unreachable": cov["unreachable"], "bodies": cov["bodies"],
            "depends": cov["depends_edges"], "by_layer": cov["by_layer"],
            "ids": [s["id"] for s in c["standards"]]}


def index_issues(text: str) -> list:
    issues = []
    if not text.startswith("# 标准目录 · 可引用索引（GEO 出口）"):
        issues.append("缺标题「# 标准目录 · 可引用索引（GEO 出口）」")
    if "禁止手改" not in text:
        issues.append("缺「生成物，禁止手改」声明")
    if "## 口径与复现" not in text:
        issues.append("缺「§口径与复现」段")
    for marker in ("--write", "--check", "check40", "投影", "layer-", "answer-cards.md"):
        if marker not in text:
            issues.append(f"口径段缺：{marker}")
    f = facts()
    ids = [m.group(1) for m in (ENTRY.match(ln) for ln in text.splitlines()) if m]
    if len(ids) != f["standards"]:
        issues.append(f"锚数 {len(ids)} != 标准数 {f['standards']}")
    if sorted(ids) != sorted(f["ids"]):
        issues.append("锚集合与 catalog 不一致")
    for label in (f"**{f['standards']}**", f"**{f['reachable']}**",
                  f"**{f['unreachable']}**", f"**{f['bodies']}**",
                  f"**{f['depends']}**"):
        if label not in text:
            issues.append(f"覆盖数缺：{label}")
    for layer, n in f["by_layer"].items():
        if f"{layer} {n}" not in text:
            issues.append(f"层分布缺：{layer} {n}")
    lines = text.splitlines()
    bad = 0
    for i, ln in enumerate(lines):
        if not ENTRY.match(ln):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if not LAYER_RE.match(nxt):
            bad += 1
    if bad:
        issues.append(f"行结构不符七字段（{bad} 条）")
    return issues


class StandardsIndexDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_index_matches_contract(self):
        self.assertEqual([], index_issues(self.text), "标准主索引不满足契约")

    def test_freshness(self):
        proc = subprocess.run([sys.executable, "scripts/geo_export.py", "--check"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺口径段 / 锚缺失 / 计数回退 / 行结构破坏。"""
        no_sec = self.text.replace("## 口径与复现", "## 说明")
        self.assertTrue(any("口径与复现" in i for i in index_issues(no_sec)))
        target = "### " + BT + "onnx" + BT
        drop = "\n".join(ln for ln in self.text.splitlines() if ln != target) + "\n"
        self.assertTrue(any("锚数" in i for i in index_issues(drop)))
        old = self.text.replace("**370**", "**369**")
        self.assertTrue(any("370" in i for i in index_issues(old)))
        broken = self.text.replace(" · 可达 是（200 · 2026-09-24）", " · 可达 是", 1)
        self.assertTrue(any("行结构" in i for i in index_issues(broken)))
        no_gen = self.text.replace("禁止手改", "可以手改")
        self.assertTrue(any("禁止手改" in i for i in index_issues(no_gen)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_index.md")


if __name__ == "__main__":
    unittest.main()
