"""External metadata must stay machine-readable and version-coherent."""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_sync_module():
    path = ROOT / "scripts" / "sync_llms.py"
    spec = importlib.util.spec_from_file_location("nf_sync_llms", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExternalMetadataTests(unittest.TestCase):
    def test_codemeta_is_json_and_version_matches_public_packages(self):
        codemeta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        npm = json.loads((ROOT / "packaging/npm/package.json").read_text(encoding="utf-8"))
        self.assertEqual(codemeta["@type"], "SoftwareSourceCode")
        self.assertEqual(codemeta["version"], pyproject["project"]["version"])
        self.assertEqual(codemeta["version"], npm["version"])
        self.assertEqual(codemeta["license"], "MIT")

    def test_security_txt_has_required_machine_fields(self):
        text = (ROOT / "site/.well-known/security.txt").read_text(encoding="utf-8")
        fields = {}
        for line in text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields.setdefault(key.strip().lower(), []).append(value.strip())
        self.assertTrue(fields.get("contact"))
        self.assertEqual(fields.get("canonical"), ["https://ninfenz.dev/.well-known/security.txt"])
        self.assertEqual(fields.get("policy"), ["https://github.com/Monyeah777/NinFenz/security/policy"])
        self.assertRegex(fields["expires"][0], r"^20\d\d-\d\d-\d\dT")

    def test_editorconfig_is_root_and_lf(self):
        text = (ROOT / ".editorconfig").read_text(encoding="utf-8")
        self.assertIn("root = true", text)
        self.assertIn("charset = utf-8", text)
        self.assertIn("end_of_line = lf", text)

    def test_root_llms_full_matches_site_source(self):
        sync = _load_sync_module()
        self.assertTrue(sync.synchronized())
        self.assertEqual((ROOT / "llms-full.txt").read_bytes(), (ROOT / "site/llms-full.txt").read_bytes())

    def test_sync_write_is_idempotent_and_check_detects_drift(self):
        sync = _load_sync_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "site").mkdir()
            source = root / "site" / "llms-full.txt"
            source.write_bytes(b"# NF\n\xe5\x86\x85\xe5\xae\xb9\n")
            sync.SOURCE = source
            sync.TARGET = root / "llms-full.txt"
            self.assertFalse(sync.synchronized())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sync.main(["--write"]), 0)
            self.assertEqual((root / "llms-full.txt").read_bytes(), source.read_bytes())
            self.assertTrue(sync.synchronized())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sync.main(["--check"]), 0)
            (root / "llms-full.txt").write_bytes(b"drift\n")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(sync.main(["--check"]), 1)


if __name__ == "__main__":
    unittest.main()
