#!/usr/bin/env python3
"""ASVS V5.2.2: file extension and content-type agreement regression tests."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import file_format, repo_index  # noqa: E402


class FileFormatValidationTest(unittest.TestCase):
    def test_accepts_supported_content_that_matches_its_extension(self):
        cases = {
            ".json": b'{"ok":true}\n',
            ".jsonl": b'{"id":1}\n{"id":2}\n',
            ".toml": b'ok = true\n',
            ".yaml": b"ok: true\n",
            ".graphml": (
                b'<?xml version="1.0"?>'
                b'<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
                b"<graph/></graphml>"
            ),
            ".csv": b"name,value\nalpha,1\n",
            ".md": b"# heading\n\ntext\n",
            ".wasm": b"\x00asm\x01\x00\x00\x00",
        }
        for suffix, raw in cases.items():
            with self.subTest(suffix=suffix):
                file_format.validate_bytes(suffix, raw, source="fixture" + suffix)

    def test_rejects_binary_or_malformed_content(self):
        cases = {
            ".json": b'{"ok":\xff}',
            ".jsonl": b'{"ok":true}\nnot-json\n',
            ".toml": b"key = [\n",
            ".yaml": b"key: [\n",
            ".graphml": b'<?xml version="1.0"?><not-graphml/>',
            ".csv": b'name,value\n"unterminated,1\n',
            ".md": b"# heading\x00binary\n",
            ".wasm": b"not-wasm",
        }
        for suffix, raw in cases.items():
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                file_format.validate_bytes(suffix, raw, source="fixture" + suffix)

    def test_rejects_graphml_with_dtd_or_entities(self):
        raw = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE graphml [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b'<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
            b"<graph/></graphml>"
        )
        with self.assertRaises(ValueError):
            file_format.validate_bytes(".graphml", raw, source="fixture.graphml")

    def test_unknown_extension_is_rejected_in_the_accepted_local_file_surface(self):
        with self.assertRaises(ValueError):
            file_format.validate_bytes(".exe", b"MZ", source="fixture.exe")

    def test_repository_read_boundary_enforces_content_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "payload.json"
            bad.write_bytes(b'{"broken":\xff}')
            with self.assertRaises(ValueError):
                repo_index.read_text(root, "payload.json")

            good = root / "payload.json"
            good.write_bytes(b'{"ok":true}\n')
            self.assertEqual('{"ok":true}\n', repo_index.read_text(root, "payload.json"))


if __name__ == "__main__":
    unittest.main()
