#!/usr/bin/env python3
"""Validate generated CycloneDX 1.6 and SPDX 3 JSON-LD release SBOMs."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
from core import json_doc  # noqa: E402


def _json(path: Path) -> dict[str, Any]:
    return json_doc.loads(path.read_text(encoding="utf-8"), dict, what=str(path))


def validate_cyclonedx(path: Path) -> list[str]:
    try:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator
    except ImportError as exc:
        raise RuntimeError(
            "缺 CycloneDX 验证器（修复指引：安装 .github/requirements-sbom.txt）"
        ) from exc

    doc = _json(path)
    error = JsonStrictValidator(SchemaVersion.V1_6).validate_str(
        json.dumps(doc, ensure_ascii=False)
    )
    if error is not None:
        return [f"{path.name}: CycloneDX 1.6 schema: {error}"]
    root = (doc.get("metadata") or {}).get("component") or {}
    refs = {root.get("bom-ref")}
    issues: list[str] = []
    for key in ("supplier", "name", "version", "bom-ref", "hashes"):
        if not root.get(key):
            issues.append(f"{path.name}: NTIA 根组件缺 {key}")
    for component in doc.get("components") or []:
        for key in ("bom-ref", "name", "version", "supplier"):
            if not component.get(key):
                issues.append(f"{path.name}: NTIA 组件缺 {key}: {component.get('name')!r}")
        if component.get("bom-ref") in refs:
            issues.append(f"{path.name}: bom-ref 重复：{component.get('bom-ref')}")
        refs.add(component.get("bom-ref"))
    deps = (doc.get("dependencies") or [{}])[0]
    if deps.get("ref") != root.get("bom-ref"):
        issues.append(f"{path.name}: 缺根依赖关系")
    unknown = set(deps.get("dependsOn") or []) - refs
    if unknown:
        issues.append(f"{path.name}: 依赖指向未知组件：{sorted(unknown)}")
    return issues


def _spdx_context() -> dict[str, Any]:
    resource = (
        importlib.resources.files("spdx_tools.spdx3.writer.json_ld")
        .joinpath("context.json")
    )
    return json_doc.loads(resource.read_text(encoding="utf-8"), dict,
                          what="spdx_tools JSON-LD context")


def _index_spdx_graph(
    path: Path, graph: list[Any]
) -> tuple[list[str], set[str], dict[str, list[dict[str, Any]]]]:
    issues: list[str] = []
    ids: set[str] = set()
    by_type: dict[str, list[dict[str, Any]]] = {}
    for element in graph:
        if not isinstance(element, dict) or not element.get("@type"):
            issues.append(f"{path.name}: 元素缺 @type")
            continue
        ident = element.get("@id")
        if not ident:
            issues.append(f"{path.name}: {element.get('@type')} 缺 @id")
        elif ident in ids:
            issues.append(f"{path.name}: @id 重复：{ident}")
        ids.add(ident)
        by_type.setdefault(str(element["@type"]), []).append(element)
    return issues, ids, by_type


def _validate_spdx_required(
    path: Path, ids: set[str], by_type: dict[str, list[dict[str, Any]]]
) -> list[str]:
    issues: list[str] = []
    if len(by_type.get("SpdxDocument", [])) != 1:
        issues.append(f"{path.name}: 必须恰有一个 SpdxDocument")
    if not by_type.get("CreationInfo"):
        issues.append(f"{path.name}: 缺 CreationInfo")
    roots = (by_type.get("SpdxDocument") or [{}])[0].get("rootElement") or []
    packages = by_type.get("SoftwarePackage", [])
    root = next((p for p in packages if p.get("@id") in roots), None)
    if len(roots) != 1 or root is None:
        issues.append(f"{path.name}: rootElement 必须指向唯一 SoftwarePackage")
    elif not all(root.get(k) for k in ("name", "packageVersion", "packageUrl",
                                         "suppliedBy", "verifiedUsing")):
        issues.append(f"{path.name}: SPDX/NTIA 根包字段不全")
    for package in packages:
        for key in (
            "name", "packageVersion", "packageUrl", "suppliedBy",
            "concludedLicense", "declaredLicense",
        ):
            if not package.get(key):
                issues.append(
                    f"{path.name}: SPDX/NTIA 包缺 {key}: {package.get('name')!r}"
                )
    for rel in by_type.get("Relationship", []):
        if rel.get("from") not in ids or any(x not in ids for x in (rel.get("to") or [])):
            issues.append(f"{path.name}: Relationship 指向未知 @id")
    return issues


def validate_spdx3(path: Path) -> list[str]:
    try:
        from rdflib import Graph
    except ImportError as exc:
        raise RuntimeError(
            "缺 rdflib JSON-LD 解析器（修复指引：安装 .github/requirements-sbom.txt）"
        ) from exc

    issues: list[str] = []
    doc = _json(path)
    if not str(doc.get("@context", "")).startswith("https://spdx.org/rdf/3.0"):
        issues.append(f"{path.name}: @context 不是 SPDX 3.0")
    graph = doc.get("@graph")
    if not isinstance(graph, list) or not graph:
        return issues + [f"{path.name}: @graph 为空"]
    index_issues, ids, by_type = _index_spdx_graph(path, graph)
    issues.extend(index_issues)
    issues.extend(_validate_spdx_required(path, ids, by_type))
    local = dict(doc)
    local["@context"] = _spdx_context()
    try:
        parsed = Graph().parse(data=json.dumps(local, ensure_ascii=False), format="json-ld")
    except Exception as exc:  # rdflib raises parser-specific exception classes
        issues.append(f"{path.name}: JSON-LD 解析失败：{exc}")
    else:
        if len(parsed) == 0:
            issues.append(f"{path.name}: JSON-LD 未展开出 RDF 三元组")
    return issues


def validate_release(directory: Path) -> list[str]:
    cdx = sorted(directory.glob("*.cdx.json"))
    spdx = sorted(directory.glob("*.spdx3.json"))
    if not cdx or len(cdx) != len(spdx):
        return [
            f"{directory}: CycloneDX/SPDX 数量必须一致且非零，"
            f"实得 {len(cdx)}/{len(spdx)}"
        ]
    issues: list[str] = []
    for path in cdx:
        issues.extend(validate_cyclonedx(path))
    for path in spdx:
        issues.extend(validate_spdx3(path))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验发布目录中的 CycloneDX 1.6 与 SPDX 3 SBOM")
    parser.add_argument("directory", nargs="?", default="packaging/npm/dist/release")
    args = parser.parse_args(argv)
    try:
        issues = validate_release(Path(args.directory))
    except (OSError, ValueError, ImportError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"✗ {issue}", file=sys.stderr)
    if issues:
        return 1
    print("✓ CycloneDX 1.6 schema 与 SPDX 3 JSON-LD/NTIA 形状通过")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
