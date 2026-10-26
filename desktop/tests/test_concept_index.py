#!/usr/bin/env python3
"""资产本体索引（T10.2）判据：合成 3+1 域 fixture / 真仓统计 / 篡改红。

fixture 覆盖任务要求的四类语义：
- **同名合并**：`共享概念` 在包A/包B 各出现一次 → 一个节点、domains 2 个、类别冲突 WARN；
- **悬空边**：包A 的 `A3` 声明前置 `GHOST`（不在节点表也不在外部前置族）→ 记 dangling；
- **重复边**：`A1` 的前置列表重复声明 `共享概念` 两次 → 一条边 + occurrences=2；
- **空图**：包C 的 `nodes: []` → 域在场、0 节点；
- 另加**外部前置**（X00 → external 节点）与 **graphml 回退**（包D 只有 outputs/CONCEPT_DAG.graphml）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import concept_index as ci  # noqa: E402


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _md(domain: str, nodes: str, external: str = "") -> str:
    block = ["<!-- nf-asset: key=\"CONCEPT_GRAPH\" version=\"1.0\" status=\"active\" -->",
             "# 概念图 · %s" % domain, "", "## 4. 机器可读块", "", "```yaml",
             "concept_graph:", "  domain: %s" % domain, '  version: "1.0"',
             "  nodes:" + ("" if nodes.strip() else " []")]
    if nodes.strip():
        block.append(nodes.rstrip("\n"))
    if external.strip():
        block.append("  external_prereqs:")
        block.append(external.rstrip("\n"))
    block.append("```")
    return "\n".join(block) + "\n"


_GRAPHML = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="k_name" for="node" attr.name="name" attr.type="string"/>
  <key id="k_branch" for="node" attr.name="branch" attr.type="string"/>
  <graph id="g" edgedefault="directed">
    <node id="g1"><data key="k_name">图概念一</data><data key="k_branch">domain</data></node>
    <node id="g2"><data key="k_name">图概念二</data><data key="k_branch">domain</data></node>
    <edge source="g1" target="g2"/>
  </graph>
</graphml>
"""


def _scene() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="nf-onto-"))
    _write(tmp, "community/包A/assets/CONCEPT_GRAPH.md", _md(
        "包A",
        "    - id: S\n      name: 共享概念\n      layer: P40\n      branch: domain\n"
        "      prereqs: []\n      provenance: [a-anchor]\n"
        "    - id: A1\n      name: 独立概念一\n      layer: P40\n      branch: domain\n"
        "      prereqs: [S, S]\n      provenance: [a-anchor]\n"
        "    - id: A2\n      name: 外部前置消费者\n      layer: P40\n      branch: app\n"
        "      prereqs: [X00]\n      provenance: [a-anchor]\n"
        "    - id: A3\n      name: 悬空边节点\n      layer: P40\n      branch: app\n"
        "      prereqs: [GHOST]\n      provenance: [a-anchor]",
        "    - id: X00\n      name: 包外前置\n"))
    _write(tmp, "community/包B/assets/CONCEPT_GRAPH.md", _md(
        "包B",
        "    - id: S\n      name: 共享概念\n      branch: standards\n      prereqs: []\n"
        "    - id: A1\n      name: 独立概念一\n      layer: P50\n      branch: domain\n"
        "      prereqs: []"))
    _write(tmp, "community/包C/assets/CONCEPT_GRAPH.md", _md("包C", ""))
    _write(tmp, "community/包D/outputs/CONCEPT_DAG.graphml", _GRAPHML)
    return tmp


def _write_index(root: Path):
    issues, doc = ci.write(str(root))
    assert not issues, issues
    return doc


class MergeFixtureTest(unittest.TestCase):
    def setUp(self):
        self.root = _scene()
        self.doc, self.issues = ci.compute(str(self.root))
        self.stats = self.doc["stats"]

    def test_coverage(self):
        self.assertEqual([], self.issues)
        src = self.doc["sources"]
        self.assertEqual((3, 3), (src["md_total"], src["md_parsed"]))
        self.assertEqual((1, 1), (src["graphml_total"], src["graphml_parsed"]))
        self.assertEqual(1, src["graphml_used"], "graphml 回退未生效（包D 无 md）")
        self.assertEqual([], src["skipped"])
        kinds = {d["id"]: d["kind"] for d in self.doc["domains"]}
        self.assertEqual("graphml", kinds.get("包D"))

    def test_stats(self):
        s = self.stats
        self.assertEqual(4, s["domains"])
        self.assertEqual(8, s["node_occurrences"])
        self.assertEqual(7, s["nodes"])
        self.assertEqual(2, s["merged_same_name"])        # 共享概念 + 独立概念一 各合并一次
        self.assertEqual(5, s["edge_occurrences"])
        self.assertEqual(3, s["edges"])                   # S→A1 · X00→A2 · 图概念一→图概念二
        self.assertEqual(1, s["duplicate_edges_merged"])
        self.assertEqual(1, s["dangling_edges"])
        self.assertEqual(1, s["orphan_nodes"])            # A3（只有悬空前置，无边）
        self.assertEqual(1, s["external_nodes"])
        self.assertEqual(1, s["category_conflicts"])
        self.assertEqual(1, s["warnings"])

    def test_same_name_merged_with_domains_and_conflict(self):
        node = [n for n in self.doc["nodes"] if n["id"] == "共享概念"][0]
        self.assertEqual(["包A", "包B"], node["domains"])
        self.assertEqual(["domain", "standards"], node["categories"])
        self.assertIn("同名概念类别冲突", " ".join(self.doc["warnings"]))

    def test_duplicate_edge_has_occurrences(self):
        edge = [e for e in self.doc["edges"] if e["source"] == "共享概念"
                and e["target"] == "独立概念一"][0]
        self.assertEqual(2, edge["occurrences"])
        self.assertEqual(1, len([e for e in self.doc["edges"]
                                 if e["source"] == "共享概念" and e["target"] == "独立概念一"]))

    def test_empty_graph_domain_present(self):
        dom = [d for d in self.doc["domains"] if d["id"] == "包C"][0]
        self.assertEqual(0, dom["nodes"])
        self.assertFalse([n for n in self.doc["nodes"]
                          if "包C" in n["domains"] and n["id"] != "共享概念"])

    def test_deterministic(self):
        doc2, issues2 = ci.compute(str(self.root))
        self.assertEqual([], issues2)
        self.assertEqual(ci.dump(self.doc), ci.dump(doc2))
        self.assertEqual(self.doc["root"], doc2["root"])

    def test_write_idempotent_and_check_clean(self):
        doc1 = _write_index(self.root)
        text1 = (self.root / ci.INDEX_REL).read_text(encoding="utf-8")
        _write_index(self.root)
        text2 = (self.root / ci.INDEX_REL).read_text(encoding="utf-8")
        self.assertEqual(text1, text2, "同树两次 --write 字节不一致")
        self.assertEqual(doc1["root"], self.doc["root"])
        issues, _ = ci.check(str(self.root))
        self.assertEqual([], issues, issues)

    def test_asset_tamper_turns_check_red(self):
        _write_index(self.root)
        _write(self.root, "community/包B/assets/CONCEPT_GRAPH.md", _md(
            "包B",
            "    - id: S\n      name: 共享概念\n      branch: standards\n      prereqs: []\n"
            "    - id: NEW\n      name: 新增概念\n      branch: domain\n      prereqs: []"))
        issues, doc = ci.check(str(self.root))
        self.assertTrue(issues)
        self.assertEqual(8, doc["stats"]["nodes"])
        self.assertIn("新增概念", doc["sources"] and json.dumps(doc["nodes"], ensure_ascii=False))

    def test_index_tamper_turns_check_red(self):
        _write_index(self.root)
        p = self.root / ci.INDEX_REL
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["root"] = "0" * 64
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        issues, _ = ci.check(str(self.root))
        self.assertTrue(any("root 与 nodes/edges 实时重算不一致" in i for i in issues), issues)


class EdgeCaseTest(unittest.TestCase):
    def test_empty_repo_reports_hard_issue(self):
        tmp = Path(tempfile.mkdtemp(prefix="nf-onto-empty-"))
        _doc, issues = ci.compute(str(tmp))
        self.assertTrue(any("没扫到任何概念图" in i for i in issues), issues)


class RealRepoTest(unittest.TestCase):
    """真仓：committed index 必须与实时重算一致（相当于门禁那一条）。"""

    def test_repo_index_in_sync_and_stats(self):
        if not (ROOT / ci.INDEX_REL).is_file():
            self.skipTest("protocol/concept_graph_index.json 尚未生成")
        issues, doc = ci.check(str(ROOT))
        self.assertEqual([], issues, issues[:5])
        s = doc["stats"]
        self.assertEqual(101, doc["sources"]["md_total"])
        self.assertEqual(101, doc["sources"]["md_parsed"])
        self.assertEqual(101, s["domains"])
        self.assertGreaterEqual(s["nodes"], 1200)
        self.assertGreaterEqual(s["edges"], 4000)
        self.assertEqual(0, s["dangling_edges"])
        self.assertRegex(doc["root"], r"^[0-9a-f]{64}$")
        self.assertEqual(doc["root"], ci.root_of(doc))


if __name__ == "__main__":
    unittest.main()
