"""独立交叉认证（xcheck.py）的单元回归。

作者：impl（DSH agent）· 2026-11-02
运行：cd desktop && PYTHONPATH=src python3 -m unittest tests.test_labeling_xcheck -v

测什么：独立解析 PNG 文本块/JSON、七字段/Label/SM3 结构事实、与主报告的
agree/conflict 语义、篡改报告必须判冲突、回执与自检；主判定逻辑本身不在本文件。
"""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, report, xcheck  # noqa: E402

META = {"Label": 1, "ContentProducer": "1" * 27,
        "ProduceID": "XCHECK-TEST-1"}
ALL_FIELDS = ["Label", "ContentProducer", "ProduceID", "ReservedCode1",
              "ContentPropagator", "PropagateID", "ReservedCode2"]


def make_aigc_png(path, meta=None):
    """造一个带 AIGC JSON 文本块的 PNG（未签名，主报告多为 WARN）。"""
    payload = {"AIGC": META if meta is None else meta}
    metadata.make_png(str(path),
                      {"AIGC": json.dumps(payload, ensure_ascii=False)})


class XcheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.png = str(self.dir / "a.png")
        make_aigc_png(self.png)
        self.rep = report.build_report(
            self.png, generated_at="2026-11-02T00:00:00+0800")

    def tearDown(self):
        self._tmp.cleanup()

    def _verify(self, rep=None):
        return xcheck.verify(self.png, rep)

    def test_verify_png_structure(self):
        xc = self._verify()
        self.assertEqual(xc["schema"], "nf-label-xcheck/1")
        self.assertEqual(xc["mode"], "png")
        self.assertEqual(xc["container"], "png")
        ind = xc["independent"]
        self.assertTrue(ind["aigc_found"])
        self.assertEqual(ind["aigc_count"], 1)
        self.assertEqual(ind["field_count"], 3)
        self.assertEqual(ind["fields_present"], ["Label", "ContentProducer",
                                                 "ProduceID"])
        self.assertEqual(ind["label"], "1")
        self.assertTrue(ind["label_valid"])
        self.assertEqual(ind["verdict"], "WARN")
        self.assertEqual(xc["file"]["sha256"],
                         hashlib.sha256(Path(self.png).read_bytes()).hexdigest())
        self.assertEqual(xc["report_id"], xc["file"]["sha256"][:16])
        self.assertEqual(xc["trust"], "partial")
        self.assertEqual(xc["comparisons"], [])
        self.assertEqual(xc["conflict"], [])

    def test_verify_json_document(self):
        doc = self.dir / "aigc.json"
        doc.write_text(json.dumps({"AIGC": META}, ensure_ascii=False),
                       encoding="utf-8")
        xc = xcheck.verify(str(doc))
        self.assertEqual(xc["mode"], "json")
        self.assertEqual(xc["container"], "text")
        self.assertTrue(xc["independent"]["aigc_found"])
        self.assertEqual(xc["independent"]["field_count"], 3)
        self.assertEqual(xc["independent"]["label"], "1")

    def test_agree_with_main_report(self):
        xc = self._verify(self.rep)
        self.assertEqual(xc["trust"], "agree")
        self.assertEqual(xc["agree_count"], 7)
        self.assertEqual(xc["conflict"], [])
        self.assertEqual({i["name"] for i in xc["comparisons"]},
                         {"container", "report_id", "file_sha256", "verdict",
                          "fields_present", "label", "sm3"})
        self.assertTrue(all(i["agree"] is True for i in xc["comparisons"]))
        main_sm3 = next(i["evidence"]["sm3"]
                        for i in self.rep["sections"]["D"]["items"]
                        if i["id"] == "D2")
        self.assertEqual(xc["independent"]["sm3"]["sm3"], main_sm3)

    def test_tampered_sha256_conflicts(self):
        bad = copy.deepcopy(self.rep)
        bad["file"]["sha256"] = "0" * 64
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("file_sha256", xc["conflict"])
        self.assertNotIn("report_id", xc["conflict"])
        self.assertEqual(xc["agree_count"], 6)

    def test_tampered_report_id_conflicts(self):
        bad = copy.deepcopy(self.rep)
        bad["report_id"] = "0" * 16
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("report_id", xc["conflict"])

    def test_tampered_field_count_conflicts(self):
        bad = copy.deepcopy(self.rep)
        for item in bad["sections"]["B"]["items"]:
            if item["id"] == "B1":
                item["evidence"]["present"] = list(ALL_FIELDS)
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("fields_present", xc["conflict"])

    def test_tampered_label_conflicts(self):
        bad = copy.deepcopy(self.rep)
        for item in bad["sections"]["B"]["items"]:
            if item["id"] == "B4":
                item["detail"] = "Label=2（可能为生成合成）"
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("label", xc["conflict"])

    def test_tampered_sm3_conflicts(self):
        bad = copy.deepcopy(self.rep)
        for item in bad["sections"]["D"]["items"]:
            if item["id"] == "D2":
                item["evidence"]["sm3"] = "0" * 64
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("sm3", xc["conflict"])

    def test_tampered_verdict_conflicts(self):
        bad = copy.deepcopy(self.rep)
        bad["verdict"] = "FAIL"
        xc = self._verify(bad)
        self.assertEqual(xc["trust"], "conflict")
        self.assertIn("verdict", xc["conflict"])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            xcheck.verify(str(self.dir / "nope.png"))
        self.assertIn("修复指引", str(ctx.exception))

    def test_to_receipt_shape(self):
        xc = self._verify(self.rep)
        rec = xcheck.to_receipt(xc, xc["file"]["sha256"])
        self.assertEqual(rec["schema"], "nf-label-xcheck-receipt/1")
        self.assertEqual(rec["subject"]["sha256"], xc["file"]["sha256"])
        self.assertTrue(rec["subject"]["subject_match"])
        self.assertEqual(rec["crosscheck"]["trust"], "agree")
        self.assertIn("nf_label_xcheck.py verify",
                      rec["recompute"][0])
        self.assertGreaterEqual(len(rec["method"]), 4)
        self.assertEqual(rec["issued_at"], xc["generated_at"])
        other = xcheck.to_receipt(xc, "0" * 64)
        self.assertFalse(other["subject"]["subject_match"])
        with self.assertRaises(ValueError):
            xcheck.to_receipt(xc, "too-short")

    def test_selfcheck_all_pass(self):
        rows = xcheck.selfcheck()
        self.assertTrue(rows)
        self.assertTrue(all(ok for _name, ok, _detail in rows),
                        [r for r in rows if not r[1]])


if __name__ == "__main__":
    unittest.main()
