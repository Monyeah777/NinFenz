"""core._runtime 私有实现分片 1/2（对外只经 core._runtime 门面导入）：_McpRuntimePart1"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core import repo_index, trust_boundary
from core._mcp._const import (
    _NOT_IMPLEMENTED,
    INVALID_PARAMS,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    LEGACY_PROTOCOL_VERSION,
    META_PROTOCOL_VERSION,
    META_SERVER_INFO,
    METHOD_NOT_FOUND,
    SUPPORTED_VERSIONS,
    UNSUPPORTED_PROTOCOL_VERSION,
)
from core._mcp._tool_defs import PROMPT_DEFS, TOOL_DEFS
from core._mcp._tools import TOOL_ALIASES, TOOL_HANDLERS
from core._mcp._uris import (
    UnknownUriError,
    _discover_instructions,
    _extra_params_issue,
    _repo_resource_templates,
    _repo_root,
    _sources_of,
    _texts_of,
    _trust_note,
)
from core._mcp._wire import _err, _err_at, _valid_request_id


class _McpRuntimePart1:

    def __init__(self, snapshot: Dict[str, Any], schema_check=None, ingress=None):
        """`schema_check`（可选）= 「参数 ⇄ inputSchema」校验器，**由调用方注入**。

        依赖倒置：本模块是稳定侧（被 `endpoint` / `mcp_package` 依赖），若直接 `import
        json_schema` 会把自身不稳定性抬到那条判据之下（实测 I 0.50 → 0.55，触发两条 SDP
        违例）。故这里只**声明接口**，实现由不稳侧（CLI 启动路径、脚本）注入——与
        `domain_pack.build(renderer=…)` 同一条纪律。未注入时不校验声明面（调用方自负）。
        """
        self._ingress = ingress
        mcp = snapshot.get("mcp", snapshot)
        self.server_name = str(mcp.get("name") or "nf-mcp")
        self.server_version = str(mcp.get("version") or "0.1.0")
        self._schema_check = schema_check
        #: uri → Resource 元数据（无 text——G2 剥离点）
        self._meta: Dict[str, Dict[str, Any]] = {}
        #: uri → 正文（read 专用，G2 两段式）
        self._text: Dict[str, str] = {}
        #: 仓库实时内容资源（nf://repo/…）；**懒构建**——首个 list/read 才建，构造不再全扫。
        self._repo_meta: Optional[Dict[str, Dict[str, Any]]] = None
        for r in mcp.get("resources") or []:
            uri = r.get("uri")
            if not uri:
                continue
            meta = {
                "uri": uri,
                "name": r.get("name") or uri,
                "mimeType": r.get("mimeType") or "text/markdown",
            }
            if r.get("source"):
                meta["source"] = str(r["source"])
            if isinstance(r.get("_meta"), dict):
                meta["_meta"] = r["_meta"]
            self._meta[uri] = meta
            self._text[uri] = r.get("text") or ""

    def _repo_metas(self) -> Dict[str, Dict[str, Any]]:
        """仓库资源白名单（懒建；RepoIndex 负责懒构建与失效）。"""
        if self._repo_meta is None:
            self._repo_meta = {m["uri"]: m
                               for m in repo_index.get(_repo_root()).resource_metas()}
        return self._repo_meta

    # ---- 消息面 ----
    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理一条入站 JSON-RPC 消息。

        通知（无 id）→ None（不应答）；请求 → 响应 dict。
        """
        if not isinstance(msg, dict):
            return _err(INVALID_REQUEST, "消息必须是 JSON 对象")
        if msg.get("jsonrpc") != JSONRPC_VERSION:
            return _err(INVALID_REQUEST, f"jsonrpc 版本必须为 {JSONRPC_VERSION}")
        method = msg.get("method")
        if not isinstance(method, str):
            return _err(INVALID_REQUEST, "缺 method")
        # 通知：无 id 字段 → 处理但不应答
        is_request = "id" in msg
        rid = msg.get("id")
        # §4：id MUST be String / Number / Null；非有限数（NaN/±Infinity）不是合法 JSON
        # （RFC 8259 §6），放行会让响应原样写出 `NaN`（严格客户端解析不了）。
        if is_request and not _valid_request_id(rid):
            return _err(INVALID_REQUEST, "id 必须是字符串、有限数字或 null"
                        "（修复指引：按 JSON-RPC 2.0 §4 用请求序号，勿用结构体/布尔/NaN/Infinity）")
        # JSON-RPC 2.0 §4.2：params 若在场 MUST be Structured（对象或数组）；
        # MCP 只定义按名对象参数 → 数组走 INVALID_PARAMS（本运行时无位置参数面）。
        if "params" in msg and msg.get("params") is not None:
            if not isinstance(msg["params"], (dict, list)):
                return _err_at(INVALID_REQUEST, "params 必须是结构化值（对象或数组）"
                               "（修复指引：JSON-RPC 2.0 §4.2——原始类型参数非法）", rid)
            if isinstance(msg["params"], list):
                return _err_at(INVALID_PARAMS, "params 只接受按名对象"
                               "（修复指引：改用 {name: value} 形式，本运行时无位置参数面）", rid)
        params = msg.get("params") or {}

        # modern 版本协商：请求自带 _meta 版本时逐请求校验（规范 §Versioning——
        # 「no negotiation handshake, every request declares its version」）。
        requested_version = None
        if isinstance(params, dict) and isinstance(params.get("_meta"), dict):
            requested_version = params["_meta"].get(META_PROTOCOL_VERSION)
        if isinstance(requested_version, str) and requested_version not in SUPPORTED_VERSIONS:
            # MUST：不支持即以 -32022 列出支持集（客户端据此选版重试）
            if is_request:
                return _err(UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version",
                            {"supported": list(SUPPORTED_VERSIONS),
                             "requested": requested_version})
            return None

        try:
            result = self._dispatch(method, params)
        except UnknownUriError:
            # uri 白名单外（read）——仅 _read 抛的专用信号才归 -32602
            if is_request:
                return {"jsonrpc": JSONRPC_VERSION, "id": rid,
                        "error": {"code": INVALID_PARAMS, "message": "未知资源 uri"}}
            return None
        except ValueError as exc:
            if is_request:
                return {"jsonrpc": JSONRPC_VERSION, "id": rid,
                        "error": {"code": INVALID_PARAMS, "message": str(exc)}}
            return None

        if result is _NOT_IMPLEMENTED:
            if is_request:
                return {"jsonrpc": JSONRPC_VERSION, "id": rid,
                        "error": {"code": METHOD_NOT_FOUND,
                                  "message": f"Method not found: {method}"}}
            return None
        if not is_request:
            return None
        return {"jsonrpc": JSONRPC_VERSION, "id": rid, "result": result}

    def _dispatch(self, method: str, params: dict) -> Any:
        if method == "server/discover":
            return self._discover(params)
        if method == "initialize":
            return self._initialize(params)
        if method == "resources/list":
            return self._list_resources(params)
        if method == "resources/templates/list":
            return self._cacheable({"resourceTemplates": _repo_resource_templates()})
        if method == "resources/read":
            return self._read(params)
        if method == "tools/list":
            return self._cacheable({"tools": TOOL_DEFS})
        if method == "tools/call":
            return self._call_tool(params)
        if method == "prompts/list":
            return self._cacheable({"prompts": [{"name": d["name"],
                                                "description": d["description"]}
                                               for d in PROMPT_DEFS]})
        if method == "prompts/get":
            return self._prompt_get(params)
        if method == "ping":
            return {}
        return _NOT_IMPLEMENTED

    # ---- 方法实现 ----
    def _capabilities(self) -> dict:
        """本服务器能力面（只读：resources/tools/prompts）。"""
        return {"resources": {}, "tools": {}, "prompts": {}}

    def _discover(self, params: dict) -> dict:
        """server/discover（2026-07-28 规范 §Discovery：现代服务器 MUST 实现）。

        一次请求返回支持版本 + 能力 + 身份（`_meta` serverInfo），供客户端选版；
        附可选 instructions 与缓存提示（ttlMs/cacheScope）。
        """
        issue = _extra_params_issue("server/discover", params, ())
        if issue:
            raise ValueError(issue)
        return {
            "resultType": "complete",
            "supportedVersions": list(SUPPORTED_VERSIONS),
            "capabilities": self._capabilities(),
            "_meta": {META_SERVER_INFO: {"name": self.server_name,
                                         "version": self.server_version}},
            "instructions": _discover_instructions(),
            "ttlMs": 3600000,
            "cacheScope": "public",
        }

    def _initialize(self, params: dict) -> dict:
        """legacy 握手（2025-11-25 及更早）：会话建在 legacy 版本上。

        双时代纪律：走 initialize 的客户端按定义是 legacy 客户端——请求版本受支持
        则回显，否则回落到最新 legacy 版本（modern 版本对其不可理解）。
        """
        issue = _extra_params_issue("initialize", params,
                                    ("protocolVersion", "capabilities", "clientInfo"))
        if issue:
            raise ValueError(issue)
        for key, typ in (("protocolVersion", str), ("capabilities", dict), ("clientInfo", dict)):
            got = params.get(key) if isinstance(params, dict) else None
            if got is not None and not isinstance(got, typ):
                raise ValueError("initialize 的 %s 须为 %s（修复指引：按 MCP 规范传 %s 对象）"
                                 % (key, typ.__name__, key))
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        version = requested if requested in SUPPORTED_VERSIONS else LEGACY_PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": self._capabilities(),
            "serverInfo": {"name": self.server_name, "version": self.server_version},
            # MCP InitializeResult 的可选 instructions 位：目录站/客户端在读工具表
            # 之前先看到「只读、无写路径、无网络」的定位，与 server/discover 同源。
            "instructions": _discover_instructions(),
        }

    # ---- C7 只读 tools/prompts（41 波C；无写路径）----
    def _call_tool(self, params: Any) -> dict:
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            raise ValueError("tools/call 需 params{name, arguments}")
        name = params["name"]
        # 旧名兼容：tools/list 只发布新名，但旧客户端仍可 calls 旧名。
        canonical = TOOL_ALIASES.get(name, name)
        # arguments 是**声明为对象**的字段：显式 null 视为未传，其余非对象一律参数非法。
        # 修此处的理由（2026-10-08 实测）：旧写法把 []/""/0/False 这些**假值**静默当成「没传参数」
        # 并继续执行——客户端以为走了位置参数，服务端却按默认值跑完并给了结果（静默降级）；
        # 口径也与 prompts/get 不一致（那边早已拒绝非对象）。
        raw_args = params.get("arguments")
        if raw_args is None:
            args: Dict[str, Any] = {}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            raise ValueError("arguments 须为对象（收到 %s；修复指引：按 tools/list 的 inputSchema "
                             "用 {name: value} 形式，勿传数组/标量）" % type(raw_args).__name__)
        handler = TOOL_HANDLERS.get(canonical)
        if handler is None:
            raise ValueError("未知工具：%s（只读工具面 = %s）"
                             % (name, "、".join(sorted(TOOL_HANDLERS))))
        # 越权/注入参数面（trust_boundary 硬面）：控制字符 / 超长载荷 / 路径穿越写法
        # 在进入处理器之前一律拒出（映射 -32602），fail-closed。
        if self._ingress is not None:
            self._ingress.check_call(canonical, args, params)
        trust_boundary.check_arguments(canonical, args)
        # **声明面校验**（2026-09-30 补）：按 `tools/list` 里那份 inputSchema 逐条校验参数——
        # 类型不符、枚举越界、**多余/拼错的键**（additionalProperties=false）都在进处理器之前
        # 拒掉。此前未知键被静默忽略：客户端把 `query` 拼成 `quer` 会拿到**未过滤的**结果，
        # 却以为筛过了（只读面里最隐蔽的一类错答）。
        schema = next((t.get("inputSchema") for t in TOOL_DEFS if t.get("name") == canonical), None)
        if isinstance(schema, dict) and self._schema_check is not None:
            unsup: List[str] = []
            errs = self._schema_check(args, schema, unsupported=unsup)
            if errs or unsup:
                raise ValueError(
                    "工具 %s 参数不合 inputSchema：%s（修复指引：按 `tools/list` 的 inputSchema "
                    "传参——键名/类型/枚举须一致，勿夹带多余键）"
                    % (name, "；".join((errs + unsup)[:4])))
        result = handler(args)
        if self._ingress is not None:
            self._ingress.record_call(canonical, args, result)
        # MCP 2025-06-18+：声明了 outputSchema 的工具必须同时给 structuredContent。
        # 列表型结果统一包成 {"items": [...]}（与 outputSchema 的根对象一致）；content
        # 仍保留原来的 JSON 文本，老客户端按文本消费不受影响。
        structured = result if isinstance(result, dict) else {"items": result}
        payload: Dict[str, Any] = {
            "content": [{"type": "text",
                         "text": json.dumps(result, ensure_ascii=False,
                                            indent=2, sort_keys=True)}],
            "structuredContent": structured,
        }
        # 信任边界（06 §12）：结果里只要掺了外来面（library/ / community/ / 外部材料），
        # 就带一条 `_meta` 标注——消费方据此按**数据**消费，标注不改正文一个字节。
        srcs: List[str] = []
        bodies: List[str] = []
        _sources_of(result, srcs)
        _texts_of(result, bodies)
        note = _trust_note(srcs, bodies)
        if note:                                  # 外来面才带标注；仓库自持内容不打标记
            payload.setdefault("_meta", {}).update(note)
        return payload
