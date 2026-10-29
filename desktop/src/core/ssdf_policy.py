"""Fail-closed validator for the task-level NIST SSDF v1.1 evidence matrix."""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core import json_doc

MATRIX_REL = Path("packaging/security/ssdf-800-218-v1.1.json")
ADVISORIES_REL = Path("results/supply-chain/vuln-disposition.json")
VEX_REL = Path("results/supply-chain/ninfenz.openvex.json")
SECURITY_REL = Path("SECURITY.md")
SCHEMA = "nf-ssdf-evidence/1"
VERSION = "1.1"
TASK_STATUSES = {"enforced", "external-manual", "not-applicable"}
FINDING_STATUSES = {"not_affected", "affected", "fixed", "under_investigation"}
SEVERITIES = {"critical", "high", "medium", "low"}
EXPLOITABILITY = {"reachable", "unreachable", "unknown"}
TABLE_URL = (
    "https://csrc.nist.gov/files/pubs/sp/800/218/final/docs/"
    "nist.sp.800-218.ssdf-table.xlsx"
)
TABLE_SHA256 = "f5729c4c6c792cbf6cfbea74eee7cc84c579b2109006fe3cbfa8934eb460bd55"
EXPECTED_PRACTICES = {
    "PO.1": "Define Security Requirements for Software Development",
    "PO.2": "Implement Roles and Responsibilities",
    "PO.3": "Implement Supporting Toolchains",
    "PO.4": "Define and Use Criteria for Software Security Checks",
    "PO.5": "Implement and Maintain Secure Environments for Software Development",
    "PS.1": "Protect All Forms of Code from Unauthorized Access and Tampering",
    "PS.2": "Provide a Mechanism for Verifying Software Release Integrity",
    "PS.3": "Archive and Protect Each Software Release",
    "PW.1": "Design Software to Meet Security Requirements and Mitigate Security Risks",
    "PW.2": (
        "Review the Software Design to Verify Compliance with Security Requirements "
        "and Risk Information"
    ),
    "PW.4": (
        "Reuse Existing, Well-Secured Software When Feasible Instead of "
        "Duplicating Functionality"
    ),
    "PW.5": "Create Source Code by Adhering to Secure Coding Practices",
    "PW.6": (
        "Configure the Compilation, Interpreter, and Build Processes to Improve "
        "Executable Security"
    ),
    "PW.7": (
        "Review and/or Analyze Human-Readable Code to Identify Vulnerabilities and "
        "Verify Compliance with Security Requirements"
    ),
    "PW.8": (
        "Test Executable Code to Identify Vulnerabilities and Verify Compliance with "
        "Security Requirements"
    ),
    "PW.9": "Configure Software to Have Secure Settings by Default",
    "RV.1": "Identify and Confirm Vulnerabilities on an Ongoing Basis",
    "RV.2": "Assess, Prioritize, and Remediate Vulnerabilities",
    "RV.3": "Analyze Vulnerabilities to Identify Their Root Causes",
}
EXPECTED_TASKS = {
    "PO.1.1": (
        "Identify and document all security requirements for the organization's software "
        "development infrastructures and processes, and maintain the requirements over time."
    ),
    "PO.1.2": (
        "Identify and document all security requirements for organization-developed software "
        "to meet, and maintain the requirements over time."
    ),
    "PO.1.3": (
        "Communicate requirements to all third parties who will provide commercial software "
        "components to the organization for reuse by the organization's own software."
    ),
    "PO.2.1": (
        "Create new roles and alter responsibilities for existing roles as needed to encompass "
        "all parts of the SDLC. Periodically review and maintain the defined roles and "
        "responsibilities, updating them as needed."
    ),
    "PO.2.2": (
        "Provide role-based training for all personnel with responsibilities that contribute to "
        "secure development. Periodically review personnel proficiency and role-based training, "
        "and update the training as needed."
    ),
    "PO.2.3": (
        "Obtain upper management or authorizing official commitment to secure development, and "
        "convey that commitment to all with development-related roles and responsibilities."
    ),
    "PO.3.1": (
        "Specify which tools or tool types must or should be included in each toolchain to "
        "mitigate identified risks, as well as how the toolchain components are to be "
        "integrated with each other."
    ),
    "PO.3.2": (
        "Follow recommended security practices to deploy, operate, and maintain tools and "
        "toolchains."
    ),
    "PO.3.3": (
        "Configure tools to generate artifacts of their support of secure software development "
        "practices as defined by the organization."
    ),
    "PO.4.1": "Define criteria for software security checks and track throughout the SDLC.",
    "PO.4.2": (
        "Implement processes, mechanisms, etc. to gather and safeguard the necessary "
        "information in support of the criteria."
    ),
    "PO.5.1": "Separate and protect each environment involved in software development.",
    "PO.5.2": (
        "Secure and harden development endpoints (i.e., endpoints for software designers, "
        "developers, testers, builders, etc.) to perform development-related tasks using a "
        "risk-based approach."
    ),
    "PS.1.1": (
        "Store all forms of code - including source code, executable code, and "
        "configuration-as-code - based on the principle of least privilege so that only "
        "authorized personnel, tools, services, etc. have access."
    ),
    "PS.2.1": "Make software integrity verification information available to software acquirers.",
    "PS.3.1": (
        "Securely archive the necessary files and supporting data (e.g., integrity verification "
        "information, provenance data) to be retained for each software release."
    ),
    "PS.3.2": (
        "Collect, safeguard, maintain, and share provenance data for all components of each "
        "software release (e.g., in a software bill of materials [SBOM])."
    ),
    "PW.1.1": (
        "Use forms of risk modeling - such as threat modeling, attack modeling, or attack "
        "surface mapping - to help assess the security risk for the software."
    ),
    "PW.1.2": (
        "Track and maintain the software's security requirements, risks, and "
        "design decisions."
    ),
    "PW.1.3": (
        "Where appropriate, build in support for using standardized security features and "
        "services (e.g., enabling software to integrate with existing log management, identity "
        "management, access control, and vulnerability management systems) instead of creating "
        "proprietary implementations of security features and services."
    ),
    "PW.2.1": (
        "Have 1) a qualified person (or people) who were not involved with the design and/or "
        "2) automated processes instantiated in the toolchain review the software design to "
        "confirm and enforce that it meets all of the security requirements and satisfactorily "
        "addresses the identified risk information."
    ),
    "PW.4.1": (
        "Acquire and maintain well-secured software components (e.g., software libraries, "
        "modules, middleware, frameworks) from commercial, open-source, and other third-party "
        "developers for use by the organization's software."
    ),
    "PW.4.2": (
        "Create and maintain well-secured software components in-house following SDLC processes "
        "to meet common internal software development needs that cannot be better met by "
        "third-party software components."
    ),
    "PW.4.4": (
        "Verify that acquired commercial, open-source, and all other third-party software "
        "components comply with the requirements, as defined by the organization, throughout "
        "their life cycles."
    ),
    "PW.5.1": (
        "Follow all secure coding practices that are appropriate to the development languages "
        "and environment to meet the organization's requirements."
    ),
    "PW.6.1": (
        "Use compiler, interpreter, and build tools that offer features to improve executable "
        "security."
    ),
    "PW.6.2": (
        "Determine which compiler, interpreter, and build tool features should be used and how "
        "each should be configured, then implement and use the approved configurations."
    ),
    "PW.7.1": (
        "Determine whether code review (a person looks directly at the code to find issues) "
        "and/or code analysis (tools are used to find issues in code, either in a fully automated "
        "way or in conjunction with a person) should be used, as defined by the organization."
    ),
    "PW.7.2": (
        "Perform the code review and/or code analysis based on the organization's secure coding "
        "standards, and record and triage all discovered issues and recommended remediations in "
        "the development team's workflow or issue tracking system."
    ),
    "PW.8.1": (
        "Determine whether executable code testing should be performed to find vulnerabilities "
        "not identified by previous reviews, analysis, or testing and, if so, which types of "
        "testing should be used."
    ),
    "PW.8.2": (
        "Scope the testing, design the tests, perform the testing, and document the results, "
        "including recording and triaging all discovered issues and recommended remediations in "
        "the development team's workflow or issue tracking system."
    ),
    "PW.9.1": (
        "Define a secure baseline by determining how to configure each setting that has an "
        "effect on security or a security-related setting so that the default settings are "
        "secure and do not weaken the security functions provided by the platform, network "
        "infrastructure, or services."
    ),
    "PW.9.2": (
        "Implement the default settings (or groups of default settings, if applicable), and "
        "document each setting for software administrators."
    ),
    "RV.1.1": (
        "Gather information from software acquirers, users, and public sources on potential "
        "vulnerabilities in the software and third-party components that the software uses, "
        "and investigate all credible reports."
    ),
    "RV.1.2": (
        "Review, analyze, and/or test the software's code to identify or confirm the presence "
        "of previously undetected vulnerabilities."
    ),
    "RV.1.3": (
        "Have a policy that addresses vulnerability disclosure and remediation, and implement "
        "the roles, responsibilities, and processes needed to support that policy."
    ),
    "RV.2.1": (
        "Analyze each vulnerability to gather sufficient information about risk to plan its "
        "remediation or other risk response."
    ),
    "RV.2.2": "Plan and implement risk responses for vulnerabilities.",
    "RV.3.1": "Analyze identified vulnerabilities to determine their root causes.",
    "RV.3.2": (
        "Analyze the root causes over time to identify patterns, such as a particular secure "
        "coding practice not being followed consistently."
    ),
    "RV.3.3": (
        "Review the software for similar vulnerabilities to eradicate a class of vulnerabilities, "
        "and proactively fix them rather than waiting for external reports."
    ),
    "RV.3.4": (
        "Review the SDLC process, and update it if appropriate to prevent (or reduce the "
        "likelihood of) the root cause recurring in updates to the software or in new software "
        "that is created."
    ),
}
SLA_LIMITS = {"critical": 1, "high": 7, "medium": 30, "low": 90}


def _natural(ident: str) -> tuple[str, int]:
    prefix, suffix = ident.split(".", 1)
    return prefix, int(suffix)


def _natural_task(ident: str) -> tuple[str, int, int]:
    practice, task = ident.rsplit(".", 1)
    prefix, number = practice.split(".", 1)
    return prefix, int(number), int(task)


def _evidence_issues(root: Path, label: str, values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return [f"{label}: evidence must be a non-empty list"]
    issues: list[str] = []
    for value in values:
        text = str(value)
        if text.startswith("external:"):
            if len(text) == len("external:"):
                issues.append(f"{label}: external evidence needs an identifier")
        elif not (root / text).exists():
            issues.append(f"{label}: evidence path missing: {text}")
    return issues


def _matrix_header_issues(doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if doc.get("schema") != SCHEMA:
        issues.append(f"{MATRIX_REL}: schema must be {SCHEMA}")
    standard = doc.get("standard") if isinstance(doc.get("standard"), dict) else {}
    if standard.get("version") != VERSION:
        issues.append(f"{MATRIX_REL}: SSDF version must be {VERSION}")
    if standard.get("document") != "NIST SP 800-218":
        issues.append(f"{MATRIX_REL}: standard document must be NIST SP 800-218")
    if not str(standard.get("source") or "").startswith("https://csrc.nist.gov/"):
        issues.append(f"{MATRIX_REL}: source must be the official NIST HTTPS page")
    if standard.get("table_source") != TABLE_URL:
        issues.append(f"{MATRIX_REL}: table_source must be the official NIST SSDF table")
    if str(standard.get("table_sha256") or "").lower() != TABLE_SHA256:
        issues.append(f"{MATRIX_REL}: table_sha256 must match the reviewed NIST table")
    try:
        reviewed = date.fromisoformat(str(standard.get("reviewed_at") or ""))
        if reviewed > date.today():
            issues.append(f"{MATRIX_REL}: reviewed_at cannot be in the future")
    except ValueError:
        issues.append(f"{MATRIX_REL}: reviewed_at must be YYYY-MM-DD")
    claim = doc.get("claim") if isinstance(doc.get("claim"), dict) else {}
    if claim.get("certified") is not False:
        issues.append(f"{MATRIX_REL}: must not claim third-party certification")
    return issues


def _task_issues(
    root: Path, practice_id: str, tasks: list[Any]
) -> tuple[list[str], list[str], list[str]]:
    issues: list[str] = []
    task_ids: list[str] = []
    statuses: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            issues.append(f"{MATRIX_REL}/{practice_id}: task entries must be objects")
            continue
        task_id = str(task.get("id") or "")
        task_ids.append(task_id)
        task_title = str(task.get("title") or "")
        if task_id in EXPECTED_TASKS and task_title != EXPECTED_TASKS[task_id]:
            issues.append(f"{MATRIX_REL}/{task_id}: title does not match the official task")
        if not task_id.startswith(practice_id + "."):
            issues.append(f"{MATRIX_REL}/{task_id}: task is under the wrong practice")
        status = str(task.get("status") or "")
        statuses.append(status)
        if status not in TASK_STATUSES:
            issues.append(f"{MATRIX_REL}/{task_id}: invalid status {status!r}")
        if status == "partial":
            issues.append(f"{MATRIX_REL}/{task_id}: partial SSDF task is forbidden")
        if not str(task.get("verification") or "").strip():
            issues.append(f"{MATRIX_REL}/{task_id}: verification is required")
        if status in {"external-manual", "not-applicable"} and not str(
                task.get("gap") or "").strip():
            issues.append(f"{MATRIX_REL}/{task_id}: {status} requires gap")
        issues.extend(_evidence_issues(
            root, f"{MATRIX_REL}/{task_id}", task.get("evidence")
        ))
    if len(task_ids) != len(set(task_ids)):
        issues.append(f"{MATRIX_REL}/{practice_id}: duplicate task IDs")
    expected = {
        task for task in EXPECTED_TASKS if task.startswith(practice_id + ".")
    }
    if sorted(expected - set(task_ids), key=_natural_task):
        issues.append(f"{MATRIX_REL}/{practice_id}: missing tasks")
    if sorted(set(task_ids) - expected, key=_natural_task):
        issues.append(f"{MATRIX_REL}/{practice_id}: unknown tasks")
    return issues, task_ids, statuses


def _derived_practice_status(statuses: list[str]) -> str:
    if "external-manual" in statuses:
        return "external-manual"
    if statuses and all(status == "not-applicable" for status in statuses):
        return "not-applicable"
    return "enforced"


def _practice_row_issues(
    root: Path,
    row: Any,
    counts: Counter[str],
    task_counts: Counter[str],
    all_task_ids: list[str],
) -> list[str]:
    if not isinstance(row, dict):
        return [f"{MATRIX_REL}: practice entries must be objects"]
    issues: list[str] = []
    ident = str(row.get("id") or "?")
    title = str(row.get("title") or "")
    if ident in EXPECTED_PRACTICES and title != EXPECTED_PRACTICES[ident]:
        issues.append(f"{MATRIX_REL}/{ident}: title does not match the official practice")
    tasks = row.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return issues + [f"{MATRIX_REL}/{ident}: tasks must be a non-empty list"]
    task_issues, task_ids, statuses = _task_issues(root, ident, tasks)
    issues.extend(task_issues)
    all_task_ids.extend(task_ids)
    task_counts.update(statuses)
    derived = _derived_practice_status(statuses)
    counts[derived] += 1
    declared = str(row.get("status") or "")
    if declared != derived:
        issues.append(
            f"{MATRIX_REL}/{ident}: practice status {declared!r} must be derived "
            f"as {derived!r}"
        )
    return issues


def _practice_issues(
    root: Path, rows: list[Any]
) -> tuple[list[str], Counter[str], Counter[str], int]:
    issues: list[str] = []
    ids = [str(row.get("id")) for row in rows if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        issues.append(f"{MATRIX_REL}: duplicate practice IDs")
    missing = sorted(set(EXPECTED_PRACTICES) - set(ids), key=_natural)
    extra = sorted(set(ids) - set(EXPECTED_PRACTICES), key=_natural)
    if missing:
        issues.append(f"{MATRIX_REL}: missing SSDF practices: {missing}")
    if extra:
        issues.append(f"{MATRIX_REL}: unknown SSDF practices: {extra}")
    counts: Counter[str] = Counter()
    task_counts: Counter[str] = Counter()
    task_ids: list[str] = []
    for row in rows:
        issues.extend(_practice_row_issues(root, row, counts, task_counts, task_ids))
    missing_tasks = sorted(set(EXPECTED_TASKS) - set(task_ids), key=_natural_task)
    extra_tasks = sorted(set(task_ids) - set(EXPECTED_TASKS), key=_natural_task)
    if missing_tasks:
        issues.append(f"{MATRIX_REL}: missing SSDF tasks: {missing_tasks}")
    if extra_tasks:
        issues.append(f"{MATRIX_REL}: unknown SSDF tasks: {extra_tasks}")
    if task_counts.get("partial"):
        issues.append(f"{MATRIX_REL}: partial SSDF task baseline regressed")
    return issues, counts, task_counts, len(task_ids)


def _matrix(root: Path) -> tuple[list[str], dict[str, Any]]:
    try:
        doc = json_doc.load(root / MATRIX_REL, dict, what=str(MATRIX_REL))
    except (OSError, ValueError) as exc:
        return [f"{MATRIX_REL}: unreadable or invalid: {exc}"], {}
    issues = _matrix_header_issues(doc)
    rows = doc.get("practices")
    if not isinstance(rows, list):
        return issues + [f"{MATRIX_REL}: practices must be a list"], {}
    practice_issues, counts, task_counts, task_total = _practice_issues(root, rows)
    issues.extend(practice_issues)
    return issues, {
        "practices": len(rows),
        "tasks": task_total,
        "statuses": dict(sorted(counts.items())),
        "task_statuses": dict(sorted(task_counts.items())),
    }


def _finding_shape_issues(
    root: Path, finding: dict[str, Any], seen: set[str]
) -> tuple[list[str], str, str, str, str]:
    issues: list[str] = []
    ident = str(finding.get("id") or "")
    vuln = str(finding.get("vulnerability") or "")
    status = str(finding.get("status") or "")
    severity = str(finding.get("severity") or "")
    if not ident or ident in seen:
        issues.append(f"{ADVISORIES_REL}: finding ID missing or duplicate: {ident!r}")
    seen.add(ident)
    if not vuln:
        issues.append(f"{ADVISORIES_REL}/{ident}: vulnerability is required")
    if not str(finding.get("source") or "").strip():
        issues.append(f"{ADVISORIES_REL}/{ident}: source is required")
    if status not in FINDING_STATUSES:
        issues.append(f"{ADVISORIES_REL}/{ident}: invalid status {status!r}")
    if severity not in SEVERITIES:
        issues.append(f"{ADVISORIES_REL}/{ident}: invalid severity {severity!r}")
    if str(finding.get("exploitability") or "") not in EXPLOITABILITY:
        issues.append(f"{ADVISORIES_REL}/{ident}: exploitability is required and must be known")
    if not str(finding.get("impact") or "").strip():
        issues.append(f"{ADVISORIES_REL}/{ident}: impact is required")
    if not finding.get("affected_versions"):
        issues.append(f"{ADVISORIES_REL}/{ident}: affected_versions is required")
    try:
        discovered = date.fromisoformat(str(finding.get("discovered_at") or ""))
        if discovered > date.today():
            issues.append(f"{ADVISORIES_REL}/{ident}: discovered_at cannot be in the future")
    except ValueError:
        issues.append(f"{ADVISORIES_REL}/{ident}: discovered_at must be YYYY-MM-DD")
    disclosure = urlparse(str(finding.get("disclosure_url") or ""))
    if disclosure.scheme != "https" or not disclosure.hostname:
        issues.append(f"{ADVISORIES_REL}/{ident}: disclosure_url must be HTTPS")
    issues.extend(_evidence_issues(
        root, f"{ADVISORIES_REL}/{ident}", finding.get("evidence")
    ))
    return issues, ident, vuln, status, severity


def _finding_disposition_issues(
    root: Path,
    ident: str,
    vuln: str,
    status: str,
    finding: dict[str, Any],
    vex_by_vuln: set[str],
) -> tuple[list[str], int]:
    issues: list[str] = []
    unresolved = 0
    if status in {"affected", "under_investigation"}:
        unresolved = 1
        issues.append(f"{ADVISORIES_REL}/{ident}: unresolved advisory blocks release")
        if not str(finding.get("action") or "").strip():
            issues.append(f"{ADVISORIES_REL}/{ident}: unresolved findings require action")
    if status == "fixed":
        for key in ("fixed_in", "root_cause", "related_review"):
            if not str(finding.get(key) or "").strip():
                issues.append(f"{ADVISORIES_REL}/{ident}: fixed requires {key}")
        regression_tests = finding.get("regression_tests")
        if not isinstance(regression_tests, list) or not regression_tests:
            issues.append(f"{ADVISORIES_REL}/{ident}: fixed requires regression_tests")
        else:
            for rel in regression_tests:
                if not (root / str(rel)).is_file():
                    issues.append(
                        f"{ADVISORIES_REL}/{ident}: regression test missing: {rel}"
                    )
        if vuln not in vex_by_vuln:
            issues.append(f"{ADVISORIES_REL}/{ident}: matching VEX statement is required")
    if status == "not_affected":
        for key in ("justification", "impact_statement"):
            if not str(finding.get(key) or "").strip():
                issues.append(f"{ADVISORIES_REL}/{ident}: not_affected requires {key}")
        if vuln not in vex_by_vuln:
            issues.append(f"{ADVISORIES_REL}/{ident}: matching VEX statement is required")
    return issues, unresolved


def _finding_issues(
    root: Path, findings: list[Any], vex_by_vuln: set[str]
) -> tuple[list[str], int]:
    issues: list[str] = []
    unresolved = 0
    seen: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            issues.append(f"{ADVISORIES_REL}: findings must be objects")
            continue
        shape, ident, vuln, status, _severity = _finding_shape_issues(root, finding, seen)
        disposition, is_unresolved = _finding_disposition_issues(
            root, ident, vuln, status, finding, vex_by_vuln
        )
        issues.extend(shape)
        issues.extend(disposition)
        unresolved += is_unresolved
    return issues, unresolved


def _ledger_header_issues(ledger: dict[str, Any]) -> tuple[list[str], Any]:
    issues: list[str] = []
    if ledger.get("schema") != "nf-vuln-disposition/1":
        issues.append(f"{ADVISORIES_REL}: schema must be nf-vuln-disposition/1")
    try:
        reviewed = date.fromisoformat(str(ledger.get("reviewed_at") or ""))
        if reviewed > date.today():
            issues.append(f"{ADVISORIES_REL}: reviewed_at cannot be in the future")
    except ValueError:
        issues.append(f"{ADVISORIES_REL}: reviewed_at must be YYYY-MM-DD")
    claims_none = ledger.get("claims_no_vulnerabilities")
    if claims_none is not False:
        issues.append(f"{ADVISORIES_REL}: must not claim that no vulnerabilities exist")
    channels = ledger.get("intake_channels")
    if not isinstance(channels, list) or len(channels) < 4:
        issues.append(f"{ADVISORIES_REL}: at least four vulnerability intake channels are required")
    sla = ledger.get("severity_sla_days")
    if not isinstance(sla, dict):
        issues.append(f"{ADVISORIES_REL}: severity_sla_days is required")
        sla = {}
    for severity, limit in SLA_LIMITS.items():
        value = sla.get(severity)
        if not isinstance(value, int) or value < 1 or value > limit:
            issues.append(
                f"{ADVISORIES_REL}: {severity} SLA must be 1-{limit} days"
            )
    return issues, claims_none


def _root_cause_review_issues(root: Path, review: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(review, dict):
        issues.append(f"{ADVISORIES_REL}: root_cause_review is required")
        review = {}
    try:
        reviewed = date.fromisoformat(str(review.get("reviewed_at") or ""))
        if reviewed > date.today():
            issues.append(f"{ADVISORIES_REL}: root_cause_review is dated in the future")
    except ValueError:
        issues.append(f"{ADVISORIES_REL}: root_cause_review.reviewed_at must be YYYY-MM-DD")
    for key in ("cadence", "statement"):
        if not str(review.get(key) or "").strip():
            issues.append(f"{ADVISORIES_REL}: root_cause_review requires {key}")
    for key in ("patterns", "sdlc_actions", "regression_tests"):
        values = review.get(key)
        if not isinstance(values, list):
            issues.append(f"{ADVISORIES_REL}: root_cause_review.{key} must be a list")
            continue
        if key == "regression_tests":
            for rel in values:
                if not (root / str(rel)).is_file():
                    issues.append(
                        f"{ADVISORIES_REL}: root-cause regression test missing: {rel}"
                    )
    return issues


def _vex_issues(vex: dict[str, Any]) -> tuple[list[str], list[Any], set[str]]:
    issues: list[str] = []
    vex_statements = vex.get("statements")
    if not isinstance(vex_statements, list):
        issues.append(f"{VEX_REL}: statements must be a list")
        vex_statements = []
    vex_by_vuln = {
        str((row.get("vulnerability") or {}).get("name") if isinstance(row, dict) else "")
        for row in vex_statements
        if isinstance(row, dict)
    }
    return issues, vex_statements, vex_by_vuln


def _advisories(root: Path) -> tuple[list[str], dict[str, Any]]:
    try:
        ledger = json_doc.load(root / ADVISORIES_REL, dict, what=str(ADVISORIES_REL))
        vex = json_doc.load(root / VEX_REL, dict, what=str(VEX_REL))
    except (OSError, ValueError) as exc:
        return [f"vulnerability response evidence unreadable: {exc}"], {}
    issues, claims_none = _ledger_header_issues(ledger)
    findings = ledger.get("findings")
    if not isinstance(findings, list):
        return issues + [f"{ADVISORIES_REL}: findings must be a list"], {}
    review = ledger.get("root_cause_review")
    issues.extend(_root_cause_review_issues(root, review))
    vex_issues, vex_statements, vex_by_vuln = _vex_issues(vex)
    issues.extend(vex_issues)
    finding_issues, unresolved = _finding_issues(root, findings, vex_by_vuln)
    issues.extend(finding_issues)
    return issues, {
        "findings": len(findings),
        "unresolved": unresolved,
        "claims_no_vulnerabilities": claims_none,
        "vex_statements": len(vex_statements),
        "root_cause_reviewed_at": (
            review.get("reviewed_at") if isinstance(review, dict) else None
        ),
    }


def _security_policy(root: Path) -> list[str]:
    try:
        text = (root / SECURITY_REL).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{SECURITY_REL}: unreadable: {exc}"]
    issues: list[str] = []
    if "GitHub Security Advisories" not in text:
        issues.append(f"{SECURITY_REL}: vulnerability intake channel is missing")
    if "响应 SLA" not in text:
        issues.append(f"{SECURITY_REL}: severity response SLA is missing")
    for severity in ("Critical", "High", "Medium", "Low"):
        if severity not in text:
            issues.append(f"{SECURITY_REL}: severity policy missing {severity}")
    return issues


def scan(root: str | Path = ".") -> tuple[list[str], dict[str, Any]]:
    base = Path(root)
    matrix_issues, matrix_stats = _matrix(base)
    advisory_issues, advisory_stats = _advisories(base)
    security_issues = _security_policy(base)
    issues = matrix_issues + advisory_issues + security_issues
    return issues, {
        "practices": matrix_stats.get("practices", 0),
        "tasks": matrix_stats.get("tasks", 0),
        "statuses": matrix_stats.get("statuses", {}),
        "task_statuses": matrix_stats.get("task_statuses", {}),
        "advisories": advisory_stats,
        "certified": False,
    }


__all__ = [
    "ADVISORIES_REL",
    "EXPECTED_PRACTICES",
    "EXPECTED_TASKS",
    "MATRIX_REL",
    "SCHEMA",
    "SECURITY_REL",
    "TABLE_SHA256",
    "TABLE_URL",
    "VEX_REL",
    "scan",
]
