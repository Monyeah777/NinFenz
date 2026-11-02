"""域包补全模板（`core.domain_fill`）：不代写内容、只给待填清单 + 自检。"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import domain_fill as df  # noqa: E402


class DomainFillTemplateTest(unittest.TestCase):
    def test_template_has_12_rows_and_empty_answers(self):
        doc = df.template(str(ROOT), "AI教育域包")
        self.assertEqual(df.SCHEMA, doc["schema"])
        self.assertEqual(12, len(doc["subdivisions"]))
        for s in doc["subdivisions"]:
            self.assertTrue(s["id"] and s["name"])
            self.assertEqual("", s["definition"])
            self.assertEqual("", s["check"])
            self.assertEqual("", s["pitfall"])

    def test_empty_template_fails_check(self):
        issues = df.check(df.template(str(ROOT), "AI教育域包"))
        self.assertEqual(36, len([i for i in issues if "缺" in i]), issues)

    def test_filled_template_passes_and_placeholder_rejected(self):
        doc = df.template(str(ROOT), "AI教育域包")
        filled = copy.deepcopy(doc)
        for s in filled["subdivisions"]:
            s["definition"] = "%s 的领域定义（可判定）" % s["name"]
            s["check"] = "字段 A/B/C 齐备且值域合法"
            s["pitfall"] = "把通用指标当领域指标"
        self.assertEqual([], df.check(filled))
        filled["subdivisions"][0]["check"] = "领域专属判据待补"
        issues = df.check(filled)
        self.assertTrue(any("占位" in i for i in issues), issues)

    def test_check_dir_reports_counts(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "a.json").write_text(json.dumps(df.template(str(ROOT), "AI教育域包")),
                                      encoding="utf-8")
            filled = df.template(str(ROOT), "AI教育域包")
            for s in filled["subdivisions"]:
                s["definition"] = "d"; s["check"] = "c"; s["pitfall"] = "p"
            (d / "b.json").write_text(json.dumps(filled), encoding="utf-8")
            issues, stats = df.check_dir(str(d))
        self.assertEqual({"files": 2, "ok": 1, "bad": 1}, stats)
        self.assertTrue(any(i.startswith("a.json:") for i in issues), issues)

    def test_fill_status_counts(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            filled = df.template(str(ROOT), "AI教育域包")
            for s in filled["subdivisions"][:3]:
                s["definition"] = "d"; s["check"] = "c"; s["pitfall"] = "p"
            (d / "a.json").write_text(json.dumps(filled), encoding="utf-8")
            stats, per = df.fill_status(str(d))
        self.assertEqual({"files": 1, "subdivisions": 12, "filled": 3, "percent": 25.0}, stats)
        self.assertEqual(3, per["a.json"]["filled"])

    def test_write_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fill.json"
            df.write_template(str(ROOT), "AI教育域包", str(out))
            import json
            doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(12, len(doc["subdivisions"]))


if __name__ == "__main__":
    unittest.main()
