"""core._runtime 私有实现分片 2/2（对外只经 core._runtime 门面导入）：McpRuntime"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional, TextIO

from core import json_doc, repo_index
from core._mcp._const import (
    _DECODE_ERROR,
    _TOO_LONG,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    MAX_MESSAGE_BYTES,
    MAX_URI_CHARS,
    PARSE_ERROR,
)
from core._mcp._tools import _prompt_assemble_guide
from core._mcp._uris import (
    UnknownUriError,
    _extra_params_issue,
    _repo_root,
    _repo_uri_source,
    _trust_note,
    _uri_escaped_alias,
)
from core._mcp._wire import _echoable_id, _err, _err_at, _iter_lines, _write_response

from ._part1 import _McpRuntimePart1


class McpRuntime(_McpRuntimePart1):
    """快照 → MCP 资源型 server 运行时。

    数据源 = mcp_adapter 产出的 mcp.json 快照（mcp{name, version, resources[]}）。
    内部把 text 从 Resource 元数据剥离，list 与 read 两段式对外。
    """

    def _prompt_get(self, params: Any) -> dict:
        # `arguments` 是**协议里就有的可选字段**（MCP `prompts/get` params = {name, arguments?}）：
        # 很多客户端会**总是**带上它（哪怕空对象），此前一律拒 ⇒ 这类客户端取不到模板
        # （2026-10-01 实测：`{"name":…,"arguments":{}}` → -32602）。现在的口径：**允许出现**，
        # 但本模板无参数 ⇒ 只接受空对象；非空即明说「这个 prompt 不收参数」。
        issue = _extra_params_issue("prompts/get", params, ("name", "arguments"))
        if issue:
            raise ValueError(issue)
        name = params.get("name") if isinstance(params, dict) else None
        args = params.get("arguments") if isinstance(params, dict) else None
        if args is not None:
            if not isinstance(args, dict):
                raise ValueError("prompts/get 的 arguments 须为对象：%r"
                                 "（修复指引：省略该字段，或传空对象 {}）" % (args,))
            if args:
                raise ValueError("prompt %s 不接收参数：%s（修复指引：本模板无参数，省略 "
                                 "arguments 或传 {}；可用 prompts/list 看声明）"
                                 % (name, "、".join(sorted(map(str, args)))))
        if name != "assemble_guide":
            raise ValueError("未知 prompt：%s（prompts/list 可枚举）" % name)
        return {
            "description": "NF 世界装配引导（只读模板）",
            "messages": [{"role": "user",
                          "content": {"type": "text",
                                      "text": _prompt_assemble_guide()}}],
        }

    def _read(self, params: dict) -> dict:
        issue = _extra_params_issue("resources/read", params, ("uri",))
        if issue:
            raise ValueError(issue)
        uri = params.get("uri") if isinstance(params, dict) else None
        if not isinstance(uri, str) or len(uri) > MAX_URI_CHARS:
            raise UnknownUriError(uri)
        # 快照资源读取不应为了命中一个普通 uri 而先构建全仓索引。只有仓库 URI
        # 才进入实时白名单与别名归一；其余直接走构造期已装载的快照表。
        repo_meta: Dict[str, Dict[str, Any]] = {}
        if isinstance(uri, str) and uri.startswith("nf://repo/"):
            repo_meta = self._repo_metas()
        # ALIAS 语义内建：馆藏 uri 大小写不敏感（仍受白名单约束——只认已登记条目）
        if (isinstance(uri, str) and uri not in repo_meta
                and uri.lower().startswith("nf://repo/library/")):
            low = uri.lower()
            for k in repo_meta:
                if k.lower() == low:
                    uri = k
                    break
        if isinstance(uri, str) and uri not in repo_meta:
            alias = _uri_escaped_alias(uri, repo_meta)
            if alias:
                uri = alias               # 未编码写法 → 已登记的 percent-encoded 形态
        if isinstance(uri, str) and uri in repo_meta:
            entry = repo_meta[uri]
            if entry.get("source"):
                rel = str(entry["source"])
            else:
                try:
                    rel = _repo_uri_source(uri)
                except (KeyError, OSError):
                    raise UnknownUriError(uri) from None
            try:
                text = repo_index.read_text(_repo_root(), rel)
            except (ValueError, OSError) as exc:
                raise UnknownUriError(uri) from exc
            item: Dict[str, Any] = {"uri": uri, "mimeType": "text/markdown", "text": text}
            note = _trust_note([rel], [text])                # 外来面 → 带信任标注
            if note:
                item["_meta"] = note
            return {"contents": [item]}
        if uri not in self._text:
            # C2 白名单：未知 uri 拒绝（schema 无 not-found 码，参数级拒绝）
            raise UnknownUriError(uri)
        item = {
            "uri": uri,
            "mimeType": self._meta[uri]["mimeType"],
            "text": self._text[uri],
        }
        # 快照资源带 source（导出时写入）→ 外来面同样打信任标注；无 source 的官方
        # 资源保持无标注（与既有测试口径一致）。
        source = self._meta[uri].get("source")
        if source:
            note = _trust_note([str(source)], [self._text[uri]])
            if note:
                item["_meta"] = note
        return {"contents": [item]}

    def _cacheable(self, payload: dict, ttl_ms: int = 3600000,
                   cache_scope: str = "public") -> dict:
        """给可缓存结果补现代规范必填三键（resultType / ttlMs / cacheScope）。

        外部实证（2026-09-21，MCP 2026-07-28 官方 schema）：`ListResourcesResult` /
        `ListToolsResult` / `ListPromptsResult` 与 `DiscoverResult` 都继承
        `CacheableResult`，其 `required = [cacheScope, resultType, ttlMs]`——
        本仓此前只在 server/discover 上给了这三个键，list 三面缺它们（官方 schema 判 FAIL）。
        """
        out: Dict[str, Any] = {"resultType": "complete"}
        out.update(payload)
        out.setdefault("ttlMs", ttl_ms)
        out.setdefault("cacheScope", cache_scope)
        return out

    def _list_resources(self, params: dict) -> dict:
        """resources/list 分页 + 过滤（type=module|pipeline|asset|library|pattern / package）。

        **参数准入**（2026-09-30 补，fail-closed）：键只许 `cursor` / `type` / `package`；
        `cursor` 须为非负整数字符串、`type` 须在词表内。此前非法 cursor 被**静默当 0**
        （客户端以为从第一页开始）、非法 `type` **静默给空表**（客户端以为「没有这类资源」）
        ——只读面里的静默错答，与工具参数面同一类。
        """
        KINDS = ("module", "pipeline", "asset", "library", "pattern")
        if params:
            # `_` 前缀是协议保留名（2026-07-28 每请求 `_meta` 由 handle() 读取做版本协商）
            # ——保留名不算「陌生参数」，其余未知键一律拒。
            extra = sorted(k for k in set(params) - {"cursor", "type", "package"}
                           if not str(k).startswith("_"))
            if extra:
                raise ValueError("resources/list 不认识的参数：%s（修复指引：只支持 cursor / "
                                 "type / package）" % "、".join(extra))
            cur = params.get("cursor")
            if cur is not None and not (isinstance(cur, str) and (cur == "" or cur.isdigit())):
                raise ValueError("cursor 须为非负整数字符串：%r（修复指引：原样传上一页返回的 "
                                 "nextCursor）" % (cur,))
            for key in ("type", "package"):
                v = params.get(key)
                if v is not None and not isinstance(v, str):
                    raise ValueError("%s 须为字符串：%r（修复指引：用文本值，勿传数字/结构体）"
                                     % (key, v))
            t = params.get("type")
            if t and t not in KINDS:
                raise ValueError("type 词表外：%r（修复指引：%s）" % (t, " / ".join(KINDS)))
        items = list(self._meta.values()) + list(self._repo_metas().values())
        ftype = None
        fpackage = None
        if isinstance(params, dict):
            ftype = params.get("type")
            fpackage = params.get("package")
        if ftype or fpackage:
            import urllib.parse as up

            kept = []
            for it in items:
                uri = it["uri"]
                parts = uri.split("/")
                if len(parts) >= 5 and parts[0] == "nf:" and parts[2] == "repo":
                    kind = parts[3]
                    if ftype and kind != ftype:
                        continue
                    if fpackage:
                        if kind == "asset":
                            pkg = up.unquote(parts[4])
                        else:
                            pkg = it.get("package", "")
                        if pkg != fpackage:
                            continue
                elif ftype or fpackage:
                    continue
                kept.append(it)
            items = kept
        page = 20
        start = 0
        if isinstance(params, dict) and isinstance(params.get("cursor"), str):
            try:
                start = max(0, int(params["cursor"]))
            except ValueError:
                start = 0
        end = start + page
        out: Dict[str, Any] = {"resources": items[start:end]}
        if end < len(items):
            out["nextCursor"] = str(end)
        return self._cacheable(out)

    # ---- transport ----
    def serve_stdio(self, stdin: Optional[TextIO] = None,
                    stdout: Optional[TextIO] = None) -> int:
        """stdio transport 主循环：逐行读 stdin → handle → 写 stdout。

        transport 纪律（modelcontextprotocol.io transports 页实证；2026-07-28 口径不变）：
        消息以换行分隔、UTF-8、消息内不得含嵌入换行；stdout 只写 MCP 消息；
        stderr 可作日志通道（本实现静默，日志由调用方决定）。
        """
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        # transport 纪律：消息 MUST 为 UTF-8 编码（schema.ts JSONRPCMessage）——
        # Windows 下管道默认按 locale（GBK）解码，须强制 UTF-8，否则含非 ASCII
        # uri 的消息会乱码、命中白名单拒绝。
        for stream in (stdin, stdout):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8")
                except (ValueError, OSError):  # 流不支持 reconfigure（非标准流）⇒ 按宿主默认编码继续
                    pass
        try:
            for line in _iter_lines(stdin):
                if line is _TOO_LONG:
                    # 入站资源闸门：单条消息超上限 → 干净拒（-32600，带修复指引）并继续服务。
                    # 不这么做的话，客户端只要不发换行就能把整条流灌进内存（实测 20 MB 照收）。
                    out = _err(INVALID_REQUEST, "消息超上限（> %d 字节；修复指引：一条消息一行、"
                                                "UTF-8，把大载荷拆成多次调用）" % MAX_MESSAGE_BYTES)
                    _write_response(stdout, out)
                    continue
                if line is _DECODE_ERROR:
                    # 传输层解码失败：按 JSON-RPC 语义回 **-32700 Parse error** 并继续服务。
                    # 修复前这里会把 UnicodeDecodeError 抛出循环 → 长驻服务直接以「内部错误」
                    # 退出（实测 rc=1）——任一条畸形帧即可打死整个会话（agent 密集调用面）。
                    out = _err(PARSE_ERROR, "Parse error（非法 UTF-8 字节；"
                                            "修复指引：stdio 消息须为 UTF-8 编码）")
                    _write_response(stdout, out)
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json_doc.loads(line, None, what="MCP 请求帧",
                                         strict_constants=True)
                except ValueError as exc:
                    # 解析失败与 NaN/±Infinity 都归 -32700（RFC 8259 §6 只许有限数）
                    out = _err(PARSE_ERROR, "Parse error（%s；修复指引：JSON 只许有限数值）" % exc)
                    _write_response(stdout, out)
                    continue
                try:
                    resp = self.handle(msg)
                except Exception as exc:  # 防御：单条消息异常不杀循环
                    # JSON-RPC 2.0 §5：id 可判定时错误响应 MUST 回显——否则调用方按 id 匹配时
                    # 「看不到」这次失败（实测此前一律回 id=null）。
                    # R2（2026-10-22 安全审计，CWE-209）：对外只回**稳定错误码 + 通用文案**。
                    # 异常原文常带绝对路径（本仓大量「{path} 不存在」形态），回给 MCP 客户端
                    # 等于泄露服务端目录结构；细节只走 stderr（诊断面保留、不进协议面）。
                    print(f"mcp_runtime: handle() 内部异常：{type(exc).__name__}: {exc}",
                          file=sys.stderr)
                    resp = _err_at(INTERNAL_ERROR, "Internal error", _echoable_id(msg))
                _write_response(stdout, resp)
        except KeyboardInterrupt:
            # Ctrl+C：会话正常终止——静默退出，不打印 traceback
            return 130
        except BrokenPipeError:
            # client 已断开（管道破裂）：stdio 会话正常终止——静默退出
            return 0
        return 0
        return 0
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
