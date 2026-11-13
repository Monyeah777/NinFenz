#!/usr/bin/env python3
"""docs/standards/layer-data.md 契约：层切片页必须「148 条 / 切片口径 / 五层同构 / --check 新鲜」。

为什么必须有：层切片是 GEO 出口的按层视图，行字段与主索引一致、锚点逐字相同；缺了「怎么读本页」
读者不知道切片边界与字段含义。本轮在生成器里补该段（切片口径 / 行字段 / 互指 / 投影定位）并重生成，
五个层页同构更新；本判据以 data 层为锚点，并把「五层同构」与真源计数一起绑死。

范围：只判本文与 geo_export 生成逻辑/catalog 事实自洽。
同族判据：geo_export --check（本判据会实跑）/ check40 / test_doc_hygiene.py。
契约：标题带条数、生成声明、§怎么读本页 4 条、148 个锚与 catalog 的 data 层集合相等、
五层页同构（同一段落在 eng/form/gov/iface 均在场）、--check 零差异。
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BT = chr(96)

DOC = ROOT / "docs" / "standards" / "layer-data.md"
CATALOG = ROOT / "protocol" / "standards_catalog.json"
LAYERS = ("data", "eng", "form", "gov", "iface")
MEANINGS = {
    "data": "数据/格式/模式与交换表示",
    "eng": "工程方法与过程约定",
    "form": "呈现与文档形态",
    "gov": "治理/合规/风险与制度框架",
    "iface": "接口/协议与互操作",
}
ENTRY = re.compile("^### " + BT + "([a-z0-9][a-z0-9._-]*)" + BT + "$")
BLOCK = "## 怎么读本页"


def load_text(path: Path = DOC) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"层切片页不可读：{exc}") from exc
    if not text.strip():
        raise ValueError("层切片页为空")
    return text


def facts() -> dict:
    c = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_layer = {layer: [s["id"] for s in c["standards"] if s.get("layer") == layer]
                for layer in LAYERS}
    cov = c["coverage"]
    return {"by_layer": by_layer, "coverage": cov,
            "standards": len(c["standards"])}


def layer_issues(text: str) -> list:
    issues = []
    f = facts()
    n = len(f["by_layer"]["data"])
    if not text.startswith(f"# 标准目录 · 层 data（{n} 条）"):
        issues.append(f"缺标题「# 标准目录 · 层 data（{n} 条）」")
    if "禁止手改" not in text:
        issues.append("缺「生成物，禁止手改」声明")
    if BLOCK not in text:
        issues.append("缺「§怎么读本页」段")
    for marker in ("--write", "--check", "切片口径", "行字段", "互指", "投影"):
        if marker not in text:
            issues.append(f"读法段缺：{marker}")
    ids = [m.group(1) for m in (ENTRY.match(ln) for ln in text.splitlines()) if m]
    if sorted(ids) != sorted(f["by_layer"]["data"]):
        issues.append(f"锚集合与 catalog 的 data 层不一致（{len(ids)} vs {n}）")
    cov = f["coverage"]
    for label in (f"**{cov['standards']}**", f"**{cov['reachable']}**"):
        if label not in text:
            issues.append(f"覆盖数缺：{label}")
    for layer in LAYERS:
        if f"{layer} {len(f['by_layer'][layer])}" not in text:
            issues.append(f"层分布缺：{layer}")
    for layer in LAYERS:
        side = ROOT / "docs" / "standards" / f"layer-{layer}.md"
        if not side.is_file():
            issues.append(f"分层页缺失：layer-{layer}.md")
            continue
        side_text = side.read_text(encoding="utf-8")
        if BLOCK not in side_text:
            issues.append(f"分层页不同构：layer-{layer}.md 缺读法段")
        want = "- 本层含义：" + MEANINGS[layer]
        if want not in side_text:
            issues.append(f"分层页缺本层含义：layer-{layer}.md")
    own = "- 本层含义：" + MEANINGS["data"]
    if own not in text:
        issues.append("本页缺本层含义（data）")
    return issues


class LayerPageDocTest(unittest.TestCase):
    def setUp(self):
        self.text = load_text()

    def test_layer_matches_contract(self):
        self.assertEqual([], layer_issues(self.text), "层切片页不满足契约")

    def test_freshness(self):
        proc = subprocess.run([sys.executable, "scripts/geo_export.py", "--check"],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300, check=False)
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-400:])

    def test_contract_catches_mutations(self):
        """变异自证：缺读法段 / 锚缺失 / 层分布回退 / 缺生成声明。"""
        no_block = self.text.replace(BLOCK, "## 说明")
        self.assertTrue(any("怎么读本页" in i for i in layer_issues(no_block)))
        target = "### " + BT + "adbc" + BT
        drop = "\n".join(ln for ln in self.text.splitlines() if ln != target) + "\n"
        self.assertTrue(any("锚集合" in i for i in layer_issues(drop)))
        old = self.text.replace("data 148", "data 140")
        self.assertTrue(any("层分布" in i for i in layer_issues(old)))
        no_gen = self.text.replace("禁止手改", "可以手改")
        self.assertTrue(any("禁止手改" in i for i in layer_issues(no_gen)))
        with self.assertRaises(ValueError):
            load_text(ROOT / "no_such_layer.md")


if __name__ == "__main__":
    unittest.main()
