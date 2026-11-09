"""Deterministic SPDX 3.0.1 SBOM builder with an honest AI Profile declaration.

The repository does not bundle model weights or training data.  The root element is
therefore an ``ai_AIPackage`` that advertises the application-layer AI contract
tooling, explicitly disclaims model training/bundling, and links its registered
software dependencies.  The builder is pure: callers supply the deterministic
version, declaration date, and dependency inventory.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

CONTEXT = "https://spdx.org/rdf/3.0.1/spdx-context.jsonld"
SPEC_VERSION = "3.0.1"
PROFILES = ("core", "software", "simpleLicensing", "ai")


def _id(base: str, name: str) -> str:
    return f"{base}#{name}"


def build(ver: str, when: str, deps: Iterable[dict], lic: str = "NOASSERTION") -> dict:
    """Build a compact SPDX 3.0.1 JSON-LD SBOM.

    ``dependencies`` rows are ``{name, version, purl, optional, reason}``.  Missing
    versions/licenses remain ``NOASSERTION`` instead of inventing evidence.
    """
    base = "https://ninfenz.dev/spdx/{}/{}".format(ver, when or "undated")
    creation = _id(base, "creation-info")
    tool = _id(base, "tool")
    supplier = _id(base, "supplier-ninfenz")
    upstream = _id(base, "supplier-upstream")
    root_pkg = _id(base, "pkg-ninfenz")
    product_license = _id(base, "license-product")
    cc0 = _id(base, "license-cc0")
    no_assert = _id(base, "license-noassertion")
    graph: list[dict[str, Any]] = [
        {
            "@type": "CreationInfo",
            "@id": creation,
            "specVersion": SPEC_VERSION,
            "created": (f"{when}T00:00:00Z") if when else "",
            "createdBy": [tool],
        },
        {
            "@type": "Tool",
            "@id": tool,
            "creationInfo": creation,
            "name": "NinFenz nf interop",
        },
        {
            "@type": "Organization",
            "@id": supplier,
            "creationInfo": creation,
            "name": "NinFenz project",
        },
        {
            "@type": "Organization",
            "@id": upstream,
            "creationInfo": creation,
            "name": "Upstream Python projects",
        },
        {
            "@type": "simplelicensing_LicenseExpression",
            "@id": product_license,
            "simplelicensing_licenseExpression": lic,
        },
        {
            "@type": "simplelicensing_LicenseExpression",
            "@id": cc0,
            "simplelicensing_licenseExpression": "CC0-1.0",
        },
        {
            "@type": "simplelicensing_LicenseExpression",
            "@id": no_assert,
            "simplelicensing_licenseExpression": "NOASSERTION",
        },
        {
            "@type": "ai_AIPackage",
            "@id": root_pkg,
            "creationInfo": creation,
            "name": "NinFenz",
            "software_packageVersion": ver,
            "software_packageUrl": f"pkg:generic/ninfenz@{ver}",
            "software_downloadLocation": "https://github.com/Monyeah777/NinFenz",
            "software_primaryPurpose": "application",
            "suppliedBy": supplier,
            "ai_autonomyType": "no",
            "ai_domain": ["content engineering", "AI agent tooling", "supply-chain assurance"],
            "ai_informationAboutApplication": (
                "Deterministic content contracts, verification gates, and evidence exports "
                "for downstream AI systems."
            ),
            "ai_informationAboutTraining": (
                "No model training is performed or shipped by this package."
            ),
            "ai_limitation": (
                "This package does not bundle model weights, training data, or an inference "
                "runtime; it does not certify downstream models."
            ),
            "ai_modelDataPreprocessing": ["not applicable: no training data bundled"],
            "ai_modelExplainability": [
                "Deterministic rule, schema, digest, and gate outputs; no learned model bundled."
            ],
            "ai_typeOfModel": ["model-agnostic application tooling"],
            "ai_useSensitivePersonalInformation": "no",
        },
    ]
    package_ids = [root_pkg]
    hard_ids: list[str] = []
    optional_ids: list[str] = []
    for row in sorted(deps, key=lambda item: str(item.get("name") or "")):
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        dep_id = _id(base, "pkg-" + name.lower().replace("_", "-").replace(".", "-"))
        version_text = str(row.get("version") or "NOASSERTION")
        package_ids.append(dep_id)
        (optional_ids if row.get("optional") else hard_ids).append(dep_id)
        graph.append({
            "@type": "software_Package",
            "@id": dep_id,
            "creationInfo": creation,
            "name": name,
            "software_packageVersion": version_text,
            "software_packageUrl": str(row.get("purl") or f"pkg:pypi/{name.lower()}"),
            "software_downloadLocation": "NOASSERTION",
            "software_primaryPurpose": "library",
            "suppliedBy": upstream,
            "comment": str(row.get("reason") or ""),
        })
    relations: list[dict[str, Any]] = []
    for index, dep_id in enumerate(hard_ids, 1):
        relations.append({
            "@type": "LifecycleScopedRelationship",
            "@id": _id(base, f"depends-on-{index}"),
            "creationInfo": creation,
            "from": root_pkg,
            "relationshipType": "dependsOn",
            "to": [dep_id],
        })
    for index, dep_id in enumerate(optional_ids, 1):
        relations.append({
            "@type": "LifecycleScopedRelationship",
            "@id": _id(base, f"optional-dependency-{index}"),
            "creationInfo": creation,
            "from": root_pkg,
            "relationshipType": "hasOptionalDependency",
            "to": [dep_id],
        })
    for index, package_id in enumerate(package_ids, 1):
        license_id = product_license if package_id == root_pkg else no_assert
        for kind in ("hasDeclaredLicense", "hasConcludedLicense"):
            relations.append({
                "@type": "Relationship",
                "@id": _id(base, f"license-{kind}-{index}"),
                "creationInfo": creation,
                "from": package_id,
                "relationshipType": kind,
                "to": [license_id],
            })
    relations.append({
        "@type": "Relationship",
        "@id": _id(base, "describes"),
        "creationInfo": creation,
        "from": _id(base, "document"),
        "relationshipType": "describes",
        "to": [root_pkg],
    })
    graph.extend(relations)
    graph.append({
        "@type": "software_Sbom",
        "@id": _id(base, "document"),
        "creationInfo": creation,
        "name": "ninfenz-spdx3-ai-profile",
        "dataLicense": cc0,
        "profileConformance": list(PROFILES),
        "rootElement": [root_pkg],
        "element": package_ids,
    })
    return {"@context": CONTEXT, "@graph": graph}


def validate(doc: dict[str, Any]) -> list[str]:
    """Validate compact JSON-LD identity, AI-profile honesty, and relationship closure."""
    issues: list[str] = []
    if doc.get("@context") != CONTEXT:
        issues.append("SPDX @context 不是 3.0.1")
    graph = doc.get("@graph")
    if not isinstance(graph, list) or not graph:
        return issues + ["SPDX @graph 为空"]
    ids: set[str] = set()
    by_type: dict[str, list[dict[str, Any]]] = {}
    for element in graph:
        if not isinstance(element, dict) or not element.get("@type"):
            issues.append("SPDX 图元素缺 @type")
            continue
        ident = str(element.get("@id") or "")
        if not ident:
            issues.append("SPDX 图元素缺 @id")
        elif ident in ids:
            issues.append(f"SPDX @id 重复：{ident}")
        ids.add(ident)
        by_type.setdefault(str(element["@type"]), []).append(element)
    docs = by_type.get("software_Sbom", [])
    if len(docs) != 1:
        issues.append("SPDX 必须恰有一个 software_Sbom")
    info = by_type.get("CreationInfo", [])
    if len(info) != 1 or info[0].get("specVersion") != SPEC_VERSION:
        issues.append("SPDX 必须恰有一个 3.0.1 CreationInfo")
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                          str(info[0].get("created") or "")):
        issues.append("SPDX CreationInfo.created 缺失或非 ISO 8601 UTC")
    roots = (docs or [{}])[0].get("rootElement") or []
    ai_pkgs = by_type.get("ai_AIPackage", [])
    root = next((pkg for pkg in ai_pkgs if pkg.get("@id") in roots), None)
    if len(roots) != 1 or root is None:
        issues.append("SPDX rootElement 必须指向唯一 ai_AIPackage")
    profiles = set((docs or [{}])[0].get("profileConformance") or [])
    if not set(PROFILES).issubset(profiles):
        issues.append("SPDX profileConformance 缺 core/software/simpleLicensing/ai")
    if root is not None:
        for key in ("name", "software_packageVersion", "software_packageUrl",
                    "software_primaryPurpose", "suppliedBy"):
            if not root.get(key):
                issues.append(f"SPDX AI 根包缺 {key}")
        if root.get("ai_autonomyType") != "no":
            issues.append("SPDX AI 根包须如实声明 ai_autonomyType=no")
        if root.get("ai_useSensitivePersonalInformation") != "no":
            issues.append("SPDX AI 根包须声明 ai_useSensitivePersonalInformation=no")
        if "No model training" not in str(root.get("ai_informationAboutTraining") or ""):
            issues.append("SPDX AI 根包须声明未训练模型")
        if "does not bundle model weights" not in str(root.get("ai_limitation") or ""):
            issues.append("SPDX AI 根包须声明未捆绑模型权重")
    for relation in by_type.get("Relationship", []) + \
            by_type.get("LifecycleScopedRelationship", []):
        refs = [relation.get("from"), *(relation.get("to") or [])]
        unknown = {ref for ref in refs if ref and ref not in ids}
        if unknown:
            issues.append(f"SPDX 关系指向未知 @id：{sorted(unknown)}")
    root_license_types = {
        relation.get("relationshipType")
        for relation in by_type.get("Relationship", [])
        if root is not None and relation.get("from") == root.get("@id")
    }
    if not {"hasDeclaredLicense", "hasConcludedLicense"}.issubset(root_license_types):
        issues.append("SPDX AI 根包缺 declared/concluded license 关系")
    for element in graph:
        for key in ("creationInfo", "suppliedBy", "dataLicense"):
            ref = element.get(key)
            if isinstance(ref, str) and ref.startswith("https://") and ref not in ids:
                issues.append(f"SPDX {key} 指向未知 @id：{ref}")
    return issues
