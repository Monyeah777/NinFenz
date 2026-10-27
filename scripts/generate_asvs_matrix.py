#!/usr/bin/env python3
"""Generate the scoped OWASP ASVS 5.0.0 Level 2 evidence matrix."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import atomic_write, json_doc  # noqa: E402

COMMIT = "5cf9b032440be53ce345ab3c130fda46ba1ce7a2"
SOURCE = (
    "https://raw.githubusercontent.com/OWASP/ASVS/"
    f"{COMMIT}/5.0/docs_en/"
    "OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json"
)
OUT = ROOT / "packaging" / "security" / "asvs-5.0.0-l2.json"
SCOPE = {
    "V1", "V2", "V4", "V5", "V6", "V7", "V8",
    "V11", "V12", "V13", "V14", "V15", "V16",
}
EXCLUDED = {
    "V3": "No browser frontend is shipped by the scoped runtime.",
    "V9": "The project does not issue self-contained user tokens.",
    "V10": "The project does not implement an OAuth or OIDC provider/client runtime.",
    "V17": "The project has no WebRTC surface.",
}
PARTIAL_EVIDENCE = [
    "desktop/src/core/daemon.py",
    "desktop/src/core/mcp_runtime.py",
    "scripts/plugin_host.py",
    "docs/asvs.md",
]
PARTIAL_GAP = "Applicable, but a dedicated end-to-end ASVS verification is not yet complete."

ENFORCED: dict[str, tuple[str, list[str]]] = {}


def _enforce(ids: list[str], verification: str, evidence: list[str]) -> None:
    for ident in ids:
        ENFORCED[ident] = (verification, evidence)


_enforce(
    ["V1.2.3", "V1.2.5", "V1.3.6", "V1.4.1", "V1.5.2"],
    "Strict JSON parsing, argv-only subprocess calls, no runtime network capability, "
    "memory-safe Python/Rust components, and non-evaluating data formats are enforced.",
    [
        "desktop/src/core/json_doc.py",
        "desktop/src/core/mcp_runtime.py",
        "scripts/plugin_host.py",
        "desktop/tests/test_mcp_runtime.py",
        "desktop/tests/test_plugin_wasm_host.py",
    ],
)
_enforce(
    ["V2.2.1", "V2.2.2", "V2.3.2", "V2.3.4"],
    "Schema admission, protocol bounds, trusted in-process validation, and atomic "
    "read-modify-write locking enforce validation at the service layer.",
    [
        "desktop/src/core/trust_boundary.py",
        "desktop/src/core/json_schema.py",
        "desktop/src/core/atomic_write.py",
        "desktop/tests/test_atomic_write.py",
    ],
)
_enforce(
    ["V5.2.1", "V5.3.2"],
    "All protocol, plugin, and snapshot input paths have byte limits; repository file "
    "paths are lexical- and realpath-contained.",
    [
        "desktop/src/core/paths.py",
        "desktop/src/core/mcp_runtime.py",
        "scripts/plugin_host.py",
        "desktop/tests/test_paths.py",
        "desktop/tests/test_daemon_limits.py",
    ],
)
_enforce(
    ["V7.1.1", "V7.1.2", "V7.2.1", "V7.2.2", "V7.2.3", "V7.3.1", "V7.3.2",
     "V7.4.1", "V7.6.2"],
    "One daemon is allowed per NF home; each process uses a fresh 256-bit CSPRNG "
    "token, verifies it locally in constant time, has idle and absolute lifetimes, "
    "and invalidates the session on shutdown.",
    [
        "desktop/src/core/daemon.py",
        "desktop/tests/test_daemon.py",
        "desktop/tests/test_daemon_limits.py",
        "docs/asvs.md",
    ],
)
_enforce(
    ["V8.2.1", "V8.3.1"],
    "Daemon command execution requires the process-scoped token; MCP exposes only "
    "an explicit read-only tool and resource allowlist.",
    [
        "desktop/src/core/daemon.py",
        "desktop/src/core/mcp_runtime.py",
        "desktop/tests/test_daemon.py",
        "desktop/tests/test_mcp_runtime.py",
    ],
)
_enforce(
    ["V11.2.1", "V11.2.3", "V11.4.1", "V11.4.3", "V11.5.1"],
    "Authentication tokens use secrets.token_hex(32), integrity checks use SHA-256, "
    "and token comparison uses hmac.compare_digest.",
    [
        "desktop/src/core/daemon.py",
        "desktop/src/core/atoms/hash.py",
        "desktop/tests/test_daemon.py",
    ],
)
_enforce(
    ["V13.2.1", "V13.2.3", "V13.4.1"],
    "IPC is loopback-only with a per-process token; no default credential exists; "
    "release payload allowlists exclude VCS metadata and development outputs.",
    [
        "desktop/src/core/daemon.py",
        "packaging/npm/tools/build_release.py",
        "packaging/npm/tools/verify-package.mjs",
        "desktop/tests/test_daemon.py",
    ],
)
_enforce(
    ["V14.2.3"],
    "Runtime code contains no analytics or tracker dependency, and MCP advertises "
    "openWorldHint=false for every tool.",
    [
        "desktop/src/core/mcp_runtime.py",
        "desktop/tests/test_mcp_runtime.py",
        "packaging/supply-chain/package-sources.json",
    ],
)
_enforce(
    ["V15.1.1", "V15.1.2", "V15.2.2", "V15.3.3"],
    "Remediation thresholds, SBOM/supplier inventories, bounded memory/CPU controls, "
    "and closed input schemas are machine-verified.",
    [
        "SECURITY.md",
        "packaging/supply-chain/suppliers.json",
        "desktop/src/core/daemon.py",
        "desktop/src/core/mcp_runtime.py",
        "scripts/plugin_host.py",
        "desktop/tests/test_supply_chain_standards.py",
    ],
)
_enforce(
    ["V16.1.1", "V16.2.1", "V16.2.2", "V16.2.3", "V16.2.4",
     "V16.2.5", "V16.3.1", "V16.3.2", "V16.3.3",
     "V16.3.4", "V16.4.1", "V16.5.1", "V16.5.2", "V16.5.3"],
    "Security events use UTC timestamps and structured metadata; auth, authorization, "
    "bypass, and unexpected-error paths are logged with single-line escaping and "
    "credential redaction while clients receive generic errors.",
    [
        "desktop/src/core/plog.py",
        "desktop/src/core/daemon.py",
        "desktop/tests/test_security_logging.py",
        "desktop/tests/test_daemon.py",
        "desktop/tests/test_mcp_runtime.py",
    ],
)

NA_BY_CHAPTER = {
    "V4": "The scoped runtime exposes no HTTP, GraphQL, or WebSocket service.",
    "V6": "The project has no human account, password, MFA, or federated login flow; "
          "the local daemon token is assessed under V7 and V8.",
    "V12": "The scoped runtime has no remote network listener; loopback daemon traffic "
           "is protected by process-scoped authorization rather than TLS.",
}
NA_IDS = {
    "V1.2.1": "No HTML, HTTP, or XML response generator is in scope.",
    "V1.2.4": "No SQL, NoSQL, or database query engine is used.",
    "V1.2.6": "No LDAP integration exists.",
    "V1.2.7": "No XPath query engine exists.",
    "V1.2.8": "No LaTeX shell-enabled processor is in scope.",
    "V1.3.1": "No WYSIWYG HTML ingestion exists.",
    "V1.3.4": "No user-supplied SVG renderer exists.",
    "V1.3.7": "No server-side template engine is in scope.",
    "V1.3.8": "No JNDI integration exists.",
    "V1.3.9": "No memcache integration exists.",
    "V1.3.11": "No mail-system integration exists.",
    "V1.4.3": "Managed Python and Rust code contain no manual pointer lifetime.",
    "V2.3.1": "There is no multi-step user authentication or account business flow.",
    "V2.4.1": "The CLI and MCP transport are local single-user surfaces, not a remote "
              "multi-user service; request-size and compute caps remain enforced.",
    "V5.3.1": "No public web-serving directory executes stored files.",
    "V5.4.1": "No HTTP Content-Disposition file response exists.",
    "V5.4.2": "No HTTP or email attachment filename response exists.",
    "V5.4.3": "The runtime does not serve files obtained from remote uploads.",
    "V7.1.3": "No federated identity system exists.",
    "V7.2.4": "There is no interactive user authentication/reahentication step.",
    "V7.4.2": "There are no user accounts to disable or delete.",
    "V7.4.3": "There are no user authentication factors to change.",
    "V7.4.4": "There is no authenticated web page or logout UI.",
    "V7.4.5": "There is no user-session administration console.",
    "V7.5.1": "There are no account attributes or authentication factors.",
    "V7.5.2": "There is no user-facing session inventory UI.",
    "V7.6.1": "No relying-party or identity-provider federation exists.",
    "V8.1.2": "No field-level multi-user data authorization surface exists.",
    "V8.2.2": "No multi-user object store or IDOR/BOLA surface exists.",
    "V8.2.3": "No multi-user property-level authorization surface exists.",
    "V8.4.1": "The application is not multi-tenant.",
    "V11.3.1": "No block cipher or padding scheme is used.",
    "V11.3.2": "No encryption cipher is used in the runtime; SHA-256 is used for "
                "integrity and HMAC comparison for token equality.",
    "V11.3.3": "The application does not encrypt local user content.",
    "V11.4.2": "No passwords are stored or verified.",
    "V11.4.4": "No password-derived key material exists.",
    "V13.2.5": "The application is not a web/application server.",
    "V13.4.3": "The application does not serve directory listings.",
    "V13.4.4": "The application has no HTTP method surface.",
    "V13.4.5": "The application exposes no HTTP API documentation or monitoring endpoint.",
    "V14.2.1": "No HTTP URLs or query strings carry sensitive data.",
    "V14.2.2": "There is no server-side HTTP cache.",
    "V14.3.1": "There is no browser DOM or browser session.",
    "V14.3.2": "There is no browser HTTP cache.",
    "V14.3.3": "There is no browser storage.",
    "V15.3.2": "No backend HTTP redirect client exists in the runtime.",
    "V15.3.4": "No HTTP proxy or middleware IP forwarding exists.",
    "V15.3.6": "There is no JavaScript runtime in the scoped application.",
    "V15.3.7": "There is no HTTP parameter parser in the scoped application.",
}


def _natural(ident: str) -> tuple[int, ...]:
    return tuple(int(part) for part in ident.removeprefix("V").split("."))


def _assessment(ident: str, chapter: str) -> tuple[str, str, str, list[str]]:
    if chapter in NA_BY_CHAPTER:
        return (
            "not-applicable",
            NA_BY_CHAPTER[chapter],
            "The scoped threat surface does not implement this chapter.",
            ["docs/asvs.md"],
        )
    if ident in NA_IDS:
        return (
            "not-applicable",
            NA_IDS[ident],
            "Applicability review found no corresponding runtime surface.",
            ["docs/asvs.md"],
        )
    if ident in ENFORCED:
        verification, evidence = ENFORCED[ident]
        return "enforced", "", verification, evidence
    return (
        "partial",
        PARTIAL_GAP,
        "The control has partial repository evidence.",
        PARTIAL_EVIDENCE,
    )


def generate() -> dict[str, Any]:
    # Fixed HTTPS upstream at the pinned ASVS commit; this generator is never run by CI.
    parsed = urlsplit(SOURCE)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError(
            "ASVS source must use the pinned raw.githubusercontent.com HTTPS URL"
            "（修复指引：恢复 SOURCE 常量，不要从参数或环境变量覆盖）"
        )
    last: OSError | None = None
    raw: dict[str, Any] | None = None
    for attempt in range(3):
        conn = http.client.HTTPSConnection(parsed.hostname, timeout=30)
        try:
            conn.request("GET", parsed.path)
            response = conn.getresponse()
            if response.status != 200:
                raise OSError(
                    f"ASVS source returned HTTP {response.status}"
                    "（修复指引：确认网络与 pinned commit 仍可访问后重试）"
                )
            raw = json_doc.loads(response.read().decode("utf-8"), dict, what="ASVS source")
            break
        except OSError as exc:
            last = exc
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
        finally:
            conn.close()
    if raw is None:
        raise last or OSError("ASVS source unavailable（修复指引：检查网络后重试）")
    rows = [
        row for row in raw["requirements"]
        if row.get("chapter_id") in SCOPE and int(row.get("L", 99)) <= 2
    ]
    entries: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: _natural(str(item["req_id"]))):
        ident = str(row["req_id"])
        chapter = str(row["chapter_id"])
        status, reason, verification, evidence = _assessment(ident, chapter)
        entry = {
            "id": ident,
            "chapter": chapter,
            "section": str(row["section_id"]),
            "minimum_level": int(row["L"]),
            "status": status,
            "verification": verification,
            "evidence": list(dict.fromkeys(evidence)),
        }
        if reason:
            entry["gap"] = reason
        entries.append(entry)
    ids = "\n".join(entry["id"] for entry in entries)
    return {
        "schema": "nf-asvs-evidence/1",
        "standard": {
            "name": "OWASP Application Security Verification Standard",
            "version": "5.0.0",
            "repository": "https://github.com/OWASP/ASVS",
            "commit": COMMIT,
            "scope": sorted(SCOPE, key=lambda item: int(item[1:])),
            "excluded_chapters": EXCLUDED,
            "scope_note": "Internal risk-tailored assessment of the local CLI, daemon, "
                          "MCP, plugin, file, logging, and configuration surfaces.",
        },
        "claim": {
            "kind": "internal-tailored-evidence",
            "certified": False,
            "statement": "This is not third-party ASVS certification or a claim that "
                         "every ASVS chapter applies to this product.",
        },
        "requirement_id_digest": hashlib.sha256(ids.encode()).hexdigest(),
        "requirement_count": len(entries),
        "requirements": entries,
    }


def reassess(path: Path) -> dict[str, Any]:
    """Apply current local assessments to the already pinned requirement IDs."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries = doc.get("requirements")
    if not isinstance(entries, list):
        raise ValueError(
            f"{path}: requirements must be a list"
            "（修复指引：恢复已提交矩阵，或先运行联网生成模式）"
        )
    for entry in entries:
        ident = str(entry["id"])
        chapter = str(entry["chapter"])
        status, reason, verification, evidence = _assessment(ident, chapter)
        entry["status"] = status
        entry["verification"] = verification
        entry["evidence"] = list(dict.fromkeys(evidence))
        if reason:
            entry["gap"] = reason
        else:
            entry.pop("gap", None)
    ids = "\n".join(entry["id"] for entry in sorted(entries,
                                                    key=lambda item: _natural(item["id"])))
    doc["requirement_id_digest"] = hashlib.sha256(ids.encode()).hexdigest()
    doc["requirement_count"] = len(entries)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 ASVS 5.0.0 L2 证据矩阵")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--reassess", action="store_true",
                        help="离线更新已固定 ID 的本地判定（CI 安全路径）")
    args = parser.parse_args(argv)
    try:
        doc = reassess(OUT) if args.reassess else generate()
    except (OSError, ValueError, KeyError) as exc:
        print(f"✗ ASVS 矩阵生成失败：{exc}", file=sys.stderr)
        return 2
    text = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if not args.write and not args.reassess:
        print(text, end="")
        return 0
    atomic_write.write_text(OUT, text)
    print(f"✓ ASVS 矩阵已写入：{OUT.relative_to(ROOT)}（{doc['requirement_count']} 条）")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
