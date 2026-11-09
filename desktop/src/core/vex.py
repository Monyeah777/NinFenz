"""OpenVEX 0.2.0 and CycloneDX 1.6 VEX projections from one disposition ledger."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from . import product_metadata

DISPOSITION_REL = "results/supply-chain/vuln-disposition.json"
OPENVEX_REL = "results/supply-chain/ninfenz.openvex.json"
CYCLONEDX_REL = "results/supply-chain/ninfenz.cdx-vex.json"
FALLBACK_PRODUCT = "pkg:npm/ninfenz@0.0.0-dev"
STATUSES = {"not_affected", "affected", "fixed", "under_investigation"}
CYCLONEDX_STATE = {
    "not_affected": "not_affected",
    "affected": "affected",
    "fixed": "fixed",
    "under_investigation": "in_triage",
}
JUSTIFICATION = {
    "component_not_present": "code_not_present",
    "vulnerable_code_not_present": "code_not_present",
    "vulnerable_code_not_in_execute_path": "code_not_reachable",
    "vulnerable_code_cannot_be_controlled_by_adversary":
        "protected_by_mitigating_control",
    "inline_mitigations_already_exist": "protected_by_mitigating_control",
}
CYCLONEDX_RESPONSES = {
    "can_not_fix", "will_not_fix", "update", "rollback", "workaround_available",
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: 顶层必须是对象（修复指引：恢复 JSON 对象）")
    return value


def _disposition(root: Path) -> tuple[dict[str, Any], list[Any], str]:
    disposition = _json(root / DISPOSITION_REL)
    findings = disposition.get("findings")
    if not isinstance(findings, list):
        raise ValueError(
            f"{DISPOSITION_REL} findings 必须是数组"
            "（修复指引：恢复 findings: []）"
        )
    reviewed = str(disposition.get("reviewed_at") or "")
    if len(reviewed) != 10:
        raise ValueError(
            "reviewed_at 必须是 YYYY-MM-DD"
            "（修复指引：填写实际复核日期）"
        )
    return disposition, findings, reviewed


def _identity(disposition: dict[str, Any]) -> str:
    payload = json.dumps(
        disposition, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _default_product(root: Path) -> str:
    if (root / product_metadata.REL).is_file():
        product = product_metadata.load(root)
        return (
            f"pkg:npm/{quote(product['distribution_names']['npm'], safe='/')}"
            f"@{product['version']}"
        )
    path = root / "packaging" / "npm" / "package.json"
    if not path.is_file():
        return FALLBACK_PRODUCT
    package = _json(path)
    name = str(package.get("name") or "").strip()
    version = str(package.get("version") or "").strip()
    if not name or not version:
        raise ValueError(
            "packaging/npm/package.json 缺 name/version"
            "（修复指引：恢复 npm 包身份）"
        )
    return f"pkg:npm/{quote(name, safe='/')}@{version}"


def _finding(
    finding: Any,
) -> tuple[dict[str, Any], str, str, str]:
    if not isinstance(finding, dict):
        raise ValueError("finding 必须是对象（修复指引：删除标量 finding）")
    vulnerability = str(finding.get("vulnerability") or "").strip()
    status = str(finding.get("status") or "").strip()
    product = str(finding.get("product") or "").strip()
    if not vulnerability or status not in STATUSES:
        raise ValueError(
            f"finding 缺 vulnerability 或 status 非法：{finding!r}"
            "（修复指引：使用登记状态并填写漏洞 ID）"
        )
    return finding, vulnerability, status, product


def vex_doc(root: Path, product: str = "") -> dict[str, Any]:
    product = product or _default_product(root)
    disposition, findings, reviewed = _disposition(root)
    statements: list[dict[str, Any]] = []
    for raw in findings:
        raw, vulnerability, status, finding_product = _finding(raw)
        statement: dict[str, Any] = {
            "vulnerability": {"name": vulnerability},
            "products": [{"@id": finding_product or product}],
            "status": status,
        }
        if status == "not_affected":
            statement["justification"] = str(raw.get("justification") or "")
            statement["impact_statement"] = str(raw.get("impact_statement") or "")
            if not statement["justification"] or not statement["impact_statement"]:
                raise ValueError(
                    f"not_affected 缺 justification/impact：{vulnerability}"
                    "（修复指引：补齐规范枚举与影响说明）"
                )
        elif status in {"affected", "under_investigation"}:
            statement["action_statement"] = str(raw.get("action_statement") or "")
            if not statement["action_statement"]:
                raise ValueError(
                    f"{status} 缺 action_statement：{vulnerability}"
                    "（修复指引：写明处置动作）"
                )
        else:
            action = str(raw.get("action_statement") or "").strip()
            if action:
                statement["action_statement"] = action
        statements.append(statement)
    identity = _identity(disposition)[:16]
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": f"https://ninfenz.dev/vex/{reviewed}/{identity}",
        "author": "NinFenz maintainers",
        "timestamp": f"{reviewed}T00:00:00Z",
        "version": 1,
        "tooling": "NinFenz core.vex",
        "statements": statements,
    }


def _component(purl: str) -> dict[str, Any]:
    if not purl.startswith("pkg:") or "@" not in purl:
        raise ValueError(
            f"CycloneDX product 必须是带版本的 purl：{purl!r}"
            "（修复指引：使用 pkg:ecosystem/name@version）"
        )
    body = purl[4:]
    ecosystem_and_name, version = body.rsplit("@", 1)
    _ecosystem, _sep, package_name = ecosystem_and_name.partition("/")
    name = unquote(package_name or ecosystem_and_name)
    if not name or not version:
        raise ValueError(
            f"CycloneDX product purl 不完整：{purl!r}"
            "（修复指引：补齐包名和版本）"
        )
    return {
        "type": "application",
        "bom-ref": purl,
        "name": name,
        "version": version,
        "purl": purl,
    }


def _analysis(vulnerability: str, status: str, raw: dict[str, Any]) -> dict[str, Any]:
    analysis: dict[str, Any] = {"state": CYCLONEDX_STATE[status]}
    if status == "not_affected":
        justification = str(raw.get("justification") or "").strip()
        if justification not in JUSTIFICATION:
            raise ValueError(
                "CycloneDX not_affected justification 不是可映射枚举："
                f"{justification!r}"
                "（修复指引：使用 OpenVEX 规范 justification）"
            )
        impact = str(raw.get("impact_statement") or "").strip()
        if not impact:
            raise ValueError(
                f"not_affected 缺 impact：{vulnerability}"
                "（修复指引：写明不可达或不受影响依据）"
            )
        analysis.update({
            "justification": JUSTIFICATION[justification],
            "detail": impact,
        })
    elif status in {"affected", "under_investigation"}:
        action = str(raw.get("action_statement") or "").strip()
        if not action:
            raise ValueError(
                f"{status} 缺 action_statement：{vulnerability}"
                "（修复指引：写明处置动作）"
            )
        analysis["detail"] = action
    else:
        detail = str(raw.get("action_statement") or "").strip()
        if detail:
            analysis["detail"] = detail
    responses = raw.get("responses") or []
    if not isinstance(responses, list) or not all(
        isinstance(item, str) and item in CYCLONEDX_RESPONSES for item in responses
    ):
        raise ValueError(
            f"CycloneDX responses 非法或未知：{responses!r}"
            "（修复指引：只使用 CycloneDX 1.6 response 枚举）"
        )
    if responses:
        analysis["response"] = responses
    return analysis


def cyclonedx_vex_doc(root: Path, product: str = "") -> dict[str, Any]:
    product = product or _default_product(root)
    disposition, findings, reviewed = _disposition(root)
    component = _component(product)
    vulnerabilities = []
    for raw in findings:
        raw, vulnerability, status, finding_product = _finding(raw)
        if finding_product and finding_product != product:
            raise ValueError(
                f"finding product 未登记为 metadata.component：{finding_product!r}"
                "（修复指引：每个产品分别生成发布束）"
            )
        vulnerabilities.append({
            "id": vulnerability,
            "source": {"name": "NinFenz vulnerability disposition"},
            "analysis": _analysis(vulnerability, status, raw),
            "affects": [{"ref": product}],
        })
    identity = _identity(disposition)
    urn = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"https://ninfenz.dev/vex/{reviewed}/{identity}",
    )
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{urn}",
        "version": 1,
        "metadata": {
            "timestamp": f"{reviewed}T00:00:00Z",
            "authors": [{"name": "NinFenz maintainers"}],
            "tools": [{"name": "NinFenz core.vex", "version": "1"}],
            "component": component,
        },
        "components": [component],
        "vulnerabilities": vulnerabilities,
    }


def validate_vex(doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if doc.get("@context") != "https://openvex.dev/ns/v0.2.0":
        issues.append("VEX 不是 OpenVEX 0.2.0")
    for key in ("@id", "author", "timestamp", "version", "tooling"):
        if not doc.get(key):
            issues.append(f"VEX 缺 {key}")
    statements = doc.get("statements")
    if not isinstance(statements, list):
        return issues + ["VEX statements 必须是数组"]
    for statement in statements:
        if not isinstance(statement, dict):
            issues.append("VEX statement 必须是对象")
            continue
        vulnerability = statement.get("vulnerability")
        if not isinstance(vulnerability, dict) or not vulnerability.get("name"):
            issues.append("VEX statement 缺 vulnerability.name")
        if statement.get("status") not in STATUSES:
            issues.append(f"VEX statement status 非法：{statement.get('status')!r}")
        products = statement.get("products")
        if not isinstance(products, list) or not products:
            issues.append("VEX statement 缺 products")
        elif any(
            not isinstance(product, dict)
            or not str(product.get("@id", "")).startswith("pkg:")
            for product in products
        ):
            issues.append("VEX product 必须是 purl")
        if statement.get("status") == "not_affected":
            for key in ("justification", "impact_statement"):
                if not statement.get(key):
                    issues.append(f"VEX not_affected 缺 {key}")
    return issues


def _metadata_issues(doc: dict[str, Any]) -> tuple[list[str], set[str]]:
    issues: list[str] = []
    if doc.get("bomFormat") != "CycloneDX" or doc.get("specVersion") != "1.6":
        issues.append("CycloneDX VEX 必须是 CycloneDX 1.6")
    if not str(doc.get("serialNumber") or "").startswith("urn:uuid:"):
        issues.append("CycloneDX VEX serialNumber 必须是 urn:uuid")
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("timestamp"):
        issues.append("CycloneDX VEX 缺 metadata.timestamp")
    component = metadata.get("component") if isinstance(metadata, dict) else None
    if not isinstance(component, dict):
        issues.append("CycloneDX VEX 缺 metadata.component")
        component = {}
    root_ref = str(component.get("bom-ref") or "")
    if not str(component.get("purl") or "").startswith("pkg:"):
        issues.append("CycloneDX VEX metadata.component 缺 purl")
    refs = {root_ref} if root_ref else set()
    components = doc.get("components") or []
    if not isinstance(components, list):
        issues.append("CycloneDX VEX components 必须是数组")
    else:
        refs.update(
            str(item["bom-ref"])
            for item in components
            if isinstance(item, dict) and item.get("bom-ref")
        )
    return issues, refs


def _vulnerability_issues(
    vulnerability: Any,
    refs: set[str],
    seen: set[tuple[str, str]],
) -> list[str]:
    if not isinstance(vulnerability, dict):
        return ["CycloneDX VEX vulnerability 必须是对象"]
    vuln = str(vulnerability.get("id") or "")
    issues: list[str] = []
    if not vuln:
        issues.append("CycloneDX VEX vulnerability 缺 id")
    affects = vulnerability.get("affects")
    if not isinstance(affects, list) or not affects:
        issues.append(f"CycloneDX VEX {vuln or '?'} 缺 affects")
        affects = []
    for affect in affects:
        ref = str(affect.get("ref") or "") if isinstance(affect, dict) else ""
        if ref not in refs:
            issues.append(f"CycloneDX VEX affects.ref 未指向已知组件：{ref!r}")
        key = (vuln, ref)
        if key in seen:
            issues.append(f"CycloneDX VEX 重复 vulnerability/product：{key!r}")
        seen.add(key)
    analysis = vulnerability.get("analysis")
    if not isinstance(analysis, dict):
        return issues + [f"CycloneDX VEX {vuln or '?'} 缺 analysis"]
    state = str(analysis.get("state") or "")
    if state not in set(CYCLONEDX_STATE.values()):
        issues.append(f"CycloneDX VEX analysis.state 非法：{state!r}")
    if state == "not_affected" and analysis.get("justification") not in set(
        JUSTIFICATION.values()
    ):
        issues.append(f"CycloneDX VEX {vuln or '?'} not_affected justification 非法")
    responses = analysis.get("response") or []
    if not isinstance(responses, list) or not all(
        isinstance(item, str) and item in CYCLONEDX_RESPONSES for item in responses
    ):
        issues.append(f"CycloneDX VEX {vuln or '?'} analysis.response 非法")
    return issues


def validate_cyclonedx_vex(doc: dict[str, Any]) -> list[str]:
    issues, refs = _metadata_issues(doc)
    vulnerabilities = doc.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        return issues + ["CycloneDX VEX vulnerabilities 必须是数组"]
    seen: set[tuple[str, str]] = set()
    for vulnerability in vulnerabilities:
        issues.extend(_vulnerability_issues(vulnerability, refs, seen))
    return issues


def _openvex_semantics(doc: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for statement in doc.get("statements") or []:
        vuln = str((statement.get("vulnerability") or {}).get("name") or "")
        for product in statement.get("products") or []:
            ref = str((product or {}).get("@id") or "")
            out[(vuln, ref)] = {
                "state": CYCLONEDX_STATE.get(str(statement.get("status") or ""), ""),
                "justification": JUSTIFICATION.get(
                    str(statement.get("justification") or ""), ""
                ),
                "detail": str(
                    statement.get("impact_statement")
                    or statement.get("action_statement")
                    or ""
                ),
            }
    return out


def _cyclonedx_semantics(
    doc: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for vulnerability in doc.get("vulnerabilities") or []:
        vuln = str(vulnerability.get("id") or "")
        analysis = vulnerability.get("analysis") or {}
        for affect in vulnerability.get("affects") or []:
            ref = str((affect or {}).get("ref") or "")
            out[(vuln, ref)] = {
                "state": str(analysis.get("state") or ""),
                "justification": str(analysis.get("justification") or ""),
                "detail": str(analysis.get("detail") or ""),
            }
    return out


def validate_vex_pair(openvex: dict[str, Any], cyclonedx: dict[str, Any]) -> list[str]:
    """Fail when the two VEX formats disagree on a vulnerability/product outcome."""
    issues = validate_vex(openvex) + validate_cyclonedx_vex(cyclonedx)
    left = _openvex_semantics(openvex)
    right = _cyclonedx_semantics(cyclonedx)
    if set(left) != set(right):
        issues.append(
            f"OpenVEX/CycloneDX 语义键集不一致：only-open={sorted(set(left) - set(right))} "
            f"only-cdx={sorted(set(right) - set(left))}"
        )
    for key in sorted(set(left) & set(right)):
        if left[key] != right[key]:
            issues.append(
                f"OpenVEX/CycloneDX 语义不一致 {key!r}: {left[key]!r} != {right[key]!r}"
            )
    return issues


def verify_release_artifacts(
    release: Path,
    product: str,
    source_root: Path,
) -> list[str]:
    issues: list[str] = []
    openvex_paths = sorted(release.glob("*.openvex.json"))
    cyclonedx_paths = sorted(release.glob("*.cdx-vex.json"))
    if len(openvex_paths) != 1:
        issues.append("发布目录缺 OpenVEX")
    if len(cyclonedx_paths) != 1:
        issues.append("发布目录缺 CycloneDX VEX")
    if len(openvex_paths) != 1 or len(cyclonedx_paths) != 1:
        return issues
    actual_openvex = _json(openvex_paths[0])
    actual_cyclonedx = _json(cyclonedx_paths[0])
    if actual_openvex != vex_doc(source_root, product):
        issues.append("发布束 OpenVEX 与处置台账不一致")
    if actual_cyclonedx != cyclonedx_vex_doc(source_root, product):
        issues.append("发布束 CycloneDX VEX 与处置台账不一致")
    issues.extend(validate_vex_pair(actual_openvex, actual_cyclonedx))
    return issues


def scan_files(root: Path) -> tuple[list[str], dict[str, Any]]:
    openvex = _json(root / OPENVEX_REL)
    cyclonedx = _json(root / CYCLONEDX_REL)
    issues = validate_vex_pair(openvex, cyclonedx)
    stats = {
        "statements": len(openvex.get("statements") or []),
        "vulnerabilities": len(cyclonedx.get("vulnerabilities") or []),
        "formats": ["openvex", "cyclonedx"],
    }
    return issues, stats
