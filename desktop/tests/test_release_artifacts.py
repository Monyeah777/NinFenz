#!/usr/bin/env python3
"""Reproducible npm release artifacts and SBOM release-gate tests."""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "packaging" / "npm" / "tools" / "build_release.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReleaseArtifactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("无 node，无法运行 npm payload 暂存器")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "release"
        proc = subprocess.run(
            [sys.executable, str(BUILDER), "--out", str(cls.out), "--allow-dirty"],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=900,
        )
        if proc.returncode != 0:
            raise AssertionError((proc.stdout + proc.stderr)[-2400:])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    def test_expected_release_bundle_is_present_and_verifies(self):
        names = {path.name for path in self.out.iterdir()}
        for suffix in (".tgz", ".cdx.json", ".spdx3.json", ".payload-manifest.json",
                       "SHA256SUMS", "release-metadata.json"):
            self.assertTrue(
                any(name.endswith(suffix) or name == suffix for name in names),
                f"缺发布文件 {suffix}：{sorted(names)}",
            )
        proc = subprocess.run(
            [sys.executable, str(BUILDER), "--verify", str(self.out)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-1600:])

    def test_metadata_marks_two_builds_and_no_wall_clock(self):
        metadata = json.loads((self.out / "release-metadata.json").read_text(encoding="utf-8"))
        self.assertTrue(metadata["reproducible_build"]["verified"])
        self.assertEqual(2, metadata["reproducible_build"]["independent_builds"])
        manifest = json.loads(next(self.out.glob("*.payload-manifest.json"))
                              .read_text(encoding="utf-8"))
        self.assertIsInstance(manifest["source_date_epoch"], int)
        self.assertTrue(manifest["generated_at"].endswith("Z"))
        tar = next(self.out.glob("*.tgz")).read_bytes()
        self.assertEqual(b"\x00\x00\x00\x00", tar[4:8], "gzip mtime 未归零")
        self.assertEqual(255, tar[9], "gzip OS 字节未归一")

    def test_second_build_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            second = Path(tmp) / "release"
            proc = subprocess.run(
                [sys.executable, str(BUILDER), "--out", str(second),
                 "--allow-dirty", "--skip-stage"],
                cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=900,
            )
            self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-1600:])
            first_names = sorted(path.name for path in self.out.iterdir())
            self.assertEqual(first_names, sorted(path.name for path in second.iterdir()))
            for name in first_names:
                self.assertEqual(
                    _sha(self.out / name),
                    _sha(second / name),
                    f"第二次构建字节不一致：{name}",
                )

    def test_checksum_gate_catches_one_byte_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "release"
            shutil.copytree(self.out, copy)
            target = next(copy.glob("*.cdx.json"))
            target.write_bytes(target.read_bytes() + b" ")
            proc = subprocess.run(
                [sys.executable, str(BUILDER), "--verify", str(copy)],
                cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=300,
            )
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("摘要不符", proc.stderr)

    def test_official_sbom_validators_when_available(self):
        modules = ("cyclonedx", "spdx_tools", "rdflib")
        if any(importlib.util.find_spec(name) is None for name in modules):
            self.skipTest("SBOM 验证依赖未安装；npm-release CI 运行固定 requirements-sbom.txt")
        proc = subprocess.run(
            [sys.executable, "scripts/validate_sboms.py", str(self.out)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        self.assertEqual(0, proc.returncode, (proc.stdout + proc.stderr)[-2000:])


if __name__ == "__main__":
    unittest.main()
