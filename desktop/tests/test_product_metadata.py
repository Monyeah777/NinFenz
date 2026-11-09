"""Canonical product metadata must govern every duplicated release surface."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import product_metadata

ROOT = Path(__file__).resolve().parents[2]


def _copy_code_package_surfaces(root):
    for rel in (
        "engine/rust/Cargo.toml",
        "engine/rust/canonical/Cargo.toml",
        "engine/rust/pyo3/Cargo.toml",
        "engine/rust/pyo3/pyproject.toml",
        "engine/rust/ffi/Cargo.toml",
        "engine/wasm/sha256-component/Cargo.toml",
        "engine/wasm/sha256/Cargo.toml",
        "engine/dotnet/src/Nf.Engine/Nf.Engine.csproj",
        "engine/dotnet/src/Nf.Engine/Interop.cs",
        "engine/dotnet/tools/nf-canonical/nf-canonical.csproj",
    ):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)


class ProductMetadataTest(unittest.TestCase):
    def test_repo_metadata_is_single_source(self):
        self.assertEqual([], product_metadata.check(ROOT))
        doc = product_metadata.load(ROOT)
        self.assertEqual("1.1.2", doc["version"])
        self.assertEqual("AGPL-3.0-only OR LicenseRef-Commercial",
                         doc["license_expression"])
        self.assertTrue(doc["release_bundle_required"])

    def test_drift_between_metadata_and_cli_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                "protocol", "scripts", "packaging", "LICENSES", "site", "skills",
                "desktop/src",
                "engine/dotnet/tools/nf-dotnet",
            ):
                shutil.copytree(ROOT / rel, root / rel)
            for rel in (
                "pyproject.toml", "codemeta.json", "CITATION.cff",
                "README.md", "README.en.md", "README.ja.md", "CONTRIBUTING.md",
                "REUSE.toml", "llms.txt", "llms-full.txt", "llms-install.md", "GLAMA.md",
                "LICENSE", "LICENSING.md", "COMMERCIAL.md", "MIT-NOTICE.md",
            ):
                shutil.copy2(ROOT / rel, root / rel)
            _copy_code_package_surfaces(root)
            package = root / "packaging" / "npm" / "package.json"
            doc = json.loads(package.read_text(encoding="utf-8"))
            doc["version"] = "1.0.5"
            package.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            issues = product_metadata.check(root)
            self.assertTrue(any("package.json" in issue for issue in issues), issues)

    def test_write_is_idempotent_and_uses_canonical_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                "protocol", "scripts", "packaging", "LICENSES", "site", "skills",
                "desktop/src",
                "engine/dotnet/tools/nf-dotnet",
            ):
                shutil.copytree(ROOT / rel, root / rel)
            for rel in (
                "pyproject.toml", "codemeta.json", "CITATION.cff",
                "README.md", "README.en.md", "README.ja.md", "CONTRIBUTING.md",
                "REUSE.toml", "llms.txt", "llms-full.txt", "llms-install.md", "GLAMA.md",
                "LICENSE", "LICENSING.md", "COMMERCIAL.md", "MIT-NOTICE.md",
            ):
                shutil.copy2(ROOT / rel, root / rel)
            _copy_code_package_surfaces(root)
            self.assertEqual([], product_metadata.write(root))

    def test_release_bundle_cannot_be_disabled(self):
        doc = json.loads((ROOT / product_metadata.REL).read_text(encoding="utf-8"))
        doc["release_bundle_required"] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / product_metadata.REL
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(ValueError):
                product_metadata.load(tmp)

    def test_licensing_product_truth_cannot_be_erased(self):
        original = json.loads((ROOT / product_metadata.REL).read_text(encoding="utf-8"))
        for key, value in (
            ("commercial_license_available", False),
            ("paid_hosted_tier", True),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                doc = dict(original)
                doc[key] = value
                path = Path(tmp) / product_metadata.REL
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(ValueError):
                    product_metadata.load(tmp)


if __name__ == "__main__":
    unittest.main()
