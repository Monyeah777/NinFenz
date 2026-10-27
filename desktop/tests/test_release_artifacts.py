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
VSA = ROOT / "scripts" / "build_vsa.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_vsa():
    spec = importlib.util.spec_from_file_location("test_release_build_vsa", VSA)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VSA}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
                       ".openvex.json", "SHA256SUMS", "release-metadata.json"):
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

    def test_vsa_verifies_bundle_and_signs_only_build_l2(self):
        policy_path = ROOT / "packaging/supply-chain/verification-policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        metadata = json.loads(
            (self.out / "release-metadata.json").read_text(encoding="utf-8")
        )
        module = _load_vsa()
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "release"
            shutil.copytree(self.out, bundle)
            metadata_path = bundle / "release-metadata.json"
            checked = json.loads(metadata_path.read_text(encoding="utf-8"))
            checked["release_ready"] = True
            metadata_path.write_text(json.dumps(checked), encoding="utf-8")
            self.assertEqual(
                [], module.verify_release(bundle, policy, metadata["source_commit"])
            )
            out = Path(tmp) / "vsa.json"
            proc = subprocess.run(
                [
                    sys.executable, str(VSA),
                    "--release-dir", str(bundle),
                    "--policy", str(policy_path),
                    "--repository", policy["repository"],
                    "--commit", metadata["source_commit"],
                    "--run-id", "123456",
                    "--time", "2026-10-27T00:00:00Z",
                    "--out", str(out),
                ],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", timeout=120,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(["SLSA_BUILD_LEVEL_2"], doc["verifiedLevels"])
            self.assertEqual(64, len(doc["policy"]["digest"]["sha256"]))

    def test_vsa_rejects_tamper_commit_vex_and_insufficient_builds(self):
        policy = json.loads(
            (ROOT / "packaging/supply-chain/verification-policy.json")
            .read_text(encoding="utf-8")
        )
        metadata = json.loads(
            (self.out / "release-metadata.json").read_text(encoding="utf-8")
        )
        module = _load_vsa()
        cases = ("commit", "checksum", "sums", "vex", "builds", "dirty")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                bundle = Path(tmp) / "release"
                shutil.copytree(self.out, bundle)
                if case == "commit":
                    issues = module.verify_release(bundle, policy, "0" * 40)
                    self.assertTrue(any("source_commit" in item for item in issues))
                    continue
                if case == "checksum":
                    target = next(bundle.glob("*.cdx.json"))
                    target.write_bytes(target.read_bytes() + b" ")
                    issues = module.verify_release(bundle, policy, metadata["source_commit"])
                    self.assertTrue(any("摘要不符" in item for item in issues))
                    continue
                if case == "sums":
                    tarball = next(bundle.glob("*.tgz")).name
                    sums = bundle / "SHA256SUMS"
                    sums.write_text(
                        "".join(
                            line for line in sums.read_text(encoding="ascii").splitlines(True)
                            if not line.endswith(f"  {tarball}\n")
                        ),
                        encoding="ascii",
                    )
                    issues = module.verify_release(bundle, policy, metadata["source_commit"])
                    self.assertTrue(any("未进 SHA256SUMS" in item for item in issues))
                    continue
                if case == "vex":
                    next(bundle.glob("*.openvex.json")).unlink()
                    issues = module.verify_release(bundle, policy, metadata["source_commit"])
                    self.assertTrue(any("OpenVEX" in item for item in issues))
                    continue
                if case == "dirty":
                    path = bundle / "release-metadata.json"
                    doc = json.loads(path.read_text(encoding="utf-8"))
                    doc["release_ready"] = False
                    path.write_text(json.dumps(doc), encoding="utf-8")
                    issues = module.verify_release(bundle, policy, metadata["source_commit"])
                    self.assertTrue(any("release_ready" in item for item in issues))
                    continue
                path = bundle / "release-metadata.json"
                doc = json.loads(path.read_text(encoding="utf-8"))
                doc["reproducible_build"]["independent_builds"] = 1
                path.write_text(json.dumps(doc), encoding="utf-8")
                issues = module.verify_release(bundle, policy, metadata["source_commit"])
                self.assertTrue(any("独立构建次数不足" in item for item in issues))

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
