#!/usr/bin/env python3
"""§19.1 补件判据：wiki/spec 报告 + 分层 QA 映射（L0–L20）+ examples/docs 入口。"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import layer_reports as lr  # noqa: E402


class LayerReportsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wiki = json.loads((ROOT / lr.WIKI_REPORT_REL).read_text(encoding="utf-8"))
        cls.spec = json.loads((ROOT / lr.SPEC_REPORT_REL).read_text(encoding="utf-8"))
        cls.qa = json.loads((ROOT / lr.QA_REL).read_text(encoding="utf-8"))

    def test_check_green(self):
        self.assertEqual([], lr.check(str(ROOT)))

    def test_committed_equals_live(self):
        live = {"wiki": lr.build_wiki_report(str(ROOT)),
                "spec": lr.build_spec_report(str(ROOT)),
                "qa": lr.build_qa_layers(str(ROOT))}
        for rel, doc in ((lr.WIKI_REPORT_REL, live["wiki"]),
                         (lr.SPEC_REPORT_REL, live["spec"]),
                         (lr.QA_REL, live["qa"])):
            self.assertEqual(json.dumps(doc, ensure_ascii=False, sort_keys=True),
                             json.dumps(json.loads((ROOT / rel).read_text(encoding="utf-8")),
                                        ensure_ascii=False, sort_keys=True), rel)

    def test_wiki_and_spec_reports_ok(self):
        self.assertTrue(self.wiki["ok"], self.wiki.get("issues"))
        self.assertEqual(133, self.wiki["pages"])
        self.assertGreaterEqual(len(self.wiki["files"]), 5)
        self.assertTrue(self.spec["ok"], self.spec.get("issues"))
        self.assertGreaterEqual(self.spec["tasks"], 1)
        self.assertEqual(64, len(self.spec["bundle_digest"]))

    def test_qa_layers_complete(self):
        ids = [row["layer"] for row in self.qa["layers"]]
        self.assertEqual(["L%d" % i for i in range(21)], ids)
        for row in self.qa["layers"]:
            self.assertIn(row["status"], ("covered", "partial", "gap", "open"))
            if row["status"] in ("partial", "gap", "open"):
                self.assertTrue(row.get("owner"), row["layer"])
                self.assertTrue(row.get("next"), row["layer"])
        self.assertEqual(21, sum(self.qa["summary"].values()))

    def test_examples_and_qa_docs_present(self):
        for rel in ("examples/README.md", "examples/core-only/README.md",
                    "examples/governance/README.md", "docs/qa/README.md"):
            self.assertTrue((ROOT / rel).is_file(), rel)


if __name__ == "__main__":
    unittest.main()
