"""MCP Server 运行时（v2.5.0 Wave5 C1：快照烧成服务——静态 mcp.json → stdio JSON-RPC）。

33_v2.2.0_A5-MCP规范差距核查报告 三差距勾销（对照 2025-11-25 schema.ts 实证）：
- G1 形态级：mcp.json 静态定义文件 → 运行时 JSON-RPC 会话协议（stdio transport，
  换行分隔 UTF-8 消息——transport 页实证）；mcp.json 快照降为数据源。
- G2 字段级：resources/list 返回去 text 的 Resource 纯元数据（schema.ts L802 Resource
  无 text）；正文经 resources/read 按 uri 返回 contents[].text（L895 TextResourceContents）。
- G4 归属层：name/version 从快照顶层迁入 initialize 握手 serverInfo（L550 Implementation）——
  快照文件仅作数据源，运行时自述经握手。

C2 最小安全层（Wave5 随 C1）：
- 只读：本运行时只实现只读面（resources list/read + 41 波C C7 只读 tools/prompts），
  写路径工具一律不实现（-32601 METHOD_NOT_FOUND / 未知工具 -32602 天然被拒）。
- uri 白名单：resources/read 只接受快照内已登记 uri，未知 uri → -32602 INVALID_PARAMS
  （schema.ts 无 resource-not-found 专用码，参数级拒绝为最小面裁决，不泄露目录结构）。

C7 只读工具面（41_v2.8.0_波C质量编译深化规划，2026-09-08）：
- tools（检索类结构化工具，inputSchema 真实存在）：library_search（仓库侧知识库检索）/
  registry_search（registry 模块+协议查询）/ pipeline_list（管线清单）/ spec_list（协议包清单）。
- prompts：assemble_guide 装载引导模板（1 条）。
- 数据源 = 本仓库只读扫描（03_管线库/04_模块库/community/*/docs/registry.json），
  不改 C2 只读安全层（全部只读，无 tools 写路径）。

协议事实（2026-07-28 规范 basic/versioning + server/discover 实证；dual-era 服务器）：
- modern（2026-07-28 起）：无协商握手——每请求以 `_meta` 携带协议版本/身份/能力；
  版本不受支持 → UnsupportedProtocolVersionError（-32022，data={supported,requested}）。
- legacy（2025-11-25 及更早）：`initialize` 握手建会话；本运行时保留双时代兼容
  （术语见规范 §Versioning：modern / legacy / dual-era）。
- `server/discover`：现代服务器 MUST 实现——一次返回 supportedVersions /
  capabilities / serverInfo(_meta) 与可选 instructions / ttlMs / cacheScope。
- initialize 响应：{protocolVersion, capabilities, serverInfo: Implementation, instructions}
- notifications/initialized 是通知（无 id）→ 不应答；ping → EmptyResult（{}）
- 标准错误码：PARSE_ERROR=-32700 / INVALID_REQUEST=-32600 / METHOD_NOT_FOUND=-32601 /
  INVALID_PARAMS=-32602 / INTERNAL_ERROR=-32603

用法：
    snap = load_snapshot("mcp.json")     # 快照 → 运行时数据源
    srv = McpRuntime(snap)
    srv.serve_stdio(sys.stdin, sys.stdout)   # 换行分隔 JSON-RPC 循环
"""
from __future__ import annotations

# ruff: noqa: F401 — 门面按原模块面重新导出（re-export 是职责，不是未使用）
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 依赖面：实现在 _mcp 子包；本行履约原模块对 core 的 import 边（勿删）。
# 资源面调用点（拆分后在子包内）：RepoIndex.resource_metas / RepoIndex.docs_matching /
# RepoIndex.source_of —— 供死代码判据识别既有调用面。
from core import json_doc, knowledge, repo_index, trust_boundary

from ._mcp._const import (
    _DECODE_ERROR,
    _NOT_IMPLEMENTED,
    _TEMPLATE_VAR,
    _TOO_LONG,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    LEGACY_PROTOCOL_VERSION,
    LINE_BOUNDARY_TRAPS,
    MAX_MESSAGE_BYTES,
    MAX_RESPONSE_MESSAGE_BYTES,
    MAX_SNAPSHOT_BYTES,
    MAX_SNAPSHOT_RESOURCE_TEXT_BYTES,
    MAX_URI_CHARS,
    META_PROTOCOL_VERSION,
    META_SERVER_INFO,
    META_TRUST,
    METHOD_NOT_FOUND,
    MODERN_PROTOCOL_VERSION,
    PARSE_ERROR,
    PROTOCOL_VERSION,
    SUPPORTED_VERSIONS,
    UNSUPPORTED_PROTOCOL_VERSION,
)
from ._mcp._runtime import (
    McpRuntime,
)
from ._mcp._tool_defs import (
    PROMPT_DEFS,
    TOOL_DEFS,
)
from ._mcp._tools import (
    TOOL_ALIASES,
    TOOL_HANDLERS,
    _prompt_assemble_guide,
    _tool_asset_get,
    _tool_asset_list,
    _tool_knowledge_order_read,
    _tool_library_read,
    _tool_library_search,
    _tool_module_read,
    _tool_pattern_list,
    _tool_pattern_read,
    _tool_pipeline_list,
    _tool_pipeline_read,
    _tool_registry_search,
    _tool_spec_list,
)
from ._mcp._uris import (
    UnknownUriError,
    _discover_instructions,
    _extra_params_issue,
    _repo_read_uri,
    _repo_resource_metas,
    _repo_resource_templates,
    _repo_root,
    _repo_uri_source,
    _sources_of,
    _texts_of,
    _trust_note,
    _uri_escaped_alias,
    template_matches,
    uri_template_issue,
)
from ._mcp._wire import (
    _echoable_id,
    _err,
    _err_at,
    _iter_lines,
    _valid_request_id,
    _write_response,
    encode_message,
    is_single_line_message,
)


def _read_snapshot(path: str) -> Dict[str, Any]:
    p = Path(path)
    try:
        with p.open("rb") as fh:
            raw = fh.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ValueError(f"快照超过上限 {MAX_SNAPSHOT_BYTES} 字节"
                             "（修复指引：删除未使用资源后重新导出）")
        # 用单一实现（N11）：顶层形状在下方就地判；这里只要「合法 JSON 才回」。
        return json_doc.loads(raw.decode("utf-8"), None, what=path)
    except OSError:
        raise
    except ValueError as exc:
        raise ValueError("快照不是合法 JSON：%s（修复指引：用 `nf run --fmt mcp --dest <目录>` 重生"
                         "成）" % exc) from exc


def _snapshot_resources(data: Any, p: Path) -> List[Any]:
    if not isinstance(data, dict) or "mcp" not in data:
        raise ValueError("快照缺 mcp 顶层键（非 mcp.json 产物）：%s"
                         "（修复指引：用 `nf run --fmt mcp` 重生成；或直接 `nf serve` 走实时仓库面"
                         "）" % p)
    if not isinstance(data.get("mcp"), dict):
        raise ValueError("快照的 mcp 键须为对象（修复指引：同上）")
    resources = data["mcp"].get("resources") or []
    if not isinstance(resources, list):
        raise ValueError("快照的 mcp.resources 须为列表（修复指引：同上）")
    return resources


def _check_resources(resources: List[Any]) -> None:
    for idx, item in enumerate(resources, 1):
        if not isinstance(item, dict) or not str(item.get("uri") or "").strip():
            raise ValueError(f"快照第 {idx} 条 resource 缺 uri 或不是对象（修复指引：同上）")
        text = item.get("text")
        if text is None:
            continue
        if not isinstance(text, str):
            raise ValueError(f"快照第 {idx} 条 resource.text 须为字符串（修复指引：同上）")
        if len(text.encode()) > MAX_SNAPSHOT_RESOURCE_TEXT_BYTES:
            raise ValueError(
                f"快照第 {idx} 条 resource.text 超过上限 "
                f"{MAX_SNAPSHOT_RESOURCE_TEXT_BYTES} 字节（修复指引：拆分资源）"
            )


def load_snapshot(path: str) -> Dict[str, Any]:
    """读 mcp.json 静态快照 → 运行时数据源 dict（mcp{name, version, resources[]}）。

    形状不合规一律抛**带修复指引的 ValueError**（用户输入问题不得冒成「内部错误」——
    实测修复前：不存在 / 非法 JSON / 缺 mcp / `resources` 非列表，四种都报「内部错误」rc=1）。
    文件不存在抛 `OSError`（由调用方给指引）。
    """
    p = Path(path)
    data = _read_snapshot(path)
    _check_resources(_snapshot_resources(data, p))
    return data




def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口：python -m core.mcp_runtime <mcp.json>（stdio 服务）。

    接线（2026-10-01 收口）：与 `nf serve` 一样注入 `json_schema.json_schema_check`。为守住
    SDP（`endpoint` / `mcp_package` 依赖本模块），这里**以移除 `plog` 出边对等换入**
    `json_schema` 出边（Ce 5 → 5，I 保持 0.50）——既不新增架构债，也不静默降级（此前本入口
    照常启动但 `query:123` 冒成 -32603，是同一条参数在 `nf serve` 下回 -32602 的不一致）。
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        sys.stderr.write("用法: python -m core.mcp_runtime <mcp.json>  （stdio MCP 服务）\n")
        return 2
    snap = load_snapshot(args[0])
    from core import json_schema
    srv = McpRuntime(snap, schema_check=json_schema.json_schema_check)
    sys.stderr.write("MCP server 启动：%s v%s（stdio · 只读 resources/tools/prompts）\n"
                     % (srv.server_name, srv.server_version))
    rc = srv.serve_stdio()
    sys.stderr.write("MCP server 退出：rc=%s\n" % rc)
    return rc




if __name__ == "__main__":
    sys.exit(main())
