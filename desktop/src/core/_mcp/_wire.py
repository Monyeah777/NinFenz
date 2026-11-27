"""mcp_runtime · _wire（自 mcp_runtime.py 拆出；只移动代码，行为/文案不变）。"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional, TextIO

from ._const import (
    _DECODE_ERROR,
    _TOO_LONG,
    INTERNAL_ERROR,
    JSONRPC_VERSION,
    LINE_BOUNDARY_TRAPS,
    MAX_MESSAGE_BYTES,
)


def _drain_long_line(buf) -> None:
    """超长帧读透丢弃（保持行对齐，后续消息不受污染）。"""
    while True:
        rest = buf.readline(MAX_MESSAGE_BYTES + 1)
        if not rest or rest.endswith(b"\n"):
            break


def _iter_lines(stream: TextIO):
    """逐行读 stdio：**行级严格 UTF-8 解码**，解码失败吐哨兵而不抛。

    为什么不用 `errors="replace"`：替换会让坏字节静默变成 U+FFFD 混进 JSON 字符串——
    那是**静默数据污染**；解码失败必须显式回 `-32700`。文本流（无 `.buffer`，如单测的
    StringIO）走原路径，行为一字不变。
    """
    buf = getattr(stream, "buffer", None)
    if buf is None:
        for text in stream:
            yield text
        return
    while True:
        # `readline(limit)` 让「不发换行的超长帧」也有界：拿满上限还没见到换行 ⇒ 判超长，
        # 并把该行剩余字节读完丢弃（保持行对齐，后续消息不受污染）。
        raw = buf.readline(MAX_MESSAGE_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_MESSAGE_BYTES and not raw.endswith(b"\n"):
            _drain_long_line(buf)
            yield _TOO_LONG
            continue
        try:
            yield raw.decode("utf-8")
        except UnicodeDecodeError:
            yield _DECODE_ERROR




def _err(code: int, message: str, data: Optional[dict] = None) -> dict:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": None, "error": err}




def _err_at(code: int, message: str, rid: Any) -> dict:
    """带 id 回显的错误响应（JSON-RPC 2.0 §5：id 可判定时 MUST 回显）。"""
    out = _err(code, message)
    out["id"] = rid
    return out




def _echoable_id(msg: Any) -> Any:
    """异常响应的**可回显 id**：形态合法且有限才回显，否则 None（§5：无法判定时为 null）。"""
    if not isinstance(msg, dict) or "id" not in msg:
        return None
    rid = msg.get("id")
    if rid is None or isinstance(rid, bool):
        return None
    if isinstance(rid, float) and not math.isfinite(rid):
        return None
    return rid if isinstance(rid, (str, int, float)) else None




def _valid_request_id(rid: Any) -> bool:
    """JSON-RPC 2.0 §4：id 须为 String / Number / null（布尔、结构体、非有限数皆非法）。"""
    if rid is None:
        return True
    if isinstance(rid, bool) or not isinstance(rid, (str, int, float)):
        return False
    return not isinstance(rid, float) or math.isfinite(rid)




def encode_message(msg: Optional[dict]) -> Optional[str]:
    """响应 → 单行 UTF-8 消息（transport 纪律的可执行落点）。

    判据（modelcontextprotocol.io transports 页 + JSON-RPC 2.0 §6 换行分隔）：
    ① 紧凑分隔符（无多余空白，减小截断面）；② 行边界陷阱字符转义；
    ③ 行尾恰好一个 ``\\n``（消息内不得出现裸换行）。
    """
    if msg is None:
        return None
    text = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
    for ch, esc in LINE_BOUNDARY_TRAPS.items():
        text = text.replace(ch, esc)
    return text + "\n"




def _write_response(stdout: TextIO, resp: dict | None) -> None:
    if resp is None:
        return
    # 上限在门面测量：测试以 patch.object(mcp_runtime, MAX_RESPONSE_MESSAGE_BYTES) 收窄，
    # 故此处惰性读取门面属性（单份定义仍在 _const）。
    from core import mcp_runtime as _facade
    cap = _facade.MAX_RESPONSE_MESSAGE_BYTES
    line = encode_message(resp) or ""
    if len(line.encode()) > cap:
        rid = resp.get("id")
        line = encode_message(_err_at(
            INTERNAL_ERROR,
            f"响应超过上限 {cap} 字节"
            "（修复指引：收窄查询范围或改用分页接口）",
            rid if _valid_request_id(rid) else None,
        )) or ""
    stdout.write(line)
    stdout.flush()




def is_single_line_message(line: str) -> bool:
    """校验一行是否为合规消息（恰好一条、无裸行边界字符、非空）。"""
    body = line[:-1] if line.endswith("\n") else line
    if not body or "\n" in body or "\r" in body:
        return False
    return not any(ch in body for ch in LINE_BOUNDARY_TRAPS)
# ruff: noqa: UP035 — 拆分产物按需重复 typing 注解 import（债未新增）
