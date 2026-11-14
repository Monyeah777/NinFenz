#!/usr/bin/env python3
"""WP-10 LLMWiki 编译器判据（`nf wiki build/check/get/search/related/context`）。

真源 = 真源文件（registry/03 管线/05 资产/community DOMAIN_SPEC/protocol schemas）；
生成物 = `wiki/{pages.json,INDEX.json,GRAPH.json,llms.txt,mcp.json}`。
判据：
1. 确定性：同输入两次编译逐字节一致；
2. 页面符合 `nf-wiki-page/1`（id 唯一、spec_ref/digest/citations 齐）；
3. 覆盖：module 13 / pipeline 3 / domain 100 / protocol 14 / asset 3；
4. 关系可解析、INDEX/GRAPH/MCP 三入口与 pages 一致；
5. `check` 真源现算 digest → 陈旧/手改即红；投影页禁复制正文（body/content/text + summary 上限）；
6. 查询面：get/search/related/context（预算与 citations）；
7. 变异自证：digest 篡改、关系断链、ID 重复、注入正文、缺生成物 → 都必须红。
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import json_schema  # noqa: E402
from core import wiki_compiler as wc  # noqa: E402


def _committed():
    return (json.loads((ROOT / "wiki" / "pages.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "wiki" / "INDEX.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "wiki" / "GRAPH.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "wiki" / "mcp.json").read_text(encoding="utf-8")))


class WikiCompilerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages, cls.index, cls.graph, cls.mcp = _committed()
        cls.live_pages, cls.live_rest = wc.build(str(ROOT))
        cls.expected = cls.live_rest["expected"]

    def test_build_deterministic(self):
        first = wc.render(str(ROOT))
        second = wc.render(str(ROOT))
        self.assertEqual(first, second, "同输入两次编译必须逐字节一致")
        self.assertEqual(133, len(self.live_pages["pages"]))
        self.assertEqual(133, len(wc.render(str(ROOT))["wiki/llms.txt"].splitlines()) - 2)

    def test_pages_schema_valid(self):
        schema = json.loads((ROOT / wc.PAGE_SCHEMA_REL).read_text(encoding="utf-8"))
        for page in self.pages["pages"]:
            problems = json_schema.json_schema_check(page, schema)
            self.assertEqual([], problems[:1], page.get("id"))
            self.assertTrue(page["spec_ref"]["id"])
            self.assertGreaterEqual(len(page["citations"]), 1)

    def test_coverage_by_type(self):
        counts = {}
        for page in self.pages["pages"]:
            counts[page["type"]] = counts.get(page["type"], 0) + 1
        for ptype, want in self.expected.items():
            self.assertEqual(want, counts.get(ptype), "%s 覆盖不足" % ptype)
        self.assertEqual({"protocol": 14, "module": 13, "pipeline": 3,
                          "domain": 100, "asset": 3}, self.expected)

    def test_ids_unique_and_pattern(self):
        ids = [p["id"] for p in self.pages["pages"]]
        self.assertEqual(len(ids), len(set(ids)))
        for pid in ids:
            self.assertTrue(pid.startswith("wiki:"), pid)
            self.assertNotIn(" ", pid)

    def test_relations_index_graph_mcp(self):
        self.assertEqual([], wc.validate_pages(self.pages, self.index, self.graph,
                                               self.mcp, self.expected, str(ROOT)))
        ids = {p["id"] for p in self.pages["pages"]}
        self.assertEqual(ids, {p["id"] for p in self.index["pages"]})
        self.assertEqual(ids, set(self.graph["nodes"]))
        self.assertEqual(5, len(self.mcp["tools"]))

    def test_committed_check_green(self):
        self.assertEqual([], wc.check(str(ROOT)))

    def test_stale_digest_red(self):
        tampered = copy.deepcopy(self.pages)
        tampered["pages"][0]["provenance"]["digest"] = "0" * 64
        self.assertTrue(wc.stale_issues(tampered, str(ROOT)), "篡改 digest 必须判陈旧")

    def test_duplicate_body_red(self):
        tampered = copy.deepcopy(self.pages)
        tampered["pages"][0]["body"] = "x" * 500
        self.assertTrue(wc.validate_pages(tampered, self.index, self.graph, self.mcp,
                                          self.expected, str(ROOT)),
                        "投影页复制正文必须红")

    def test_relation_target_red(self):
        tampered = copy.deepcopy(self.pages)
        tampered["pages"][0]["relations"] = [{"kind": "depends_on",
                                              "target": "wiki:nonexistent/page"}]
        self.assertTrue(wc.validate_pages(tampered, self.index, self.graph, self.mcp,
                                          self.expected, str(ROOT)),
                        "关系断链必须红")

    def test_query_functions(self):
        page = wc.get("wiki:module:M06", str(ROOT))
        self.assertIsNotNone(page)
        self.assertEqual("module", page["type"])
        self.assertTrue(wc.search("M06", str(ROOT)))
        rel = wc.related("wiki:module:M06", str(ROOT))
        self.assertEqual("wiki:protocol:schema/module", rel["outgoing"][0]["to"])
        ctx = wc.context(["wiki:pipeline:P00_通用文档生成管线"], 400, str(ROOT))
        self.assertTrue(ctx["entries"])
        self.assertTrue(ctx["entries"][0]["citations"])

    def test_missing_outputs_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            issues = wc.check(tmp)
            self.assertTrue(issues, "缺生成物/真源必须如实报 issue 而不是裸崩")


if __name__ == "__main__":
    unittest.main()
