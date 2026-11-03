"""一份数据多渲染（render_extra.py）的单元回归。

作者：impl（DSH agent）· 2026-11-02
运行：cd desktop && PYTHONPATH=src python3 -m unittest tests.test_labeling_render_extra -v

覆盖：用 report.build_report 对临时 PNG 造真实报告，再断言 SVG 分享卡的字段与
自包含性、终端摘要行数、CSV 列宽与转义、JSONL 单行可解析、selfcheck 全 PASS、
缺字段时的修复指引。
"""

import copy
import csv
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, render_extra, report  # noqa: E402


def _build(td, name="样例 图片.png"):
    """在临时目录造一个带 AIGC JSON 的 PNG，并生成真实报告字典。"""
    path = str(Path(td) / name)
    fields = {
        "Label": "1",
        "ContentProducer": "001091350100M000100Y4300000",
        "ProduceID": "pid20250101v123456",
    }
    metadata.make_png(path, {"AIGC": json.dumps(fields)})
    return report.build_report(path, generated_at="2026-11-02T00:00:00+0800")


def _row(text):
    return next(csv.reader(io.StringIO(text)))


class SvgCardTest(unittest.TestCase):
    def test_svg_card_contains_core_fields(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        svg = render_extra.to_svg_card(rep)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn('width="1200"', svg)
        self.assertIn('height="630"', svg)
        self.assertIn(rep["verdict"], svg)
        self.assertIn(rep["report_id"], svg)
        self.assertIn(rep["file"]["name"], svg)
        for title in ("显式标识", "隐式标识字段", "安全防护信息", "内容绑定",
                      "备案材料"):
            self.assertIn(title, svg)
        self.assertIn("整改清单", svg)
        self.assertIn("免责声明：", svg)
        ET.fromstring(svg)  # 输出必须是合法 XML（浏览器/设计工具可直接打开）

    def test_svg_card_has_no_script_or_external_refs(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        svg = render_extra.to_svg_card(rep)
        self.assertNotIn("<script", svg.lower())
        self.assertNotIn("<image", svg.lower())
        self.assertNotIn("@import", svg.lower())
        # xmlns 是命名空间标识符，不是外链；剔除后再查剩余 http(s) 引用。
        body = svg.replace(render_extra.SVG_NS, "")
        self.assertNotIn("http://", body)
        self.assertNotIn("https://", body)
        self.assertEqual(render_extra._external_refs(svg), [])

    def test_svg_card_escapes_xml_text(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        rep = copy.deepcopy(rep)
        rep["title"] = 'A&B <报告> "x"'
        rep["file"]["name"] = "<script>alert(1)</script>.png"
        svg = render_extra.to_svg_card(rep)
        self.assertIn("A&amp;B", svg)
        self.assertIn("&lt;script&gt;", svg)
        self.assertNotIn("<script>", svg)
        self.assertNotIn("<报告>", svg)
        ET.fromstring(svg)


class ConsoleTest(unittest.TestCase):
    def test_console_fits_one_screen(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        text = render_extra.to_console(rep)
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 20)
        self.assertIn("结论", text)
        self.assertIn(rep["verdict"], text)
        self.assertIn(rep["report_id"], text)
        self.assertIn("五段", text)
        self.assertIn("整改", text)

    def test_console_no_actions_message(self):
        rep = render_extra.sample_report()
        rep["actions"] = []
        text = render_extra.to_console(rep)
        self.assertIn("无整改项", text)
        self.assertLessEqual(len(text.splitlines()), 20)


class CsvTest(unittest.TestCase):
    def test_csv_header_and_row_have_same_width(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        header = _row(render_extra.csv_header())
        row = _row(render_extra.to_csv_row(rep))
        self.assertEqual(len(header), len(render_extra.CSV_FIELDS))
        self.assertEqual(len(header), len(row))
        self.assertEqual(len(set(header)), len(header))
        self.assertEqual(row[0], rep["report_id"])
        self.assertEqual(row[2], rep["verdict"])
        self.assertNotIn("\n", render_extra.to_csv_row(rep))

    def test_csv_quotes_special_characters(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        rep = copy.deepcopy(rep)
        name = 'a,b"c.png'
        rep["file"]["name"] = name
        row = _row(render_extra.to_csv_row(rep))
        index = render_extra.CSV_FIELDS.index("file_name")
        self.assertEqual(row[index], name)
        self.assertEqual(len(row), len(render_extra.CSV_FIELDS))


class JsonlTest(unittest.TestCase):
    def test_jsonl_is_single_parseable_line(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        line = render_extra.to_jsonl(rep)
        self.assertEqual(len(line.splitlines()), 1)
        doc = json.loads(line)
        self.assertEqual(doc["schema"], rep["schema"])
        self.assertEqual(doc["report_id"], rep["report_id"])
        self.assertEqual(doc["verdict"], rep["verdict"])
        self.assertEqual(doc["summary"], rep["summary"])
        self.assertEqual(doc["counts"], rep["counts"])
        self.assertEqual(doc["file"]["name"], rep["file"]["name"])
        self.assertEqual(len(doc["actions"]), len(rep["actions"]))


class SelfcheckTest(unittest.TestCase):
    def test_selfcheck_all_pass(self):
        rows = render_extra.selfcheck()
        self.assertGreaterEqual(len(rows), 6)
        for name, ok, detail in rows:
            self.assertIsInstance(name, str)
            self.assertTrue(ok, "%s：%s" % (name, detail))
            self.assertTrue(detail, name)
        joined = " ".join(name for name, _, _ in rows)
        for word in ("svg", "console", "csv", "jsonl"):
            self.assertIn(word, joined)


class GuardTest(unittest.TestCase):
    def test_missing_field_raises_with_fix_hint(self):
        broken = {"verdict": "PASS"}
        for fn in (render_extra.to_svg_card, render_extra.to_console,
                   render_extra.to_csv_row, render_extra.to_jsonl):
            with self.assertRaises(ValueError) as ctx:
                fn(broken)
            self.assertIn("修复指引", str(ctx.exception))
            self.assertIn("file", str(ctx.exception))

    def test_renderers_share_verdict_and_are_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            rep = _build(td)
        outs = [render_extra.to_svg_card(rep), render_extra.to_console(rep),
                render_extra.to_csv_row(rep), render_extra.to_jsonl(rep)]
        for text in outs:
            self.assertIn(rep["verdict"], text)
        self.assertEqual(render_extra.to_svg_card(rep),
                         render_extra.to_svg_card(rep))
        self.assertEqual(render_extra.to_jsonl(rep),
                         render_extra.to_jsonl(rep))


if __name__ == "__main__":
    unittest.main()
