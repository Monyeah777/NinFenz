# -*- coding: utf-8 -*-
"""NF Interop Layer（P-I0）：与传输无关的 JSON-RPC 2.0 分派核心。

为什么需要（§17）：LSP / MCP / HTTP 三个面各自写分派与错误形状；要「一份协议、三种传输」，
先得有**与传输无关**的核心——只吃「已解析的消息对象」，吐出「应答列表」：
  - 传输层（stdio / 本地 IPC / HTTP loopback）各自负责分帧与读写；
  - stdio 传输**复用 core/lsp_framing** 的 Content-Length 分帧（不另造一份线格式）。

纪律：纯标准库；错误码按 JSON-RPC 2.0；**通知（无 id）不应答**（§4.1）；
坏帧只回 -32700 后继续服务，绝不因一帧坏而收摊（沿用 lsp_framing 的哨兵口径）。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603

#: 处理器签名：params → result（抛异常即 -32603）。
Handler = Callable[[Any], Any]


def error(rid: Any, code: int, message: str) -> Dict[str, Any]:
    """JSON-RPC 2.0 错误应答（三处拒绝共用一处形状）。"""
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def result(rid: Any, value: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": value}


class Dispatcher:
    """方法表 + 分派。**无传输、无 IO**——同一实例可挂任意传输。"""

    def __init__(self) -> None:
        self._methods: Dict[str, Handler] = {}

    def register(self, method: str, handler: Handler) -> None:
        self._methods[method] = handler

    def methods(self) -> List[str]:
        return sorted(self._methods)

    def handle(self, msg: Any) -> List[Dict[str, Any]]:
        """单条入站消息 → 应答列表（通知返回空列表）。"""
        if isinstance(msg, list):                      # 批量：逐条处理
            out: List[Dict[str, Any]] = []
            for item in msg:
                out += self.handle(item)
            return out
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
            rid = msg.get("id") if isinstance(msg, dict) else None
            return [error(rid, INVALID_REQUEST,
                          "非法请求（须含 jsonrpc=2.0 与 method；修复指引：见 JSON-RPC 2.0 §4）")]
        method = str(msg.get("method"))
        handler = self._methods.get(method)
        if handler is None:
            if "id" not in msg:                        # 通知：未知方法也不应答
                return []
            return [error(msg.get("id"), METHOD_NOT_FOUND,
                          "未知方法：%s（修复指引：注册后重试，或改用已注册方法）" % method)]
        try:
            value = handler(msg.get("params"))
        except Exception as exc:                       # noqa: BLE001 - 处理器异常统一折成 -32603
            if "id" not in msg:
                return []
            return [error(msg.get("id"), INTERNAL_ERROR,
                          "处理器内部错误：%s（修复指引：看服务端日志；参数形状见方法说明）"
                          % type(exc).__name__)]
        if "id" not in msg:                            # 通知：执行但不应答
            return []
        return [result(msg.get("id"), value)]


def serve_stdio(dispatcher: Dispatcher, rfile: Any, wfile: Any) -> int:
    """stdio 传输：复用 lsp_framing 分帧读；坏帧回 -32700 后**继续服务**（EOF 才收摊）。"""
    from core import lsp_framing as framing
    while True:
        msg = framing.read_message(rfile)
        if msg is None:
            return 0
        if msg is framing.BAD_FRAME:
            framing.write_message(wfile, error(None, PARSE_ERROR,
                                               "坏帧（非法 UTF-8 / 非法 JSON / 坏 Content-Length）"
                                               "；修复指引：Content-Length 以字节计，正文为 UTF-8 JSON"))
            continue
        for out in dispatcher.handle(msg):
            framing.write_message(wfile, out)
