"""DOCX / Markdown 标识写入的回归测试（writers_docx_md）。

作者：impl（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_docx_md -v

夹具在测试内用 zipfile 自建最小 docx；读取面由 Lead 在 metadata.py 落地，
若尚未落地则相关「extract 往返」用例自动 skip（其余结构用例照常跑）。
"""

import json
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import sys

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in sys.path:
    sys.path.insert(0, os.path.join(sys_path_root, "desktop", "src"))

from core.labeling import metadata
from core.labeling import writers_docx_md as w

CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CUSTOM_NS = ("http://schemas.openxmlformats.org/officeDocument/2006/"
             "custom-properties")
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"

AIGC_JSON = json.dumps(
    {"AIGC": {"Label": "1",
              "ContentProducer": "001091350100M000100Y4300000",
              "ProduceID": "pid20250101v123456"}}, ensure_ascii=False)

CT_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Types xmlns="' + CT_NS.encode() + b'">'
    b'<Default Extension="rels" ContentType="application/'
    b'vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/word/document.xml" ContentType="application/'
    b'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    b'</Types>')
RELS_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Relationships xmlns="' + REL_NS.encode() + b'">'
    b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
    b'officeDocument/2006/relationships/officeDocument" '
    b'Target="word/document.xml"/></Relationships>')
DOC_XML = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<w:document xmlns:w="http://schemas.openxmlformats.org/'
    b'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
    b'\xe6\xad\xa3\xe6\x96\x87</w:t></w:r></w:p></w:body></w:document>')


def _make_docx(path, custom=None, rels=RELS_XML, ct=CT_XML):
    """最小 DOCX：三个必需 entry（+ 可选 custom.xml），顺序固定。"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", DOC_XML)
        if custom is not None:
            zf.writestr("docProps/custom.xml", custom)


def _zip_data(path, name):
    with zipfile.ZipFile(path) as zf:
        return zf.read(name)


def _zip_names(path):
    with zipfile.ZipFile(path) as zf:
        return zf.namelist()


def _custom_root(path):
    return ET.fromstring(_zip_data(path, "docProps/custom.xml"))


def _props(root, name="AIGC"):
    tag = "{%s}property" % CUSTOM_NS
    return [el for el in root if el.tag == tag and el.get("name") == name]


def _prop_text(prop):
    for child in prop:
        if child.tag == "{%s}lpwstr" % VT_NS:
            return child.text
    return None


CUSTOM_OLD = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Properties xmlns="' + CUSTOM_NS.encode() + b'" '
    b'xmlns:vt="' + VT_NS.encode() + b'">'
    b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" '
    b'name="App"><vt:lpwstr>keepme</vt:lpwstr></property></Properties>')

CUSTOM_AIGC_OLD = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Properties xmlns="' + CUSTOM_NS.encode() + b'" '
    b'xmlns:vt="' + VT_NS.encode() + b'">'
    b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="5" '
    b'name="AIGC"><vt:lpwstr>old</vt:lpwstr></property></Properties>')


class DocxWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.docx = str(self.dir / "a.docx")
        _make_docx(self.docx)

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip_property_value(self):
        w.inject_docx(self.docx, AIGC_JSON)
        props = _props(_custom_root(self.docx))
        self.assertEqual(len(props), 1)
        self.assertEqual(_prop_text(props[0]), AIGC_JSON)
        self.assertEqual(props[0].get("fmtid"),
                         "{D5CDD505-2E9C-101B-9397-08002B2CF9AE}")
        self.assertTrue(props[0].get("pid", "").isdigit())

    def test_vt_escaping_roundtrip(self):
        tricky = '{"AIGC":{"Note":"a < b & c > d \\"q\\""}}'
        w.inject_docx(self.docx, tricky)
        prop = _props(_custom_root(self.docx))[0]
        self.assertEqual(_prop_text(prop), tricky)
        raw = _zip_data(self.docx, "docProps/custom.xml")
        self.assertIn(b"&lt;", raw)
        self.assertIn(b"&amp;", raw)

    def test_other_entries_bytes_and_order(self):
        before = _zip_names(self.docx)
        before_doc = _zip_data(self.docx, "word/document.xml")
        w.inject_docx(self.docx, AIGC_JSON)
        after = _zip_names(self.docx)
        self.assertEqual(after[:len(before)], before)   # 原顺序不变
        self.assertIn("docProps/custom.xml", after)
        self.assertEqual(_zip_data(self.docx, "word/document.xml"),
                         before_doc)
        # [Content_Types].xml / _rels/.rels 属「必须改」的 entry：只验语义保留
        rels_root = ET.fromstring(_zip_data(self.docx, "_rels/.rels"))
        office = [el for el in rels_root
                  if el.get("Type", "").endswith("/officeDocument")]
        self.assertEqual(len(office), 1)
        self.assertEqual(office[0].get("Id"), "rId1")
        self.assertEqual(office[0].get("Target"), "word/document.xml")

    def test_content_types_override_added_once(self):
        w.inject_docx(self.docx, AIGC_JSON)
        w.inject_docx(self.docx, AIGC_JSON)
        raw = _zip_data(self.docx, "[Content_Types].xml")
        self.assertEqual(raw.count(b"/docProps/custom.xml"), 1)
        self.assertIn(b"custom-properties+xml", raw)
        root = ET.fromstring(raw)
        overrides = [el for el in root
                     if el.get("PartName") == "/docProps/custom.xml"]
        self.assertEqual(len(overrides), 1)
        self.assertIn("custom-properties+xml",
                      overrides[0].get("ContentType", ""))

    def test_relationship_added_once(self):
        w.inject_docx(self.docx, AIGC_JSON)
        w.inject_docx(self.docx, AIGC_JSON)
        root = ET.fromstring(_zip_data(self.docx, "_rels/.rels"))
        rels = [el for el in root
                if el.get("Type", "").endswith("/custom-properties")]
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].get("Id"), "rIdAigc1")
        self.assertEqual(rels[0].get("Target"), "docProps/custom.xml")

    def test_relationship_id_collision(self):
        rels = RELS_XML.replace(
            b'</Relationships>',
            b'<Relationship Id="rIdAigc1" Type="http://example/other" '
            b'Target="other.xml"/></Relationships>')
        _make_docx(self.docx, rels=rels)
        w.inject_docx(self.docx, AIGC_JSON)
        root = ET.fromstring(_zip_data(self.docx, "_rels/.rels"))
        rels = [el for el in root
                if el.get("Type", "").endswith("/custom-properties")]
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].get("Id"), "rIdAigc2")

    def test_preserves_existing_custom_property(self):
        _make_docx(self.docx, custom=CUSTOM_OLD)
        w.inject_docx(self.docx, AIGC_JSON)
        root = _custom_root(self.docx)
        app = _props(root, "App")
        self.assertEqual(len(app), 1)
        self.assertEqual(_prop_text(app[0]), "keepme")
        self.assertEqual(len(_props(root)), 1)

    def test_existing_aigc_replaced(self):
        _make_docx(self.docx, custom=CUSTOM_AIGC_OLD)
        w.inject_docx(self.docx, AIGC_JSON)
        root = _custom_root(self.docx)
        props = _props(root)
        self.assertEqual(len(props), 1)
        self.assertEqual(_prop_text(props[0]), AIGC_JSON)

    def test_idempotent_same_json(self):
        w.inject_docx(self.docx, AIGC_JSON)
        once = Path(self.docx).read_bytes()
        w.inject_docx(self.docx, AIGC_JSON)
        self.assertEqual(once, Path(self.docx).read_bytes())
        self.assertEqual(len(_props(_custom_root(self.docx))), 1)
        raw = _zip_data(self.docx, "[Content_Types].xml")
        self.assertEqual(raw.count(b"/docProps/custom.xml"), 1)

    def test_different_json_replaces_single(self):
        w.inject_docx(self.docx, AIGC_JSON)
        other = '{"AIGC":{"Label":2,"ProduceID":"P-2"}}'
        w.inject_docx(self.docx, other)
        props = _props(_custom_root(self.docx))
        self.assertEqual(len(props), 1)
        self.assertEqual(_prop_text(props[0]), other)

    def test_bad_zip_raises(self):
        bad = str(self.dir / "bad.docx")
        Path(bad).write_bytes(b"not a zip")
        with self.assertRaises(ValueError):
            w.inject_docx(bad, AIGC_JSON)
        trunc = str(self.dir / "trunc.docx")
        Path(trunc).write_bytes(CT_XML[:20])
        with self.assertRaises(ValueError):
            w.inject_docx(trunc, AIGC_JSON)

    def test_missing_required_entry_raises(self):
        for missing in ("_rels/.rels", "word/document.xml",
                        "[Content_Types].xml"):
            path = str(self.dir / ("miss-" + missing.replace("/", "_")))
            with zipfile.ZipFile(path, "w") as zf:
                if missing != "[Content_Types].xml":
                    zf.writestr("[Content_Types].xml", CT_XML)
                if missing != "_rels/.rels":
                    zf.writestr("_rels/.rels", RELS_XML)
                if missing != "word/document.xml":
                    zf.writestr("word/document.xml", DOC_XML)
            with self.assertRaises(ValueError):
                w.inject_docx(path, AIGC_JSON)

    def test_invalid_custom_xml_raises(self):
        _make_docx(self.docx, custom=b"<not-xml")
        with self.assertRaises(ValueError):
            w.inject_docx(self.docx, AIGC_JSON)

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            w.inject_docx(self.docx, "{bad json}")

    def test_extract_roundtrip_when_reader_ready(self):
        if not hasattr(metadata, "_docx_entries"):
            self.skipTest("metadata 的 DOCX 读取面尚未落地（Lead 负责）")
        w.inject_docx(self.docx, AIGC_JSON)
        cands = metadata.extract_json_candidates(self.docx)
        self.assertTrue(any(c.get("obj") == json.loads(AIGC_JSON)
                            for c in cands), cands)


class MarkdownWriterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return str(self.dir / name)

    def test_header_first_line_and_body_preserved(self):
        md = self.p("a.md")
        body = "标题\n\n正文 中文，保留。\n"
        Path(md).write_text(body, encoding="utf-8")
        w.inject_markdown(md, AIGC_JSON)
        text = Path(md).read_text(encoding="utf-8")
        first, rest = text.split("\n", 1)
        self.assertEqual(first, "<!-- AIGC:%s -->" % AIGC_JSON)
        self.assertEqual(rest, body)

    def test_roundtrip_json_block(self):
        md = self.p("a.md")
        Path(md).write_text("hello\n", encoding="utf-8")
        w.inject_markdown(md, AIGC_JSON)
        text = Path(md).read_text(encoding="utf-8")
        m = re.match(r"<!--\s*AIGC:(.*?)\s*-->\n", text)
        self.assertIsNotNone(m)
        self.assertEqual(json.loads(m.group(1)), json.loads(AIGC_JSON))

    def test_replace_existing_single_block(self):
        md = self.p("a.md")
        Path(md).write_text("保留正文\n第二行\n", encoding="utf-8")
        w.inject_markdown(md, AIGC_JSON)
        other = '{"AIGC":{"Label":2,"ProduceID":"P-2"}}'
        w.inject_markdown(md, other)
        text = Path(md).read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- AIGC:"), 1)
        self.assertTrue(text.startswith("<!-- AIGC:%s -->\n" % other))
        self.assertIn("保留正文\n第二行\n", text)

    def test_idempotent_same_json(self):
        md = self.p("a.md")
        Path(md).write_text("body\n", encoding="utf-8")
        w.inject_markdown(md, AIGC_JSON)
        once = Path(md).read_bytes()
        w.inject_markdown(md, AIGC_JSON)
        self.assertEqual(once, Path(md).read_bytes())

    def test_no_bom_output(self):
        md = self.p("bom.md")
        Path(md).write_bytes(b"\xef\xbb\xbf# hi\nbody\n")
        w.inject_markdown(md, AIGC_JSON)
        raw = Path(md).read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(raw.startswith(b"<!-- AIGC:"))

    def test_multiline_json_compacted(self):
        md = self.p("pretty.md")
        Path(md).write_text("body\n", encoding="utf-8")
        pretty = json.dumps({"AIGC": {"Label": 1}}, ensure_ascii=False,
                            indent=2)
        w.inject_markdown(md, pretty)
        text = Path(md).read_text(encoding="utf-8")
        header = text.split("\n", 1)[0]
        self.assertNotIn("\n", header)
        obj = json.loads(header[len("<!-- AIGC:"):-len(" -->")])
        self.assertEqual(obj, json.loads(pretty))

    def test_empty_file(self):
        md = self.p("empty.md")
        Path(md).write_bytes(b"")
        w.inject_markdown(md, AIGC_JSON)
        text = Path(md).read_text(encoding="utf-8")
        self.assertEqual(text, "<!-- AIGC:%s -->\n" % AIGC_JSON)

    def test_bad_inputs_raise(self):
        bad = self.p("bad.md")
        Path(bad).write_bytes(b"\xff\xfe\x00binary")
        with self.assertRaises(ValueError):
            w.inject_markdown(bad, AIGC_JSON)
        ok = self.p("ok.md")
        Path(ok).write_text("body\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            w.inject_markdown(ok, "{bad json}")
        with self.assertRaises(ValueError):
            w.inject_markdown(ok, '{"AIGC":{"X":"-->"}}')

    def test_missing_file_raises(self):
        with self.assertRaises(ValueError):
            w.inject_markdown(self.p("nope.md"), AIGC_JSON)

    def test_extract_roundtrip_when_reader_ready(self):
        if not hasattr(metadata, "_md_block"):
            self.skipTest("metadata 的 Markdown 读取面尚未落地（Lead 负责）")
        md = self.p("a.md")
        Path(md).write_text("body\n", encoding="utf-8")
        w.inject_markdown(md, AIGC_JSON)
        cands = metadata.extract_json_candidates(md)
        self.assertTrue(any(c.get("obj") == json.loads(AIGC_JSON)
                            for c in cands), cands)


if __name__ == "__main__":
    unittest.main()
