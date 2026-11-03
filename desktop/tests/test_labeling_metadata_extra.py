"""多格式容器读取模块（metadata_extra）的回归测试。

作者：impl（DSH agent）· 2026-11-02
运行：cd desktop && PYTHONPATH=src python3 -m unittest \
      tests.test_labeling_metadata_extra -v

覆盖：7 个容器的 sniff/extract、扩展名+魔数双判、空文件、截断/坏 zip/坏 XML
等畸形输入不崩溃，以及 selfcheck() 全 PASS。
"""

from __future__ import annotations

import io
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import metadata, metadata_extra  # noqa: E402


# ---------------------------------------------------------------- 样例构造
def _atom(atype: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + atype + payload


def _ebml_size(size: int) -> bytes:
    for length in range(1, 8):
        if size < (1 << (7 * length)) - 1:
            return ((1 << (7 * length)) | size).to_bytes(length, "big")
    return ((1 << 56) | size).to_bytes(8, "big")


def _ebml(eid: int, payload: bytes) -> bytes:
    width = max(1, (eid.bit_length() + 7) // 8)
    return eid.to_bytes(width, "big") + _ebml_size(len(payload)) + payload


def _riff(cid: bytes, payload: bytes) -> bytes:
    pad = b"\x00" if len(payload) & 1 else b""
    return cid + struct.pack("<I", len(payload)) + payload + pad


def _zip_bytes(entries) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, body in entries:
            zf.writestr(name, body)
    return buf.getvalue()


CORE_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
    b'package/2006/metadata/core-properties"'
    b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
    b"<dc:title>NF-TITLE</dc:title><dc:creator>NF-CREATOR</dc:creator>"
    b"</cp:coreProperties>"
)
CUSTOM_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<Properties xmlns="http://schemas.openxmlformats.org/'
    b'officeDocument/2006/custom-properties"'
    b' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/'
    b'2006/docPropsVTypes">'
    b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2"'
    b' name="AIGC"><vt:lpwstr>{"AIGC":{"Label":"1"}}</vt:lpwstr></property>'
    b"</Properties>"
)


def _mov_bytes() -> bytes:
    nam = _atom(b"\xa9nam", struct.pack(">H", 12) + b"NF-MOV-TITLE")
    data = _atom(b"data", b"\x00\x00\x00\x01" + b"\x00\x00\x00\x00"
                 + b"NF-MOV-TOOL")
    udta = _atom(b"udta", nam + _atom(b"meta", b"\x00" * 4
                                      + _atom(b"ilst", _atom(b"\xa9too", data))))
    ftyp = _atom(b"ftyp", b"qt  \x00\x00\x02\x00qt  ")
    return ftyp + _atom(b"moov", udta)


def _mkv_bytes() -> bytes:
    simple = _ebml(0x67C8, _ebml(0x45A3, b"AIGC")
                   + _ebml(0x4487, b'{"AIGC":{"Label":"1"}}'))
    tags = _ebml(0x1254C367, _ebml(0x7373, simple))
    header = _ebml(0x1A45DFA3, _ebml(0x4282, b"matroska"))
    return header + _ebml(0x18538067, tags)


def _avi_bytes() -> bytes:
    info = _riff(b"LIST", b"INFO" + _riff(b"INAM", b"NF-AVI")
                 + _riff(b"ISFT", b"nf-avi-tool"))
    body = b"AVI " + info
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pptx_bytes() -> bytes:
    return _zip_bytes((
        ("[Content_Types].xml", b"<Types/>"),
        ("ppt/presentation.xml", b"<p/>"),
        ("docProps/core.xml", CORE_XML),
        ("docProps/custom.xml", CUSTOM_XML),
    ))


def _xlsx_bytes() -> bytes:
    return _zip_bytes((
        ("[Content_Types].xml", b"<Types/>"),
        ("xl/workbook.xml", b"<workbook/>"),
        ("docProps/core.xml", CORE_XML),
    ))


def _svg_bytes() -> bytes:
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<metadata>{"AIGC":{"Label":"1"}}</metadata>'
        b"<desc>NF-SVG-DESC</desc></svg>"
    )


def _rtf_bytes() -> bytes:
    return (b"{\\rtf1\\ansi{\\info{\\title NF-RTF-TITLE}"
            b"{\\*\\company NF-RTF-CO}}{\\pard body}}")


def _all_samples():
    return {
        "mov": (".mov", _mov_bytes()),
        "mkv": (".mkv", _mkv_bytes()),
        "avi": (".avi", _avi_bytes()),
        "pptx": (".pptx", _pptx_bytes()),
        "xlsx": (".xlsx", _xlsx_bytes()),
        "svg": (".svg", _svg_bytes()),
        "rtf": (".rtf", _rtf_bytes()),
    }


class HelperMixin:
    """临时目录 + 落盘工具。"""

    def _write(self, tmp, name, data):
        path = str(Path(tmp) / name)
        Path(path).write_bytes(data)
        return path


class SniffTest(HelperMixin, unittest.TestCase):
    def test_sniff_all_containers(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, (ext, data) in _all_samples().items():
                path = self._write(tmp, "sample" + ext, data)
                self.assertEqual(metadata_extra.sniff_extra(path), name,
                                 f"扩展名+魔数双判应识别 {name}")

    def test_sniff_rejects_wrong_extension_or_magic_and_empty(self):
        cases = [
            ("a.mov", b"\x89PNG\r\n\x1a\n"),              # 魔数不是 ftyp
            ("b.avi", _mov_bytes()),                      # 魔数不是 RIFF/AVI
            ("c.rtf", b"just plain text"),                # 缺 {\rtf
            ("d.pptx", b"PK\x03\x04broken"),              # 坏 zip
            ("e.xlsx", _zip_bytes([("x.xml", b"<x/>")])),  # zip 但缺 entry
            ("f.svg", b"<html><body>hi</body></html>"),   # 无 <svg
            ("g.txt", _rtf_bytes()),                      # 扩展名不支持
            ("h.mkv", b""),                               # 空文件
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in cases:
                path = self._write(tmp, name, data)
                self.assertIsNone(metadata_extra.sniff_extra(path), name)
                self.assertEqual(metadata_extra.extract_extra(path), [], name)


class MovTest(HelperMixin, unittest.TestCase):
    def test_mov_text_atoms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.mov", _mov_bytes())
            entries = metadata_extra.extract_extra(path)
        by_key = {e["key"]: e for e in entries}
        self.assertEqual(by_key["©nam"]["text"], "NF-MOV-TITLE")
        self.assertEqual(by_key["©nam"]["container"], "mov.udta")
        # iTunes data 子 atom 里的文本也要取到
        self.assertEqual(by_key["©too"]["text"], "NF-MOV-TOOL")
        self.assertTrue(all(e["offset"] >= 0 for e in entries))

    def test_mov_truncated_is_safe(self):
        bad = b"\x00\x00\x00\x40ftyp" + b"qt  "      # 声称 64 字节，实际 12
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "bad.mov", bad)
            self.assertEqual(metadata_extra.sniff_extra(path), "mov")
            self.assertEqual(metadata_extra.extract_extra(path), [])
            empty = self._write(tmp, "empty.mov",
                                _atom(b"ftyp", b"qt  ") + _atom(b"moov", b""))
            self.assertEqual(metadata_extra.extract_extra(empty), [])


class MkvTest(HelperMixin, unittest.TestCase):
    def test_mkv_aigc_simpletag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.mkv", _mkv_bytes())
            entries = metadata_extra.extract_extra(path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["container"], "mkv.Tags")
        self.assertEqual(entries[0]["key"], "AIGC")
        self.assertIn("AIGC", entries[0]["text"])
        self.assertEqual(entries[0]["kind"], "json")

    def test_mkv_malformed_or_no_tags_is_safe(self):
        no_tag = _ebml(0x1A45DFA3, _ebml(0x4282, b"matroska"))
        truncated = b"\x1aE\xdf\xa3\x81"                  # 长度 1，载荷缺失
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in (("a.mkv", no_tag), ("b.mkv", truncated)):
                path = self._write(tmp, name, data)
                self.assertEqual(metadata_extra.sniff_extra(path), "mkv")
                self.assertEqual(metadata_extra.extract_extra(path), [])


class AviTest(HelperMixin, unittest.TestCase):
    def test_avi_info_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.avi", _avi_bytes())
            entries = metadata_extra.extract_extra(path)
            bad = self._write(
                tmp, "bad.avi",
                b"RIFF\xff\xff\xff\xffAVI LIST\xff\xff\xff\xffINFO")
            self.assertEqual(metadata_extra.sniff_extra(bad), "avi")
            self.assertEqual(metadata_extra.extract_extra(bad), [])
        by_key = {e["key"]: e["text"] for e in entries}
        self.assertEqual(by_key, {"INAM": "NF-AVI", "ISFT": "nf-avi-tool"})


class OfficeTest(HelperMixin, unittest.TestCase):
    def test_pptx_core_and_custom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.pptx", _pptx_bytes())
            entries = metadata_extra.extract_extra(path)
        by_key = {e["key"]: e for e in entries}
        self.assertEqual(by_key["title"]["container"], "pptx.core")
        self.assertEqual(by_key["title"]["text"], "NF-TITLE")
        self.assertEqual(by_key["creator"]["text"], "NF-CREATOR")
        self.assertEqual(by_key["AIGC"]["container"], "pptx.custom")
        self.assertIn("AIGC", by_key["AIGC"]["text"])
        self.assertEqual(by_key["AIGC"]["kind"], "json")

    def test_xlsx_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.xlsx", _xlsx_bytes())
            entries = metadata_extra.extract_extra(path)
        self.assertEqual({e["key"] for e in entries}, {"title", "creator"})
        self.assertEqual({e["container"] for e in entries}, {"xlsx.core"})

    def test_office_bad_zip_and_missing_props_safe(self):
        no_props = _zip_bytes((("ppt/presentation.xml", b"<p/>"),))
        with tempfile.TemporaryDirectory() as tmp:
            bad = self._write(tmp, "bad.pptx", b"PK\x03\x04broken")
            self.assertIsNone(metadata_extra.sniff_extra(bad))
            self.assertEqual(metadata_extra.extract_extra(bad), [])
            path = self._write(tmp, "noprops.pptx", no_props)
            self.assertEqual(metadata_extra.sniff_extra(path), "pptx")
            self.assertEqual(metadata_extra.extract_extra(path), [])


class SvgTest(HelperMixin, unittest.TestCase):
    def test_svg_metadata_and_desc(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.svg", _svg_bytes())
            entries = metadata_extra.extract_extra(path)
            bad = self._write(tmp, "bad.svg", b"<svg><metadata>oops</svg>")
            self.assertEqual(metadata_extra.sniff_extra(bad), "svg")
            self.assertEqual(metadata_extra.extract_extra(bad), [])
        by_key = {e["key"]: e for e in entries}
        self.assertEqual(by_key["metadata"]["kind"], "json")
        self.assertIn("AIGC", by_key["metadata"]["text"])
        self.assertEqual(by_key["desc"]["text"], "NF-SVG-DESC")


class RtfTest(HelperMixin, unittest.TestCase):
    def test_rtf_info_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.rtf", _rtf_bytes())
            entries = metadata_extra.extract_extra(path)
            bad = self._write(tmp, "bad.rtf", b"{\\rtf1{\\info{\\title")
            self.assertEqual(metadata_extra.sniff_extra(bad), "rtf")
            self.assertIsInstance(metadata_extra.extract_extra(bad), list)
        by_key = {e["key"]: e["text"] for e in entries}
        self.assertEqual(by_key, {"title": "NF-RTF-TITLE",
                                  "company": "NF-RTF-CO"})


class ContractTest(HelperMixin, unittest.TestCase):
    def test_entries_match_metadata_entry_shape(self):
        sample = metadata._entry("c", "k", "t", 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, "s.mov", _mov_bytes())
            entries = metadata_extra.extract_extra(path)
        self.assertTrue(entries)
        for entry in entries:
            self.assertEqual(set(entry), set(sample))
            self.assertIsInstance(entry["offset"], int)
            self.assertEqual(entry["kind"], metadata._kind_of(
                entry["key"], entry["text"]))

    def test_selfcheck_all_pass(self):
        results = metadata_extra.selfcheck()
        self.assertEqual(len(results), len(metadata_extra.CONTAINERS))
        self.assertEqual({name for name, _ok, _detail in results},
                         set(metadata_extra.CONTAINERS))
        for name, ok, detail in results:
            self.assertTrue(ok, f"{name} 自检失败：{detail}")
            self.assertIsInstance(detail, str)


if __name__ == "__main__":
    unittest.main()
