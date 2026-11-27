"""mcp_runtime · _const（自 mcp_runtime.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import re

#: 双时代协议版本常量（2026-07-28 规范 §Versioning 实证）
MODERN_PROTOCOL_VERSION = "2026-07-28"


LEGACY_PROTOCOL_VERSION = "2025-11-25"


SUPPORTED_VERSIONS = (MODERN_PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION)


#: 默认对外声明版本 = 支持的最新版本（历史引用点语义不变，值随规范前移）
PROTOCOL_VERSION = MODERN_PROTOCOL_VERSION


JSONRPC_VERSION = "2.0"



#: 每请求 _meta 保留键（2026-07-28 规范 §Versioning + §Discovery 实证）
META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"


META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"


#: 外来内容面的信任标注键（`_meta` 下的扩展位）：外来内容 = **数据**，不是指令（06 §12）。
META_TRUST = "nf.trust"



#: JSON-RPC 标准错误码（schema.ts L173-177 实证）
PARSE_ERROR = -32700


INVALID_REQUEST = -32600


METHOD_NOT_FOUND = -32601


INVALID_PARAMS = -32602


INTERNAL_ERROR = -32603


#: 现代版本协商错误码（2026-07-28 basic/versioning 实证）
UNSUPPORTED_PROTOCOL_VERSION = -32022



#: 传输层解码失败的哨兵值（`__slots__`-free 的模块级单例；`is` 比较，不参与 JSON）。
_DECODE_ERROR = object()


#: 单条入站消息的字节上限（入站面唯一的资源闸门；超出即拒并**丢弃到行尾**）。
#: 依据（2026-09-30 取证）：此前 `for raw in buf` 读的是「任意长度的一行」——客户端只要
#: 不发换行，就能让服务端把整条流缓冲进内存（实测 20 MB 单帧被照单全收）。MCP 正常消息是
#: KB 量级，8 MiB 已远超任何真实用途。
MAX_MESSAGE_BYTES = 8 * 1024 * 1024


#: 超长消息的哨兵值（与解码失败分开：两者语义不同，错误码也不同）。
_TOO_LONG = object()


#: 静态快照文件上限（32 MiB）：快照在启动时整体解析，不能让本地坏件无界占内存。
MAX_SNAPSHOT_BYTES = 32 << 20


#: 资源 URI 上限（字符）：别名归一需对每个登记项 unquote，不允许超长串放大 CPU。
MAX_URI_CHARS = 4096


#: 单条出站消息上限（16 MiB）：超限时回稳定错误帧，不把巨型结果继续写到管道。
MAX_RESPONSE_MESSAGE_BYTES = 16 << 20


#: 快照单资源正文上限（8 MiB）：快照整体虽已限 32 MiB，也不能让单个 body 撑爆一条响应。
MAX_SNAPSHOT_RESOURCE_TEXT_BYTES = 8 << 20




#: stdio transport 的「行边界陷阱」字符（JSON-RPC over stdio = 一条消息一行）
#: U+2028 行分隔 / U+2029 段分隔 / U+0085 NEL —— 按 Unicode 换行边界读行的客户端会把
#: 它们当换行 → 一条消息被劈成两条。JSON 规范允许裸写这些字符，故须在**出口**转义。
LINE_BOUNDARY_TRAPS = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\u0085": "\\u0085"}




#: URI 模板判据（RFC 6570 的**一级子集**：只许 `{var}` 简单展开，不许操作符/爆炸/前缀修饰）
_TEMPLATE_VAR = re.compile(r"^[A-Za-z0-9_]+$")




#: 哨兵：方法存在但本运行时未实现（只读纪律——写路径/未知方法一律拒出）
_NOT_IMPLEMENTED = object()
