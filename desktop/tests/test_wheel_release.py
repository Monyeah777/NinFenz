#!/usr/bin/env python3
"""SLSA wheel release metadata and workflow regression tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import wheel_release as wr  # noqa: E402


class WheelMetadataTest(unittest.TestCase):
    def _fixture(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        wheel = root / "ninfenz_pyengine-0.1.0-cp311-cp311-manylinux_2_28_x86_64.whl"
        wheel.write_bytes(b"deterministic-wheel")
        return tmp, root, wheel

    def test_metadata_binds_source_toolchain_and_digest(self):
        _tmp, _root, wheel = self._fixture()
        doc = wr.metadata(
            wheel,
            source_commit="a" * 40,
            source_date_epoch=1793540116,
            rustc="rustc 1.99.1",
            maturin="maturin 1.16.0",
            python="3.11.14",
        )
        self.assertEqual("nf-python-wheel/1", doc["schema"])
        self.assertEqual("0.1.0", doc["version"])
        self.assertEqual("a" * 40, doc["source_commit"])
        self.assertEqual(64, len(doc["sha256"]))
        self.assertEqual(wheel.name, doc["filename"])

    def test_verify_detects_tampered_wheel(self):
        _tmp, root, wheel = self._fixture()
        doc = wr.metadata(
            wheel,
            source_commit="a" * 40,
            source_date_epoch=1793540116,
            rustc="rustc 1.99.1",
            maturin="maturin 1.16.0",
            python="3.11.14",
        )
        metadata_path = root / "wheel-metadata.json"
        metadata_path.write_text(json.dumps(doc), encoding="utf-8")
        sums = root / "WHEEL-SHA256SUMS"
        wr.write_checksums(sums, [wheel, metadata_path])
        sums.write_text(
            "\n".join(
                line.replace(f"  {wheel.name}", f"  ./{wheel.name}")
                if wheel.name in line else line
                for line in sums.read_text(encoding="ascii").splitlines()
            ) + "\n",
            encoding="ascii",
        )
        self.assertEqual([], wr.verify(wheel, metadata_path, sums, "a" * 40))
        wheel.write_bytes(b"tampered")
        self.assertTrue(
            any(
                "summary" in issue.lower() or "摘要" in issue
                for issue in wr.verify(wheel, metadata_path, sums, "a" * 40)
            )
        )

    def test_verify_rejects_source_commit_drift(self):
        _tmp, root, wheel = self._fixture()
        doc = wr.metadata(
            wheel,
            source_commit="a" * 40,
            source_date_epoch=1793540116,
            rustc="rustc 1.99.1",
            maturin="maturin 1.16.0",
            python="3.11.14",
        )
        metadata_path = root / "wheel-metadata.json"
        metadata_path.write_text(json.dumps(doc), encoding="utf-8")
        sums = root / "WHEEL-SHA256SUMS"
        wr.write_checksums(sums, [wheel, metadata_path])
        issues = wr.verify(wheel, metadata_path, sums, "b" * 40)
        self.assertTrue(any("source_commit" in issue for issue in issues), issues)


class WheelWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder_text = (ROOT / ".github" / "workflows" / "slsa-build-l3.yml").read_text(
            encoding="utf-8"
        )
        cls.publish = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "npm-publish.yml").read_text(encoding="utf-8")
        )

    def test_builder_builds_twice_with_pinned_toolchain(self):
        for needle in (
            "rustup toolchain install 1.99.1",
            "-r .github/requirements-wheel.txt",
            "quay.io/pypa/manylinux_2_28_x86_64@sha256:",
            "--compatibility manylinux_2_28",
            'cmp "$WHEEL_A" "$WHEEL_B"',
            "WHEEL-SHA256SUMS",
            "wheel-metadata.json",
        ):
            self.assertIn(needle, self.builder_text)
        requirements = (ROOT / ".github" / "requirements-wheel.txt").read_text(
            encoding="ascii"
        )
        self.assertIn("maturin==1.16.0", requirements)
        self.assertIn("--hash=sha256:", requirements)

    def test_provenance_and_vsa_cover_wheel_subjects(self):
        text = json.dumps(self.publish, ensure_ascii=False)
        for needle in (
            ".artifacts/release/*.whl",
            ".artifacts/release/WHEEL-SHA256SUMS",
            ".artifacts/release/wheel-metadata.json",
        ):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
