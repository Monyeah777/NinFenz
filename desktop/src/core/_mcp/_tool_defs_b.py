"""mcp_runtime · _tool_defs_b（自 mcp_runtime.py 拆出的只读工具 schema 数据段）。"""
from __future__ import annotations

TOOL_DEFS_PART_B = [
    {
        "name": "pattern_read",
        "title": "Read engineering pattern",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Read one engineering pattern's full Markdown from patterns/<id>/PATTERN.md, "
            "including frontmatter, rules, and a counterexample. Use it for the practice "
            "behind an NF rule; do not use it to enumerate patterns (pattern_list) or read "
            "domain modules (module_read). pattern_id is the exact, case-sensitive "
            "directory name such as fail-closed-verification, not the document title. A "
            "missing pattern is an error, not an empty result; reads one local file and "
            "returns its full text without truncation. Local-only; no auth or rate limits."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"pattern_id": {
                "type": "string",
                "description": ("Exact pattern directory name (for example "
                                "fail-closed-verification or single-source-truth).")}},
            "required": ["pattern_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "A pattern file with its metadata and full Markdown body.",
            "properties": {
                "found": {"type": "boolean",
                          "description": "True when the pattern was located."},
                "id": {"type": "string", "description": "Pattern directory name."},
                "path": {"type": "string",
                         "description": "Repository-relative Markdown path."},
                "bytes": {"type": "integer",
                          "description": "UTF-8 byte length of text."},
                "text": {"type": "string",
                         "description": "Full PATTERN.md body as stored on disk."},
            },
            "required": ["found", "id", "path", "bytes", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "knowledge_order_read",
        "title": "Resolve knowledge order",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Return the declared knowledge-source query order and a contract-first "
            "flag.\n\n"
            "Use it before assembling or citing NF content; do not use it to search "
            "documents (use library_search instead) or read module/asset bodies "
            "(module_read / asset_read).\n\n"
            "Optional clearance is a visibility ceiling: public keeps public sources, "
            "internal keeps public and internal, restricted keeps all. Use public before "
            "republishing material, or omit it to keep all. Filtered sources are omitted "
            "without reordering the rest, and count is post-filter. Reads only the "
            "declaration, never source bodies."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"clearance": {
                "type": "string",
                "description": ("Consumer clearance; hides sources above this visibility. "
                                "Omit to keep every source."),
                "enum": ["public", "internal", "restricted"]}},
        },
        "outputSchema": {
            "type": "object",
            "description": "The resolved consultation order and the applied clearance.",
            "properties": {
                "clearance": {"type": "string",
                              "description": ("Applied clearance, or '不裁剪' when "
                                              "omitted.")},
                "contract_first": {"type": "boolean",
                                   "description": ("True when the first source in the "
                                                   "declared order is contract-level.")},
                "count": {"type": "integer",
                          "description": "Number of sources in query_order."},
                "query_order": {
                    "type": "array",
                    "description": "Sources in required consultation order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Stable source ID."},
                            "authority": {"type": "string",
                                          "description": "Source authority level."},
                            "kind": {"type": "string", "description": "Source kind."},
                            "locator": {"type": "string",
                                        "description": ("Repository-relative source "
                                                        "path.")},
                            "requires_source_label": {
                                "type": "string",
                                "description": ("'true' when quotations must carry a "
                                                "source label, 'false' otherwise.")},
                            "visibility": {"type": "string",
                                           "description": ("Visibility level used by "
                                                           "clearance filtering.")}},
                        "required": ["id", "authority", "kind", "locator",
                                     "requires_source_label", "visibility"],
                        "additionalProperties": False}},
            },
            "required": ["clearance", "contract_first", "count", "query_order"],
            "additionalProperties": False,
        },
    },
    {
        "name": "module_read",
        "title": "Fetch module document",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Read one NF module's full Markdown by ID, including its raw "
            "machine-contract block when present.\n\n"
            "Use it after registry_search resolves a module, or enumerate module IDs with "
            "registry_search and an empty query; do not use it for pipelines or assets "
            "(pipeline_read / asset_read).\n\n"
            "The ID is the declared machine-contract or heading ID (M90), or a qualified "
            "ID (通用:M10, as returned by registry_search), not the filename; matching is "
            "case-sensitive. An unknown ID returns an error with the requested value and "
            "repair guidance. Returns the full file plus resolved metadata from one local "
            "file and does not evaluate the contract. Local-only; no auth, network, rate "
            "limits, or writes."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"module_id": {
                "type": "string",
                "description": ("Exact ID (M90) or qualified ID (通用:M10); matching is "
                                "case-sensitive.")}},
            "required": ["module_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "A module file with its metadata and full Markdown body.",
            "properties": {
                "found": {"type": "boolean",
                          "description": "True when the module was located."},
                "id": {"type": "string",
                       "description": "Machine-contract or heading ID of the module."},
                "path": {"type": "string",
                         "description": "Repository-relative Markdown path."},
                "has_machine_contract": {
                    "type": "boolean",
                    "description": ("True when a machine_contract block was parsed from "
                                    "the file.")},
                "bytes": {"type": "integer",
                          "description": "UTF-8 byte length of text."},
                "text": {"type": "string",
                         "description": "Full module Markdown as stored on disk."},
            },
            "required": ["found", "id", "path", "has_machine_contract", "bytes", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pipeline_read",
        "title": "Fetch pipeline document",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Read one NF pipeline's full Markdown by P-number or repository-relative path. "
            "Use it after pipeline_list identifies a pipeline; do not use it to list "
            "pipelines (use pipeline_list instead) or read modules/assets (module_read / "
            "asset_read). "
            "pipeline is either a Pxx stem (P01, matched against the filename prefix) or a "
            ".md path under 03_管线库/ or a community pipelines/ directory; paths outside "
            "those roots and .. escapes are rejected. A missing pipeline is an error, not "
            "an empty result; reads one local file and returns its full text without "
            "truncation. Local-only; no auth or rate limits."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"pipeline": {
                "type": "string",
                "description": ("Pxx stem (P01) or repository-relative .md path under "
                                "03_管线库/ or community/*/pipelines/.")}},
            "required": ["pipeline"],
        },
        "outputSchema": {
            "type": "object",
            "description": "A pipeline file with its path and full Markdown body.",
            "properties": {
                "found": {"type": "boolean",
                          "description": "True when the pipeline was located."},
                "path": {"type": "string",
                         "description": "Repository-relative Markdown path."},
                "bytes": {"type": "integer",
                          "description": "UTF-8 byte length of text."},
                "text": {"type": "string",
                         "description": "Full pipeline Markdown as stored on disk."},
            },
            "required": ["found", "path", "bytes", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "asset_list",
        "title": "List asset keys",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "List asset files and the uppercase keys they declare, from "
            "community/*/assets and 05_资产库/用户自定义. Use it to discover a key before "
            "asset_read; do not use it to fetch asset text (asset_read) or to list "
            "modules/patterns (module_read / pattern_list). Optional package is an exact "
            "directory name, not a glob, path, or regex, and restricts the scan to "
            "community/<package>/assets (for example 校园情感领域包); README.md files are "
            "skipped. A package with no matching files returns an empty list, not an "
            "error.\n\n"
            "Keys are sorted and uncapped; each call rescans the local asset files."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"package": {
                "type": "string",
                "description": ("Optional community package name; omit to scan all "
                                "community assets and 05_资产库.")}},
        },
        "outputSchema": {
            "type": "object",
            "description": "Wrapper for the asset key list; the payload is in items.",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Asset files and their declared keys.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "package": {"type": "string",
                                        "description": ("Community package name, or 官方 "
                                                        "for user-defined assets.")},
                            "file": {"type": "string",
                                     "description": "Repository-relative Markdown path."},
                            "keys": {"type": "array",
                                     "items": {"type": "string"},
                                     "description": ("Uppercase keys declared by the file; "
                                                     "pass one to asset_read.")}},
                        "required": ["package", "file", "keys"],
                        "additionalProperties": False}},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "asset_read",
        "title": "Fetch asset content",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Read asset files for a key, returning package, path, and text.\n\n"
            "Use only a key from asset_list; for enumeration use asset_list, for other "
            "resources module_read or pipeline_read.\n\n"
            "The key is exact uppercase, never glob, regex, package, path, or prose. The "
            "package is an exact directory; it narrows files but never key matching.\n\n"
            "Tokens come from each file's name or first 6000 characters; lowercase/partial "
            "keys fail. Full text is returned; no truncation.\n\n"
            "Without a package, all community assets and 05_资产库 are searched. A package "
            "limits the scan to one directory with no fallback. Multiple matches may be "
            "returned. No match is an error."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "key": {"type": "string",
                        "description": ("Exact, case-sensitive asset key (for example "
                                        "EMOTION_WHEEL, JOB, or TECH_RULES).")},
                "package": {"type": "string",
                            "description": ("Optional community package name; omit to "
                                            "search all community assets and 05_资产库.")},
            },
            "required": ["key"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Every asset file that declares the requested key.",
            "properties": {
                "key": {"type": "string", "description": "Requested asset key."},
                "matches": {
                    "type": "array",
                    "description": "Matching files, one entry per declaring asset.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "package": {"type": "string",
                                        "description": ("Community package name, or 官方 "
                                                        "for user-defined assets.")},
                            "file": {"type": "string",
                                     "description": "Repository-relative Markdown path."},
                            "bytes": {"type": "integer",
                                      "description": "UTF-8 byte length of text."},
                            "text": {"type": "string",
                                     "description": "Full asset Markdown as stored on disk."}},
                        "required": ["package", "file", "bytes", "text"],
                        "additionalProperties": False}},
            },
            "required": ["key", "matches"],
            "additionalProperties": False,
        },
    },
]
