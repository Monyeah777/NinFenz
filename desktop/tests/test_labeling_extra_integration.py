"""扩展容器接进主判定的回归（extra_integration）。

只测补丁层：MOV（metadata_extra 认、metadata.sniff 不认）能拿到五段报告，
D 段按"无标准内容口径"记 NA，而不是伪造哈希或直接 FAIL。
"""

import json
import struct
import sys
import zipfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core.labeling import (extra_integration, metadata,  # noqa: E402
                           metadata_extra, pipeline)

FIELDS = {"Label": 1, "ContentProducer": "1" * 27, "ProduceID": "MOV-1"}


def _atom(atype, body):
    return struct.pack(">I", 8 + len(body)) + atype + body


def make_mov(path):
    payload = json.dumps({"AIGC": FIELDS}, ensure_ascii=False).encode("utf-8")
    udta = _atom(b"udta", _atom(b"\xa9nam", payload))
    moov = _atom(b"moov", udta)
    ftyp = _atom(b"ftyp", b"qt  \x00\x00\x00\x00")
    Path(path).write_bytes(ftyp + moov)


def make_pptx(path):
    """最小 PPTX：pptx 主 sniffer 不认，metadata_extra 认。"""
    core = ('<?xml version="1.0"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>'
            + json.dumps({"AIGC": FIELDS}, ensure_ascii=False)
            + '</dc:title></cp:coreProperties>')
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("ppt/presentation.xml", "<presentation/>")
        zf.writestr("docProps/core.xml", core)


class ExtraIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.mov = str(self.dir / "a.mov")
        make_mov(self.mov)
        self.pptx = str(self.dir / "a.pptx")
        make_pptx(self.pptx)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sniff_and_extract(self):
        self.assertEqual(metadata_extra.sniff_extra(self.mov), "mov")
        entries = metadata_extra.extract_extra(self.mov)
        self.assertTrue(any("AIGC" in (e.get("text") or "") for e in entries))

    def test_main_metadata_does_not_recognize(self):
        self.assertEqual(metadata.sniff(self.pptx), "unknown")

    def test_build_report_uses_extra_container(self):
        rep = extra_integration.build_report(
            self.pptx, generated_at="2026-11-02T00:00:00+0800")
        self.assertIsNotNone(rep)
        self.assertEqual(rep["container"], "pptx")
        self.assertIn("B", rep["sections"])
        self.assertNotEqual(rep["sections"]["B"]["status"], "FAIL")
        self.assertEqual(rep["sections"]["D"]["status"], "PASS")
        d1 = next(it for it in rep["sections"]["D"]["items"] if it["id"] == "D1")
        self.assertIn("DFT", d1["detail"])
        self.assertEqual(rep["extra"]["cntsel"], "DFT")
        self.assertIn(rep["verdict"], ("PASS", "WARN"))

    def test_patch_restored_after_call(self):
        original = metadata.sniff
        extra_integration.build_report(self.pptx)
        self.assertIs(metadata.sniff, original)

    def test_unknown_file_returns_none(self):
        txt = str(self.dir / "x.txt")
        Path(txt).write_text("hello", encoding="utf-8")
        self.assertIsNone(extra_integration.build_report(txt))

    def test_pipeline_uses_extra_container(self):
        result = pipeline.evaluate(self.pptx)
        self.assertEqual(result["report"]["container"], "pptx")
        self.assertEqual(result["verdict"], result["report"]["verdict"])

    def test_selfcheck(self):
        rows = extra_integration.selfcheck()
        self.assertTrue(all(ok for _n, ok, _d in rows), rows)
        self.assertGreaterEqual(len(rows), 4)
        names = {n for n, _ok, _d in rows}
        self.assertIn("DFT 扣除", names)


if __name__ == "__main__":
    unittest.main()
