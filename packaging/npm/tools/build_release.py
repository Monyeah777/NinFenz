#!/usr/bin/env python3
"""Build deterministic npm release artifacts and release SBOMs.

This is the release-side gate, not the npm package's first-run installer.  It:

1. stages the tracked payload through the existing Node policy;
2. builds the npm tarball twice and fails unless the bytes match;
3. emits CycloneDX 1.6 and SPDX 3.0 JSON-LD SBOMs;
4. writes SHA256SUMS and a machine-readable release manifest.

The builder is deliberately stdlib-only.  External validators may consume its
output, but a clean checkout can reproduce and verify it without network access.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
PAYLOAD_DIR = PACKAGE_ROOT / "payload"
MANIFEST_NAME = "payload-manifest.json"
SBOM_SUPPLIER = "NinFenz"
SBOM_AUTHOR = "NinFenz release pipeline"
ECOSYSTEM_URL = "https://github.com/Monyeah777/NinFenz"
RELEASE_SCHEMA = "nf-npm-release/1"


class ReleaseError(RuntimeError):
    """A release precondition or artifact invariant failed."""


@dataclass(frozen=True)
class PackageFile:
    rel: str
    data: bytes
    mode: int = 0o644


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReleaseError(f"{path}: 不可读 JSON：{exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseError(f"{path}: 顶层必须是对象")
    return value


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} 失败：{(proc.stderr or proc.stdout).strip()}")
    return proc.stdout.strip()


def worktree_dirty() -> bool:
    return bool(git("status", "--porcelain", "--untracked-files=no"))


def source_epoch() -> int:
    value = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if value:
        if not value.isdigit():
            raise ReleaseError("SOURCE_DATE_EPOCH 必须是非负整数")
        return int(value)
    raw = git("show", "-s", "--format=%ct", "HEAD")
    if not raw.isdigit():
        raise ReleaseError(f"无法从 HEAD 读取提交时间：{raw!r}")
    return int(raw)


def stage_payload(dirty_allowed: bool) -> None:
    args = [sys.executable]
    node = shutil.which("node")
    if not node:
        raise ReleaseError("缺 node：无法运行 npm payload 暂存器")
    args = [node, str(PACKAGE_ROOT / "tools" / "stage-payload.mjs"), "--quiet"]
    if dirty_allowed:
        args.append("--allow-dirty")
    proc = subprocess.run(
        args,
        cwd=PACKAGE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise ReleaseError(f"payload 暂存失败：{detail[-1600:]}")


def _included_files(root: Path, entries: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in entries:
        rel = raw.replace("\\", "/").rstrip("/")
        target = (root / rel).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            raise ReleaseError(f"package.json files 越界：{raw}")
        if target.is_file():
            files.add(target)
        elif target.is_dir():
            files.update(p for p in target.rglob("*") if p.is_file())
        else:
            raise ReleaseError(f"package.json files 指向不存在的路径：{raw}")
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def package_files(variant: str = "npm") -> tuple[dict[str, Any], list[PackageFile]]:
    pkg = read_json(PACKAGE_ROOT / "package.json")
    if variant == "github-packages":
        pkg = json.loads(json.dumps(pkg))
        pkg["name"] = "@monyeah777/ninfenz"
        publish = dict(pkg.get("publishConfig") or {})
        publish["registry"] = "https://npm.pkg.github.com"
        publish.pop("provenance", None)
        pkg["publishConfig"] = publish
    elif variant != "npm":
        raise ReleaseError(f"未知发布变体：{variant}")
    required = {"package.json", "README.md", "LICENSE"}
    listed = pkg.get("files", [])
    if not isinstance(listed, list) or not all(isinstance(x, str) for x in listed):
        raise ReleaseError("package.json files 必须是字符串数组")
    entries = list(dict.fromkeys(["package.json", "README.md", "LICENSE", *listed]))
    out: list[PackageFile] = []
    for path in _included_files(PACKAGE_ROOT, entries):
        rel = path.relative_to(PACKAGE_ROOT).as_posix()
        if rel.startswith(("test/", "tools/", "node_modules/", "dist/")):
            raise ReleaseError(f"发布输入混入非发布目录：{rel}")
        if rel == ".npmrc" or rel.endswith((".pyc", ".pyo")):
            raise ReleaseError(f"发布输入混入敏感或生成文件：{rel}")
        data = path.read_bytes()
        if rel == "package.json":
            data = _json_bytes(pkg)
        out.append(PackageFile(rel=rel, data=data))
    for rel in required:
        if rel not in {entry.rel for entry in out}:
            raise ReleaseError(f"发布输入缺必需文件：{rel}")
    return pkg, out


def build_tarball(files: list[PackageFile]) -> bytes:
    raw = io.BytesIO()
    with (
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar,
    ):
        for entry in files:
            info = tarfile.TarInfo(name="package/" + entry.rel)
            info.size = len(entry.data)
            info.mode = entry.mode
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            tar.addfile(info, io.BytesIO(entry.data))
    data = bytearray(raw.getvalue())
    if len(data) < 10 or data[:2] != b"\x1f\x8b":
        raise ReleaseError("tarball 不是有效 gzip")
    # OS field is part of the header even though gzip does not checksum it.
    data[9] = 255
    return bytes(data)


def verify_tarball(tar: bytes, pkg: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(tar), mode="r:gz") as archive:
            members = {member.name: member for member in archive.getmembers() if member.isfile()}
            expected = {
                "package/payload/" + entry["path"]: entry
                for entry in manifest.get("files", [])
            }
            missing = sorted(set(expected) - set(members))
            if missing:
                issues.append("tarball 缺 payload 文件：" + ", ".join(missing[:3]))
            for name, entry in expected.items():
                if name not in members:
                    continue
                data = archive.extractfile(members[name])
                if data is None or sha256(data.read()) != entry["sha256"]:
                    issues.append("tarball payload 摘要不符：" + name)
            manifest_name = "package/payload/" + MANIFEST_NAME
            if manifest_name not in members:
                issues.append("tarball 缺 payload 清单")
            else:
                data = archive.extractfile(members[manifest_name])
                try:
                    embedded = json.loads((data.read() if data else b"").decode("utf-8"))
                except ValueError:
                    issues.append("tarball payload 清单不可解析")
                else:
                    if embedded != manifest:
                        issues.append("tarball payload 清单与发布清单不一致")
            package_name = "package/package.json"
            if package_name not in members:
                issues.append("tarball 缺 package.json")
            else:
                data = archive.extractfile(members[package_name])
                try:
                    embedded_pkg = json.loads((data.read() if data else b"").decode("utf-8"))
                except ValueError:
                    issues.append("tarball package.json 不可解析")
                else:
                    if embedded_pkg.get("version") != pkg.get("version"):
                        issues.append("tarball package.json 版本不一致")
    except (tarfile.TarError, OSError) as exc:
        issues.append(f"tarball 不可读：{exc}")
    return issues


def manifest_doc(require_clean: bool = True) -> dict[str, Any]:
    manifest = read_json(PAYLOAD_DIR / MANIFEST_NAME)
    if require_clean and manifest.get("worktree_dirty") is True:
        raise ReleaseError("payload 清单来自脏工作树，不能作为正式发布输入")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ReleaseError("payload 清单 files 为空")
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ReleaseError("payload 清单含非法文件项")
    return manifest


def _component_hash(data: bytes) -> dict[str, str]:
    return {"alg": "SHA-256", "content": sha256(data)}


def _spdx_hash(data: bytes) -> dict[str, str]:
    return {"algorithm": "sha256", "hashValue": sha256(data)}


def _purl(name: str, version: str, ecosystem: str = "generic") -> str:
    return f"pkg:{ecosystem}/{name}@{version}"


def _stable_uuid(tree: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ECOSYSTEM_URL}/npm/{tree}"))


def cyclonedx_doc(
    pkg: dict[str, Any],
    manifest: dict[str, Any],
    tarball_sha: str,
    generated_at: str,
) -> dict[str, Any]:
    version = str(pkg["version"])
    root_ref = f"pkg:npm/{quote(str(pkg['name']), safe='/')}@{version}"
    cli = (PAYLOAD_DIR / "scripts" / "nf.py").read_bytes()
    components = [
        {
            "type": "application",
            "bom-ref": f"nf:cli@{version}",
            "supplier": {"name": SBOM_SUPPLIER},
            "author": SBOM_SUPPLIER,
            "name": "ninfenz-cli",
            "version": version,
            "purl": _purl("ninfenz-cli", version),
            "licenses": [{"license": {"id": "AGPL-3.0-only"}}],
            "hashes": [_component_hash(cli)],
        },
        {
            "type": "data",
            "bom-ref": f"nf:payload@{manifest['tree_sha256']}",
            "supplier": {"name": SBOM_SUPPLIER},
            "author": SBOM_SUPPLIER,
            "name": "ninfenz-payload-tree",
            "version": manifest["tree_sha256"],
            "licenses": [
                {"license": {"id": "AGPL-3.0-only"}},
                {"license": {"id": "CC-BY-4.0"}},
            ],
            "properties": [
                {"name": "nf:file-count", "value": str(manifest["count"])},
                {"name": "nf:unpacked-bytes", "value": str(manifest["total_bytes"])},
            ],
        },
        {
            "type": "library",
            "bom-ref": "pkg:pypi/pyyaml@6.0.3",
            "supplier": {"name": "PyYAML maintainers"},
            "author": "PyYAML maintainers",
            "name": "PyYAML",
            "version": "6.0.3",
            "purl": "pkg:pypi/pyyaml@6.0.3",
            "licenses": [{"license": {"id": "MIT"}}],
            "scope": "optional",
        },
        {
            "type": "framework",
            "bom-ref": "nf:runtime/nodejs",
            "supplier": {"name": "OpenJS Foundation"},
            "author": "OpenJS Foundation",
            "name": "Node.js",
            "version": pkg.get("engines", {}).get("node", "unknown"),
            "licenses": [{"license": {"id": "MIT"}}],
            "properties": [{"name": "nf:dependency-kind", "value": "runtime-framework"}],
        },
        {
            "type": "framework",
            "bom-ref": "nf:runtime/cpython",
            "supplier": {"name": "Python Software Foundation"},
            "author": "Python Software Foundation",
            "name": "CPython",
            "version": ">=3.11",
            "licenses": [{"license": {"id": "PSF-2.0"}}],
            "properties": [{"name": "nf:dependency-kind", "value": "runtime-framework"}],
        },
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": "urn:uuid:" + _stable_uuid(
            f"{pkg['name']}:{manifest['tree_sha256']}"
        ),
        "version": 1,
        "metadata": {
            "timestamp": generated_at,
            "authors": [{"name": SBOM_AUTHOR}],
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "supplier": {"name": SBOM_SUPPLIER},
                "author": SBOM_SUPPLIER,
                "name": pkg["name"],
                "version": version,
                "description": pkg.get("description", ""),
                "purl": root_ref,
                "licenses": [{"license": {"id": "AGPL-3.0-only"}}],
                "hashes": [{"alg": "SHA-256", "content": tarball_sha}],
                "externalReferences": [
                    {"type": "website", "url": pkg.get("homepage", ECOSYSTEM_URL)},
                    {"type": "vcs", "url": pkg.get("repository", {}).get("url", ECOSYSTEM_URL)},
                ],
            },
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "nf-release-builder",
                        "version": "1",
                        "supplier": {"name": SBOM_SUPPLIER},
                    }
                ]
            },
            "properties": [
                {
                    "name": "nf:ntia-minimum-elements",
                    "value": (
                        "supplier,name,version,identifier,relationships,author,timestamp"
                    ),
                },
                {"name": "nf:source-commit", "value": manifest["source_commit"]},
                {"name": "nf:payload-tree-sha256", "value": manifest["tree_sha256"]},
            ],
        },
        "components": components,
        "dependencies": [
            {
                "ref": root_ref,
                "dependsOn": [component["bom-ref"] for component in components],
            }
        ],
        "compositions": [{"aggregate": "complete", "assemblies": [root_ref]}],
    }


def spdx_doc(
    pkg: dict[str, Any],
    manifest: dict[str, Any],
    tarball_sha: str,
    generated_at: str,
) -> dict[str, Any]:
    version = str(pkg["version"])
    tree = str(manifest["tree_sha256"])
    base = (
        f"{ECOSYSTEM_URL}/spdx/npm/{quote(str(pkg['name']), safe='')}/"
        f"{version}/{tree}"
    )
    root = f"{base}#package"
    cli_data = (PAYLOAD_DIR / "scripts" / "nf.py").read_bytes()
    tool = f"{base}#tool"
    supplier = f"{base}#supplier"
    creation = f"{base}#creation"
    cli = f"{base}#cli"
    payload = f"{base}#payload"
    pyyaml = f"{base}#pyyaml"
    node = f"{base}#nodejs"
    cpython = f"{base}#cpython"
    pyyaml_supplier = f"{base}#pyyaml-supplier"
    nodejs_supplier = f"{base}#nodejs-supplier"
    python_supplier = f"{base}#python-supplier"
    agpl = f"{base}#license-agpl"
    mit = f"{base}#license-mit"
    psf = f"{base}#license-psf"
    ccby = f"{base}#license-ccby"
    payload_license = f"{base}#license-payload"
    graph: list[dict[str, Any]] = [
        {
            "@type": "Tool",
            "@id": tool,
            "creationInfo": creation,
            "name": "nf-release-builder",
            "summary": "NinFenz deterministic release artifact builder",
        },
        {
            "@type": "Organization",
            "@id": supplier,
            "creationInfo": creation,
            "name": SBOM_SUPPLIER,
        },
        {
            "@type": "CreationInfo",
            "@id": creation,
            "specVersion": "3.0.1",
            "created": generated_at,
            "createdBy": [supplier],
            "createdUsing": [tool],
            "profile": ["core", "software"],
            "dataLicense": "CC0-1.0",
        },
        {
            "@type": "SpdxDocument",
            "@id": f"{base}#document",
            "creationInfo": creation,
            "name": f"{pkg['name']} {version}",
            "profile": ["core", "software"],
            "dataLicense": "CC0-1.0",
            "rootElement": [root],
            "element": [
                root, cli, payload, pyyaml, node, cpython, tool, supplier,
                pyyaml_supplier, nodejs_supplier, python_supplier,
                agpl, mit, psf, ccby, payload_license,
            ],
        },
        {
            "@type": "SoftwarePackage",
            "@id": root,
            "creationInfo": creation,
            "name": pkg["name"],
            "summary": pkg.get("description", ""),
            "packageVersion": version,
            "packageUrl": f"pkg:npm/{quote(str(pkg['name']), safe='/')}@{version}",
            "primaryPurpose": "application",
            "suppliedBy": supplier,
            "concludedLicense": agpl,
            "declaredLicense": agpl,
            "downloadLocation": pkg.get("homepage", ECOSYSTEM_URL),
            "builtTime": generated_at,
            "releaseTime": generated_at,
            "verifiedUsing": [{"@type": "Hash", "algorithm": "sha256", "hashValue": tarball_sha}],
            "comment": f"payloadTreeSha256={tree}; sourceCommit={manifest['source_commit']}",
        },
        {
            "@type": "SoftwarePackage",
            "@id": cli,
            "creationInfo": creation,
            "name": "ninfenz-cli",
            "packageVersion": version,
            "packageUrl": _purl("ninfenz-cli", version),
            "primaryPurpose": "application",
            "suppliedBy": supplier,
            "concludedLicense": agpl,
            "declaredLicense": agpl,
            "verifiedUsing": [_spdx_hash(cli_data)],
        },
        {
            "@type": "SoftwarePackage",
            "@id": payload,
            "creationInfo": creation,
            "name": "ninfenz-payload-tree",
            "packageVersion": tree,
            "packageUrl": f"pkg:generic/ninfenz-payload@{tree}",
            "primaryPurpose": "data",
            "suppliedBy": supplier,
            "concludedLicense": payload_license,
            "declaredLicense": payload_license,
            "comment": f"fileCount={manifest['count']}; unpackedBytes={manifest['total_bytes']}",
        },
        {
            "@type": "SoftwarePackage",
            "@id": pyyaml,
            "creationInfo": creation,
            "name": "PyYAML",
            "packageVersion": "6.0.3",
            "packageUrl": "pkg:pypi/pyyaml@6.0.3",
            "primaryPurpose": "library",
            "suppliedBy": pyyaml_supplier,
            "concludedLicense": mit,
            "declaredLicense": mit,
        },
        {
            "@type": "SoftwarePackage",
            "@id": node,
            "creationInfo": creation,
            "name": "Node.js",
            "packageVersion": pkg.get("engines", {}).get("node", "unknown"),
            "packageUrl": "pkg:generic/nodejs",
            "primaryPurpose": "framework",
            "suppliedBy": nodejs_supplier,
            "concludedLicense": mit,
            "declaredLicense": mit,
        },
        {
            "@type": "SoftwarePackage",
            "@id": cpython,
            "creationInfo": creation,
            "name": "CPython",
            "packageVersion": ">=3.11",
            "packageUrl": "pkg:generic/cpython",
            "primaryPurpose": "framework",
            "suppliedBy": python_supplier,
            "concludedLicense": psf,
            "declaredLicense": psf,
        },
        {
            "@type": "Organization",
            "@id": pyyaml_supplier,
            "creationInfo": creation,
            "name": "PyYAML maintainers",
        },
        {
            "@type": "Organization",
            "@id": nodejs_supplier,
            "creationInfo": creation,
            "name": "OpenJS Foundation",
        },
        {
            "@type": "Organization",
            "@id": python_supplier,
            "creationInfo": creation,
            "name": "Python Software Foundation",
        },
        {
            "@type": "ListedLicense",
            "@id": agpl,
            "name": "GNU Affero General Public License v3.0 only",
            "licenseId": "AGPL-3.0-only",
            "isOsiApproved": True,
        },
        {
            "@type": "ListedLicense",
            "@id": mit,
            "name": "MIT License",
            "licenseId": "MIT",
            "isOsiApproved": True,
        },
        {
            "@type": "ListedLicense",
            "@id": psf,
            "name": "Python Software Foundation License 2.0",
            "licenseId": "PSF-2.0",
            "isOsiApproved": True,
        },
        {
            "@type": "ListedLicense",
            "@id": ccby,
            "name": "Creative Commons Attribution 4.0 International",
            "licenseId": "CC-BY-4.0",
            "isOsiApproved": False,
        },
        {
            "@type": "ConjunctiveLicenseSet",
            "@id": payload_license,
            "member": [agpl, ccby],
        },
    ]
    relationships = [
        (root, "dependsOn", [cli, payload, pyyaml, node, cpython]),
        (f"{base}#document", "describes", [root]),
    ]
    for index, (from_id, kind, to_ids) in enumerate(relationships, 1):
        if not to_ids:
            continue
        graph.append(
            {
                "@type": "Relationship",
                "@id": f"{base}#relationship-{index}",
                "creationInfo": creation,
                "from": from_id,
                "relationshipType": kind,
                "to": to_ids,
            }
        )
    return {
        "@context": "https://spdx.org/rdf/3.0.1/spdx-context.jsonld",
        "@graph": graph,
    }


def validate_sboms(cdx: dict[str, Any], spdx: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if cdx.get("bomFormat") != "CycloneDX" or cdx.get("specVersion") != "1.6":
        issues.append("CycloneDX 根字段不是 CycloneDX 1.6")
    root = (cdx.get("metadata") or {}).get("component") or {}
    for key in ("supplier", "name", "version", "bom-ref", "hashes"):
        if not root.get(key):
            issues.append(f"CycloneDX/NTIA 根组件缺 {key}")
    refs = {root.get("bom-ref")}
    for component in cdx.get("components") or []:
        for key in ("bom-ref", "name", "version", "supplier"):
            if not component.get(key):
                issues.append(f"CycloneDX/NTIA 组件缺 {key}: {component.get('name')!r}")
        if component.get("bom-ref") in refs:
            issues.append(f"CycloneDX bom-ref 重复：{component.get('bom-ref')}")
        refs.add(component.get("bom-ref"))
    dep = (cdx.get("dependencies") or [{}])[0]
    if dep.get("ref") != root.get("bom-ref"):
        issues.append("CycloneDX 根依赖关系缺失")
    unknown = set(dep.get("dependsOn") or []) - refs
    if unknown:
        issues.append(f"CycloneDX 依赖指向未知组件：{sorted(unknown)}")

    if not str(spdx.get("@context", "")).startswith("https://spdx.org/rdf/3.0"):
        issues.append("SPDX 3 JSON-LD @context 不合法")
    graph = spdx.get("@graph")
    if not isinstance(graph, list) or not graph:
        return issues + ["SPDX 3 @graph 为空"]
    ids = set()
    by_type: dict[str, list[dict[str, Any]]] = {}
    for element in graph:
        if not isinstance(element, dict) or not element.get("@type"):
            issues.append("SPDX 3 @graph 元素缺 @type")
            continue
        ident = element.get("@id")
        if not ident:
            issues.append(f"SPDX 3 {element.get('@type')} 缺 @id")
        elif ident in ids:
            issues.append(f"SPDX 3 @id 重复：{ident}")
        ids.add(ident)
        by_type.setdefault(str(element["@type"]), []).append(element)
    if len(by_type.get("SpdxDocument", [])) != 1:
        issues.append("SPDX 3 必须恰有一个 SpdxDocument")
    if not by_type.get("CreationInfo"):
        issues.append("SPDX 3 缺 CreationInfo")
    packages = by_type.get("SoftwarePackage", [])
    roots = (by_type.get("SpdxDocument") or [{}])[0].get("rootElement") or []
    if len(roots) != 1:
        issues.append("SPDX 3 rootElement 必须恰有一个")
    root_pkg = next((p for p in packages if p.get("@id") in roots), None)
    if not root_pkg:
        issues.append("SPDX 3 rootElement 未指向 SoftwarePackage")
    else:
        for key in ("name", "packageVersion", "packageUrl", "suppliedBy", "verifiedUsing"):
            if not root_pkg.get(key):
                issues.append(f"SPDX 3/NTIA 根包缺 {key}")
    for package in packages:
        for key in (
            "name", "packageVersion", "packageUrl", "suppliedBy",
            "concludedLicense", "declaredLicense",
        ):
            if not package.get(key):
                issues.append(f"SPDX 3/NTIA 包缺 {key}: {package.get('name')!r}")
    rels = by_type.get("Relationship", [])
    if not rels:
        issues.append("SPDX 3 缺 Relationship")
    for rel in rels:
        endpoints = [rel.get("from"), *(rel.get("to") or [])]
        unknown = {x for x in endpoints if x and x not in ids}
        if unknown:
            issues.append(f"SPDX 3 关系指向未知 spdxId：{sorted(unknown)}")
    return issues


def build_variant(
    pkg: dict[str, Any],
    files: list[PackageFile],
    manifest: dict[str, Any],
    generated_at: str,
) -> tuple[bytes, dict[str, Any], dict[str, Any], dict[str, Any]]:
    tar_one = build_tarball(files)
    tar_two = build_tarball(files)
    if tar_one != tar_two:
        raise ReleaseError("同一输入两次 tar 构建字节不一致")
    expected_version = str(pkg["version"])
    if manifest.get("package_version") != expected_version:
        raise ReleaseError("payload 清单 version 与 package.json 不一致")
    tar_issues = verify_tarball(tar_one, pkg, manifest)
    if tar_issues:
        raise ReleaseError("tarball 内容校验失败：" + "; ".join(tar_issues[:6]))
    tar_sha = sha256(tar_one)
    cdx = cyclonedx_doc(pkg, manifest, tar_sha, generated_at)
    spdx = spdx_doc(pkg, manifest, tar_sha, generated_at)
    issues = validate_sboms(cdx, spdx)
    if issues:
        raise ReleaseError("SBOM 校验失败：" + "; ".join(issues[:6]))
    return tar_one, cdx, spdx, manifest


def deterministic_inputs(
    npm_pkg: dict[str, Any],
    npm_files: list[PackageFile],
    github_pkg: dict[str, Any],
    github_files: list[PackageFile],
    allow_dirty: bool,
) -> tuple[
    tuple[bytes, dict[str, Any], dict[str, Any]],
    tuple[bytes, dict[str, Any], dict[str, Any]],
    dict[str, Any],
]:
    manifest = manifest_doc(require_clean=not allow_dirty)
    generated_at = datetime.fromtimestamp(
        int(manifest["source_date_epoch"]), tz=UTC
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    npm_tar, npm_cdx, npm_spdx, _ = build_variant(
        npm_pkg, npm_files, manifest, generated_at
    )
    github_tar, github_cdx, github_spdx, _ = build_variant(
        github_pkg, github_files, manifest, generated_at
    )
    return (
        (npm_tar, npm_cdx, npm_spdx),
        (github_tar, github_cdx, github_spdx),
        manifest,
    )


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_artifacts(
    out: Path,
    pkg: dict[str, Any],
    npm_artifacts: tuple[bytes, dict[str, Any], dict[str, Any]],
    github_pkg: dict[str, Any],
    github_artifacts: tuple[bytes, dict[str, Any], dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, str]:
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ReleaseError(f"输出目录非空：{out}（修复指引：删除旧构建或换空目录）")
    out.mkdir(parents=True, exist_ok=True)
    version = str(pkg["version"])
    npm_tar, npm_cdx, npm_spdx = npm_artifacts
    github_tar, github_cdx, github_spdx = github_artifacts
    names = {
        "tarball": f"ninfenz-{version}.tgz",
        "cyclonedx": f"ninfenz-{version}.cdx.json",
        "spdx": f"ninfenz-{version}.spdx3.json",
        "payload_manifest": f"ninfenz-{version}.payload-manifest.json",
    }
    github_names = {
        "tarball": f"monyeah777-ninfenz-{version}.tgz",
        "cyclonedx": f"monyeah777-ninfenz-{version}.cdx.json",
        "spdx": f"monyeah777-ninfenz-{version}.spdx3.json",
    }
    data = {
        names["tarball"]: npm_tar,
        names["cyclonedx"]: _json_bytes(npm_cdx),
        names["spdx"]: _json_bytes(npm_spdx),
        github_names["tarball"]: github_tar,
        github_names["cyclonedx"]: _json_bytes(github_cdx),
        github_names["spdx"]: _json_bytes(github_spdx),
        names["payload_manifest"]: _json_bytes(manifest),
    }
    for name, content in data.items():
        (out / name).write_bytes(content)
    checksums = "".join(f"{sha256(content)}  {name}\n" for name, content in sorted(data.items()))
    (out / "SHA256SUMS").write_text(checksums, encoding="ascii", newline="\n")
    metadata = {
        "schema": RELEASE_SCHEMA,
        "package": pkg["name"],
        "version": version,
        "source_commit": manifest["source_commit"],
        "source_date_epoch": manifest["source_date_epoch"],
        "payload_tree_sha256": manifest["tree_sha256"],
        "tarball_sha256": sha256(npm_tar),
        "reproducible_build": {
            "verified": True,
            "independent_builds": 2,
            "artifacts": {
                "npm": sha256(npm_tar),
                "github_packages": sha256(github_tar),
            },
        },
        "sbom": {
            "cyclonedx": {"path": names["cyclonedx"], "spec_version": "1.6"},
            "spdx": {"path": names["spdx"], "spec_version": "3.0.1"},
            "github_packages": {
                "cyclonedx": github_names["cyclonedx"],
                "spdx": github_names["spdx"],
            },
            "ntia_minimum_elements": True,
        },
        "release_ready": manifest.get("worktree_dirty") is False,
        "artifact_names": names,
        "github_packages_names": github_names,
    }
    (out / "release-metadata.json").write_bytes(_json_bytes(metadata))
    return names


def verify_release(out: Path) -> list[str]:
    issues: list[str] = []
    sums_path = out / "SHA256SUMS"
    metadata_path = out / "release-metadata.json"
    if not sums_path.is_file():
        return [f"缺 {sums_path}"]
    if not metadata_path.is_file():
        return [f"缺 {metadata_path}"]
    seen: dict[str, str] = {}
    for line in sums_path.read_text(encoding="ascii").splitlines():
        digest, sep, name = line.partition("  ")
        if not sep or len(digest) != 64 or not name:
            issues.append(f"非法 SHA256SUMS 行：{line!r}")
            continue
        seen[name] = digest
        path = out / name
        if not path.is_file():
            issues.append(f"校验和指向缺件：{name}")
        elif sha256(path.read_bytes()) != digest:
            issues.append(f"摘要不符：{name}")
    metadata = read_json(metadata_path)
    mapped = []
    for key in ("artifact_names", "github_packages_names"):
        values = metadata.get(key)
        if not isinstance(values, dict):
            issues.append(f"release-metadata 缺 {key}")
            continue
        mapped.extend(str(value) for value in values.values())
    missing_mapped = sorted(set(mapped) - set(seen))
    if missing_mapped:
        issues.append(f"release-metadata 工件未进 SHA256SUMS：{missing_mapped}")
    manifest_path = out / str(metadata.get("artifact_names", {}).get("payload_manifest"))
    if manifest_path.is_file():
        manifest = read_json(manifest_path)
        pkg = {"version": metadata.get("version")}
        for tarball_path in sorted(out.glob("*.tgz")):
            issues.extend(verify_tarball(tarball_path.read_bytes(), pkg, manifest))
    else:
        issues.append("payload manifest 缺失")
    cdx_paths = sorted(out.glob("*.cdx.json"))
    spdx_paths = sorted(out.glob("*.spdx3.json"))
    if not cdx_paths or len(cdx_paths) != len(spdx_paths):
        issues.append("SBOM 文件缺失或 CycloneDX/SPDX 数量不一致")
    else:
        for cdx_path, spdx_path in zip(cdx_paths, spdx_paths, strict=True):
            issues.extend(validate_sboms(read_json(cdx_path), read_json(spdx_path)))
    return issues


def build(out: Path, allow_dirty: bool, skip_stage: bool) -> dict[str, str]:
    dirty = worktree_dirty()
    if dirty and not allow_dirty:
        raise ReleaseError("工作树有未提交的受跟踪改动；正式发布拒绝构建（开发可用 --allow-dirty）")
    if not skip_stage:
        stage_payload(allow_dirty)
    pkg, files = package_files()
    github_pkg, github_files = package_files("github-packages")
    npm_artifacts, github_artifacts, manifest = deterministic_inputs(
        pkg, files, github_pkg, github_files, allow_dirty
    )
    names = write_artifacts(
        out, pkg, npm_artifacts, github_pkg, github_artifacts, manifest
    )
    issues = verify_release(out)
    if issues:
        raise ReleaseError("发布工件终检失败：" + "; ".join(issues[:8]))
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建可复现 npm 发布工件与 SBOM")
    parser.add_argument("--out", help="不存在的空输出目录（构建时必填）")
    parser.add_argument("--allow-dirty", action="store_true", help="开发态；产物不可作为正式发布")
    parser.add_argument(
        "--skip-stage",
        action="store_true",
        help="复用当前 payload（只用于已暂存输入）",
    )
    parser.add_argument("--verify", metavar="DIR", help="只校验已有发布目录，不构建")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            issues = verify_release(Path(args.verify))
            if issues:
                for issue in issues:
                    print("✗ " + issue, file=sys.stderr)
                return 1
            print("✓ 发布工件、SHA256SUMS 与双 SBOM 一致")
            return 0
        if not args.out:
            parser.error("构建时必须提供 --out")
        names = build(Path(args.out), args.allow_dirty, args.skip_stage)
    except ReleaseError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print("✓ 可复现发布工件已生成")
    for key in ("tarball", "cyclonedx", "spdx", "payload_manifest"):
        print(f"  {key}: {names[key]}")
    print("  npm reproducible_builds: 2")
    print("  github-packages reproducible_builds: 2")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
