"""mcp_runtime · _tool_defs_a（自 mcp_runtime.py 拆出的只读工具 schema 数据段）。"""
from __future__ import annotations

TOOL_DEFS_PART_A = [
    {
        "name": "pipeline_list",
        "title": "List pipelines",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "List NF pipelines as path/title metadata from 03_管线库 and "
            "community/*/pipelines. Use it to discover a pipeline ID before pipeline_read; "
            "do not use it to fetch pipeline text (use pipeline_read instead), module "
            "metadata (registry_search), or protocol packages (spec_list). The optional query is a "
            "case-sensitive substring of the repository-relative path or H1 title, not "
            "file content; wildcard characters are literal. Omit it to list every pipeline "
            "(examples: P04, 技术文档, 校园). Returns metadata only, never pipeline bodies, "
            "sorted by repository path; no matches yields an empty list, and each call "
            "rescans the repository. Local-only; no auth or rate limits."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {
                "type": "string",
                "description": ("Case-sensitive substring matched against the relative "
                                "path and H1 title; omit to list every pipeline.")}},
        },
        "outputSchema": {
            "type": "object",
            "description": "Wrapper for the pipeline list; the payload is in items.",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Pipelines matching query, sorted by repository path.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string",
                                     "description": "Repository-relative Markdown path."},
                            "title": {"type": "string",
                                      "description": ("H1 heading text, or an empty "
                                                      "string when absent.")}},
                        "required": ["path", "title"],
                        "additionalProperties": False}},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "spec_list",
        "title": "List protocol packages",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "List protocol packages from desktop/src/core/registry.json with each "
            "package's id, version, module count, and categories. Use it for the "
            "authoritative protocol package catalog; do not use it to search modules "
            "(registry_search) or pipelines (pipeline_list), and do not treat protocol hits "
            "from registry_search as a substitute for this list. Takes no arguments; an "
            "empty list means the registry declares no protocols. Reads one local file "
            "deterministically; a missing or malformed registry is an error. Packages "
            "appear in registry order."),
        # 2026-10-08 删除已声明的 `tier`：registry 的 protocols 里**没有分级字段**，过滤从未实现
        # （实测：传任意 tier 返回完全相同的全量清单，结果里也没有 tier 字段）——「声明了不生效」
        # 是静默降级，比缺个参数更坏；宁可不声明。若将来 registry 补了分级数据，再连同实现一起加回。
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "outputSchema": {
            "type": "object",
            "description": ("Wrapper for the protocol package list; the payload is in "
                            "items."),
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Registered protocol packages in registry order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": ["string", "null"],
                                   "description": "Protocol package ID."},
                            "version": {"type": ["string", "null"],
                                        "description": "Declared package version."},
                            "modules": {"type": "integer",
                                        "description": ("Number of module IDs bound to "
                                                        "the package.")},
                            "categories": {"type": "array",
                                           "items": {"type": "string"},
                                           "description": ("Package category labels; "
                                                           "empty when undeclared.")}},
                        "required": ["id", "version", "modules", "categories"],
                        "additionalProperties": False}},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "registry_search",
        "title": "Search module registry",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Query the NF registry for modules whose id or name contains query. Use it to "
            "resolve a module ID before module_read; do not use it for the authoritative "
            "protocol package catalog (spec_list) or free-text document search "
            "(library_search). Matching is case-sensitive; query is required, and an empty "
            "query matches every entry (examples: M90, 技术文档域包). Results are grouped "
            "under modules and protocols, with protocol hits secondary. Reads registry.json "
            "only and never scans module or pipeline files; it never matches descriptions, "
            "paths, or file contents, and no matches yields empty arrays."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {
                "type": "string",
                "description": ("Case-sensitive substring matched against module and "
                                "protocol ids and names.")}},
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "description": "Modules and protocol packages matching query.",
            "properties": {
                "modules": {
                    "type": "array",
                    "description": "Matching modules in registry order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": ["string", "null"],
                                   "description": "Module ID accepted by module_read."},
                            "name": {"type": ["string", "null"],
                                     "description": "Human-readable module name."}},
                        "required": ["id", "name"],
                        "additionalProperties": False}},
                "protocols": {
                    "type": "array",
                    "description": "Matching protocol packages in registry order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": ["string", "null"],
                                   "description": "Protocol package ID accepted by spec_list."},
                            "version": {"type": ["string", "null"],
                                        "description": "Declared package version."},
                            "modules": {"type": "integer",
                                        "description": ("Number of module IDs bound to "
                                                        "the package.")}},
                        "required": ["id", "version", "modules"],
                        "additionalProperties": False}},
            },
            "required": ["modules", "protocols"],
            "additionalProperties": False,
        },
    },
    {
        "name": "library_search",
        "title": "Search library and docs",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Search the library catalog and repository docs for query, returning ranked "
            "catalog entries plus matching document titles. Use it to find an entry ID "
            "for library_read or to locate a doc or package README; do not use it for "
            "exact module or protocol metadata (registry_search / spec_list). Catalog matching "
            "is case-insensitive and relevance-ranked; document hits match the filename or "
            "H1 title as a case-sensitive substring.\n\n"
            "The combined list is capped by limit (1–50, default 10), and there is no "
            "offset or next-page parameter. Catalog hits come first, so a full catalog page "
            "can hide document hits; an empty query returns the first page of document hits "
            "only, and no matches yields an empty list."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": ("Search text; catalog hits are relevance-ranked and "
                                    "document hits match filename or H1 title.")},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": ("Maximum combined hits to return (default 10); "
                                    "catalog and document hits share the cap.")},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "description": ("Wrapper for mixed catalog and document hits; the payload "
                            "is in items."),
            "properties": {
                "items": {
                    "type": "array",
                    "description": ("Ranked catalog entries followed by matching "
                                    "documents, truncated to limit."),
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {
                                "type": "string",
                                "enum": ["library", "doc"],
                                "description": ("Hit source: library catalog entry or "
                                                "repository document.")},
                            "id": {"type": "string",
                                   "description": ("Catalog entry ID; present only for "
                                                   "kind=library.")},
                            "path": {"type": "string",
                                     "description": ("Repository-relative path of the "
                                                     "catalog file or document.")},
                            "title": {"type": "string",
                                      "description": "Entry or document title."},
                            "score": {"type": "number",
                                      "description": ("Relevance score for kind=library; "
                                                      "absent for documents.")},
                            "status": {"type": "string",
                                       "description": ("Catalog lifecycle status; present "
                                                       "only for kind=library.")},
                            "type": {"type": "string",
                                     "description": ("Catalog Diátaxis type; present only "
                                                     "for kind=library.")},
                            "uri": {"type": "string",
                                    "description": ("nf://repo/library/<id> resource URI; "
                                                    "present only for kind=library.")}},
                        "required": ["kind", "path", "title"],
                        "additionalProperties": False}},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
    {
        "name": "library_read",
        "title": "Read library entry",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Read one library catalog entry by ID, returning its frontmatter record and "
            "body. Use it after library_search resolves the ID; do not use "
            "it to search (library_search) or to read modules, pipelines, or assets "
            "(module_read / pipeline_read / asset_read). The ID is the canonical stem "
            "without the .md suffix and matching is case-insensitive (for example NF-1); "
            "an unknown ID returns an error carrying the requested value and repair "
            "guidance. Reads one local file and returns its full text without truncation. "
            "Local-only; no auth or rate limits."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"entry_id": {
                "type": "string",
                "description": ("Catalog ID, case-insensitive (for example NF-1 or "
                                "nf-worldcampus-monyeah777-1).")}},
            "required": ["entry_id"],
        },
        "outputSchema": {
            "type": "object",
            "description": "A catalog entry with its metadata and full Markdown body.",
            "properties": {
                "found": {"type": "boolean",
                          "description": "True when the entry was located."},
                "id": {"type": "string", "description": "Canonical catalog ID."},
                "path": {"type": "string",
                         "description": "Repository-relative Markdown path."},
                "status": {"type": "string",
                           "description": "Catalog lifecycle status (for example active)."},
                "frontmatter": {
                    "type": "object",
                    "description": ("Parsed YAML frontmatter as JSON; keys vary by "
                                    "entry."),
                    "additionalProperties": True},
                "bytes": {"type": "integer",
                          "description": "UTF-8 byte length of text."},
                "text": {"type": "string",
                         "description": "Full Markdown body as stored on disk."},
            },
            "required": ["found", "id", "path", "status", "frontmatter", "bytes", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pattern_list",
        "title": "List patterns",
        # 只读红线写成协议层可机读形式；四个 hint 全给，客户端才能自动放行只读调用。
        "annotations": {"readOnlyHint": True, "destructiveHint": False,
                        "idempotentHint": True, "openWorldHint": False},
        "description": (
            "List engineering patterns as id/path/title/status metadata from "
            "patterns/*/PATTERN.md, sorted by ID. Use it to discover a pattern ID before "
            "pattern_read; do not use it to fetch pattern text (use pattern_read instead) "
            "or to list modules/assets (module_read / asset_list). Returns metadata only, "
            "never the PATTERN.md body, with no pagination; no matches yields an empty "
            "list, and each call rescans the local patterns directory."),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "outputSchema": {
            "type": "object",
            "description": "Wrapper for the pattern list; the payload is in items.",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Patterns sorted by ID.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string",
                                   "description": "Pattern directory name accepted by pattern_read."},
                            "path": {"type": "string",
                                     "description": "Repository-relative PATTERN.md path."},
                            "title": {"type": "string",
                                      "description": "H1 title, or an empty string when absent."},
                            "status": {"type": "string",
                                       "description": "Pattern lifecycle status from frontmatter."}},
                        "required": ["id", "path", "title", "status"],
                        "additionalProperties": False}},
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    },
]
