"""JPEG / PDF 标识写入的回归测试（writers_image_pdf）。

作者：impl（DSH agent）· 2026-11-02
运行：cd nf-labelcheck && python3 -m unittest tests.test_writers_image_pdf -v
"""

import json
import os
import re
import tempfile
import unittest
from pathlib import Path

sys_path_root = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if os.path.join(sys_path_root, "desktop", "src") not in __import__("sys").path:
    __import__("sys").path.insert(
        0, os.path.join(sys_path_root, "desktop", "src"))

from core.labeling import metadata as md
from core.labeling import writers_image_pdf as w

AIGC_JSON = (
    '{"AIGC":{"Label":"1",'
    '"ContentProducer":"001091350100M000100Y4300000",'
    '"ProduceID":"pid20250101v123456"}}')
UNICODE_JSON = ('{"AIGC":{"Label":1,"ContentProducer":"某内容公司",'
                '"ProduceID":"PID-中文-1"}}')


class WritersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def p(self, name):
        return str(self.dir / name)

    # ------------------------------------------------------------ JPEG
    def test_jpeg_roundtrip_ascii(self):
        jpg = self.p("a.jpg")
        md.make_jpeg_with_xmp(jpg, "<x:xmpmeta>old</x:xmpmeta>")
        w.inject_jpeg_xmp(jpg, AIGC_JSON)
        cands = md.extract_json_candidates(jpg)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["container"], "jpeg.app1.xmp")
        self.assertEqual(cands[0]["obj"], json.loads(AIGC_JSON))
        self.assertEqual(cands[0]["raw"], AIGC_JSON)

    def test_jpeg_roundtrip_unicode(self):
        jpg = self.p("u.jpg")
        md.make_jpeg_with_xmp(jpg, "<x:xmpmeta>old</x:xmpmeta>")
        w.inject_jpeg_xmp(jpg, UNICODE_JSON)
        cands = md.extract_json_candidates(jpg)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["obj"], json.loads(UNICODE_JSON))
        self.assertEqual(cands[0]["raw"], UNICODE_JSON)

    def test_jpeg_sos_eoi_bytes_unchanged(self):
        jpg = self.p("a.jpg")
        md.make_jpeg_with_xmp(jpg, "<x:xmpmeta>old</x:xmpmeta>")
        before = Path(jpg).read_bytes()
        w.inject_jpeg_xmp(jpg, AIGC_JSON)
        after = Path(jpg).read_bytes()
        sos_before = before.index(b"\xff\xda")
        sos_after = after.index(b"\xff\xda")
        self.assertEqual(before[sos_before:], after[sos_after:])
        self.assertTrue(after.endswith(b"\xff\xd9"))

    def test_jpeg_replaces_old_xmp_single_copy(self):
        jpg = self.p("a.jpg")
        md.make_jpeg_with_xmp(jpg, "<x:xmpmeta>old</x:xmpmeta>")
        w.inject_jpeg_xmp(jpg, AIGC_JSON)
        w.inject_jpeg_xmp(jpg, UNICODE_JSON)     # 第二次写入应替换而非叠加
        data = Path(jpg).read_bytes()
        self.assertEqual(data.count(b"http://ns.adobe.com/xap/1.0/"), 1)
        cands = md.extract_json_candidates(jpg)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["raw"], UNICODE_JSON)

    def test_jpeg_preserves_exif_user_comment(self):
        jpg = self.p("e.jpg")
        md.make_jpeg_with_exif(jpg, "原始 EXIF 注释")
        w.inject_jpeg_xmp(jpg, AIGC_JSON)
        items = md.extract(jpg)
        exif = [x for x in items
                if x["container"] == "jpeg.exif.UserComment"]
        self.assertEqual(len(exif), 1)
        self.assertEqual(exif[0]["text"], "原始 EXIF 注释")
        self.assertEqual(len(md.extract_json_candidates(jpg)), 1)

    def test_jpeg_rejects_bad_inputs(self):
        bad = self.p("bad.bin")
        Path(bad).write_bytes(b"not a jpeg")
        with self.assertRaises(ValueError):
            w.inject_jpeg_xmp(bad, AIGC_JSON)
        trunc = self.p("t.jpg")
        Path(trunc).write_bytes(b"\xff\xd8")
        with self.assertRaises(ValueError):
            w.inject_jpeg_xmp(trunc, AIGC_JSON)
        good = self.p("g.jpg")
        md.make_jpeg_with_xmp(good, "<x:xmpmeta/>")
        with self.assertRaises(ValueError):
            w.inject_jpeg_xmp(good, "not-json")
        with self.assertRaises(ValueError):
            w.inject_jpeg_xmp(good, "")

    def test_jpeg_rejects_too_large_payload(self):
        jpg = self.p("a.jpg")
        md.make_jpeg_with_xmp(jpg, "<x:xmpmeta/>")
        big = '{"AIGC":{"Pad":"%s"}}' % ("x" * 70000)
        with self.assertRaises(ValueError):
            w.inject_jpeg_xmp(jpg, big)

    # ------------------------------------------------------------ PDF
    def test_pdf_roundtrip_ascii(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        w.inject_pdf_info(pdf, AIGC_JSON)
        cands = md.extract_json_candidates(pdf)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["container"], "pdf.info")
        self.assertEqual(cands[0]["key"], "AIGC")
        self.assertEqual(cands[0]["obj"], json.loads(AIGC_JSON))
        self.assertEqual(cands[0]["raw"], AIGC_JSON)

    def test_pdf_prefix_bytes_unchanged(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        before = Path(pdf).read_bytes()
        w.inject_pdf_info(pdf, AIGC_JSON)
        after = Path(pdf).read_bytes()
        # 原文件整体是前缀（只追加，不改写）；第一个 %%EOF 偏移不变
        self.assertTrue(after.startswith(before))
        self.assertEqual(before.index(b"%%EOF"), after.index(b"%%EOF"))
        self.assertEqual(after.count(b"%%EOF"), 2)

    def test_pdf_keeps_original_info_keys(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        w.inject_pdf_info(pdf, AIGC_JSON)
        items = [x for x in md.extract(pdf) if x["container"] == "pdf.info"]
        keys = {x["key"] for x in items}
        self.assertIn("AIGC", keys)
        self.assertIn("Title", keys)          # 原 Info 键仍可读
        title = [x["text"] for x in items
                 if x["key"] == "Title" and x["text"] == "nf-labelcheck"]
        self.assertTrue(title)

    def test_pdf_repeat_same_json_is_noop(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        w.inject_pdf_info(pdf, AIGC_JSON)
        once = Path(pdf).read_bytes()
        w.inject_pdf_info(pdf, AIGC_JSON)
        twice = Path(pdf).read_bytes()
        self.assertEqual(once, twice)          # 同 JSON 不追加修订
        cands = md.extract_json_candidates(pdf)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["raw"], AIGC_JSON)

    def test_pdf_different_json_appends_revision(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        w.inject_pdf_info(pdf, AIGC_JSON)
        other = '{"AIGC":{"Label":2,"ProduceID":"P-2"}}'
        w.inject_pdf_info(pdf, other)
        data = Path(pdf).read_bytes()
        self.assertEqual(data.count(b"%%EOF"), 3)
        self.assertEqual(data.count(b"/AIGC "), 2)   # 历史修订各留一份（增量语义）
        cands = md.extract_json_candidates(pdf)
        self.assertEqual(len(cands), 2)
        self.assertEqual(cands[-1]["raw"], other)

    def test_pdf_trailer_links_previous_xref(self):
        pdf = self.p("a.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        before = Path(pdf).read_bytes()
        old_off = int(re.search(rb"startxref\s+(\d+)", before).group(1))
        w.inject_pdf_info(pdf, AIGC_JSON)
        data = Path(pdf).read_bytes()
        table_start = data.rfind(b"\nxref\n") + 1
        tail = data[table_start:]
        self.assertIn(b"/Prev %d" % old_off, tail)
        m = re.search(rb"/Info\s+(\d+)\s+0\s+R", tail)
        self.assertIsNotNone(m)
        new_off = int(re.search(rb"startxref\s+(\d+)\s+%%EOF", data).group(1))
        self.assertTrue(data[new_off:].startswith(b"xref"))

    def test_pdf_unicode_json_object_equal(self):
        pdf = self.p("u.pdf")
        md.make_pdf_with_xmp(pdf, "<x:xmpmeta/>")
        w.inject_pdf_info(pdf, UNICODE_JSON)
        cands = md.extract_json_candidates(pdf)
        self.assertEqual(len(cands), 1)
        # PDF 字面量回 ASCII：raw 是 \uXXXX 转义形态，但解析出的对象必须相同
        self.assertEqual(cands[0]["obj"], json.loads(UNICODE_JSON))
        self.assertIsInstance(cands[0]["raw"], str)

    def test_pdf_rejects_xref_stream(self):
        pdf = self.p("x.pdf")
        Path(pdf).write_bytes(
            b"%PDF-1.5\n1 0 obj\n<< /Type /XRef /Size 2 /W [1 1 1] >>\n"
            b"endobj\nstartxref\n9\n%%EOF\n")
        with self.assertRaises(ValueError) as ctx:
            w.inject_pdf_info(pdf, AIGC_JSON)
        self.assertIn("xref 流 PDF 写入未支持", str(ctx.exception))

    def test_pdf_rejects_bad_inputs(self):
        cases = {
            "empty.pdf": b"",
            "notpdf.pdf": b"not a pdf",
            "nostart.pdf": b"%PDF-1.4\n%%EOF\n",
            "notrailer.pdf": (
                b"%PDF-1.4\nxref\n0 1\n0000000000 65535 f \n"
                b"startxref\n9\n%%EOF\n"),
        }
        for name, blob in cases.items():
            path = self.p(name)
            Path(path).write_bytes(blob)
            with self.assertRaises(ValueError):
                w.inject_pdf_info(path, AIGC_JSON)
        good = self.p("g.pdf")
        md.make_pdf_with_xmp(good, "<x:xmpmeta/>")
        bad_off = re.sub(rb"startxref\s+\d+", b"startxref\n999999999",
                         Path(good).read_bytes())
        Path(good).write_bytes(bad_off)
        with self.assertRaises(ValueError):
            w.inject_pdf_info(good, AIGC_JSON)
        with self.assertRaises(ValueError):
            w.inject_pdf_info(good, "{bad json}")


if __name__ == "__main__":
    unittest.main()
