"""daemon 私有子模块 _proto：协议层：明文/JSON 请求框与三行头+载荷响应帧、cwd 与体量校验。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import io
import json
import os
import socket

from ._const import BIND_HOST, MAX_ARGV_CHARS, MAX_ARGV_TOTAL, MAX_CWD_CHARS, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, PROTO, SOCKET_TIMEOUT



def _configure_server_socket(sock: socket.socket) -> None:
    """Windows 用独占绑定；SO_REUSEADDR 在该平台允许别的本机进程抢绑同一端口。"""
    if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    elif os.name != "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)



def _check_argv_size(argv) -> None:
    """argv 体量上限 → 越界抛 ValueError（上层归「请求不可读」，exit 2）。

    修复前实测：单条 **200 KB** 的 argv 会被照单执行——CLI 回吐 200 KB 的 argparse 用法，
    请求体最大 1 MB 也兜不住这种放大。参数只该是命令/选项/标识符；正文请落盘后传路径。
    """
    if not isinstance(argv, list):
        return
    for a in argv:
        if isinstance(a, str) and len(a) > MAX_ARGV_CHARS:
            raise ValueError("单个参数超过上限 %d 字符（修复指引：正文/长文本先落盘，改传路径）"
                             % MAX_ARGV_CHARS)
    total = sum(len(a) for a in argv if isinstance(a, str))
    if total > MAX_ARGV_TOTAL:
        raise ValueError("参数合计超过上限 %d 字符（修复指引：减少参数，或改传文件路径）"
                         % MAX_ARGV_TOTAL)



class _LineReader:
    """带缓冲的逐行读（明文请求是多行的，不能用「recv 一次当一行」）。"""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buf = b""
        self._total = 0

    def readline(self, limit: int = MAX_REQUEST_BYTES) -> bytes:
        while True:
            line, sep, rest = self._buf.partition(b"\n")
            if sep:
                self._buf = rest
                return line
            if len(self._buf) > limit:
                raise ValueError(f"单行请求超过上限 {limit} 字节")
            chunk = self._sock.recv(65536)
            if not chunk:
                line, self._buf = self._buf, b""
                return line
            self._total += len(chunk)
            if self._total > MAX_REQUEST_BYTES:
                raise ValueError(f"请求总计超过上限 {MAX_REQUEST_BYTES} 字节")
            self._buf += chunk



class _BoundedBytesIO(io.BytesIO):
    """内存采集硬上限：越界立即失败，不先分配再事后检查。"""

    def __init__(self, cap: int) -> None:
        super().__init__()
        self._cap = int(cap)

    def write(self, data) -> int:
        size = len(data)
        if self.tell() + size > self._cap:
            raise ValueError(f"输出超过上限 {self._cap} 字节"
                             "（修复指引：收窄查询范围，或改用 --write 落盘）")
        return super().write(data)



def _decode_frame(raw: bytes, what: str) -> str:
    """协议文本一律严格 UTF-8；非法字节不得被替换字符静默洗白。"""
    try:
        return raw.decode()
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{what}不是合法 UTF-8：{exc}（修复指引：客户端须发送 UTF-8 协议帧）"
        ) from exc



def _validated_cwd(root: Path, cwd: str | None) -> str | None:
    """规范化客户端 cwd；空值表示使用守护自身 cwd。"""
    if cwd is None:
        return None
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("cwd 必须是非空字符串（修复指引：客户端传绝对目录，或省略 cwd）")
    if len(cwd) > MAX_CWD_CHARS:
        raise ValueError(f"cwd 超过上限 {MAX_CWD_CHARS} 字符（修复指引：缩短路径或省略 cwd）")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in cwd):
        raise ValueError("cwd 含控制字符（修复指引：路径里不得含 \x00-\x1f）")
    if os.name == "nt":
        # Git Bash/MSYS 的原生客户端会送 `/d/repo`；显式映射，避免 isdir 失败后静默回退。
        import re
        match = re.match(r"^/([A-Za-z])/(.*)$", cwd)
        if match:
            tail = match.group(2).replace("/", "\\")
            cwd = f"{match.group(1).upper()}:\\{tail}"
    safe = os.path.realpath(cwd)
    if not os.path.isdir(safe):
        raise ValueError(f"cwd 不是现存目录：{safe}（修复指引：传仓库根的绝对路径，或省略 cwd）")
    return safe



def _check_json_nesting(text: str, limit: int = 32) -> None:
    """JSON 请求只承载扁平控制字段；解析前先做线性深度闸，避开 RecursionError。"""
    depth = 0
    quoted = escaped = False
    for ch in text:
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise ValueError(
                    f"JSON 嵌套超过上限 {limit}（修复指引：请求体扁平化，嵌套不超过协议上限）"
                )
        elif ch in "]}":
            depth -= 1



def _strict_json_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"JSON 重复键：{key}（修复指引：请求体里每个键只写一次）")
        out[key] = value
    return out



def _parse_json_request(text: str):
    from core import json_doc
    _check_json_nesting(text)
    try:
        return json_doc.loads(text, dict, what="守护请求",
                              strict_constants=True, pairs_hook=_strict_json_object)
    except RecursionError as exc:
        raise ValueError("JSON 嵌套过深（修复指引：请求体扁平化，嵌套不超过协议上限）") from exc



def _parse_request(reader: "_LineReader") -> Dict[str, Any]:
    """解析请求框——两种形态，一种语义：

    - **JSON**（程序客户端用，argv 可含任意字符，含换行）；
    - **NFREQ 明文**（shell 客户端用：`NFREQ 1 <token>` / cwd / 条数 / 逐行 argv）——
      纯 bash 无需 JSON 编解码器即可发请求。明文框的 argv **不能含换行**（路径与命令参数
      的常规取值都不含；需要精确传递请走 JSON 框）。
    """
    head = _decode_frame(reader.readline(), "请求头")
    if head.startswith("NFREQ"):
        parts = head.split()
        if len(parts) != 3 or parts[1] != str(PROTO):
            raise ValueError("NFREQ 头格式错（期望 `NFREQ %d <token>`）" % PROTO)
        cwd = _decode_frame(reader.readline(), "NFREQ cwd")
        try:
            n = int(_decode_frame(reader.readline(), "NFREQ 条数").strip() or "0")
        except ValueError as exc:
            raise ValueError("NFREQ argv 条数不可解析：%s" % exc) from exc
        if n < 0 or n > 4096:
            raise ValueError("NFREQ argv 条数越界：%d" % n)
        argv = [_decode_frame(reader.readline(), "NFREQ argv") for _ in range(n)]
        _check_argv_size(argv)
        return {"proto": PROTO, "token": parts[2], "cwd": cwd, "argv": argv}
    req = _parse_json_request(head or "{}")
    if not isinstance(req, dict):
        raise ValueError("请求不是 JSON 对象")
    if "argv" in req:
        _check_argv_size(req.get("argv"))
    return req



def send_framed(sock: socket.socket, exit_code: int, out: bytes, err: bytes) -> None:
    """按协议写响应：三行头 + 原始载荷。"""
    if len(out) + len(err) > MAX_RESPONSE_BYTES:
        exit_code = 1
        out = b""
        err = (f"响应超过上限 {MAX_RESPONSE_BYTES} 字节"
               "（修复指引：收窄查询范围，或改用 --write 落盘）\n").encode()
    head = f"{int(exit_code)}\n{len(out)}\n{len(err)}\n".encode()
    sock.sendall(head + out + err)



def read_framed(sock: socket.socket) -> Tuple[int, bytes, bytes]:
    """按协议读响应（客户端侧）：返回 (exit, stdout 字节, stderr 字节)。"""
    fh = sock.makefile("rb")
    def _length_line(label: str) -> int:
        raw = fh.readline(64)
        if not raw or not raw.endswith(b"\n"):
            raise ValueError(f"响应帧 {label} 缺失或超长")
        try:
            value = int(raw.strip())
        except ValueError as exc:
            raise ValueError(f"响应帧 {label} 不是整数") from exc
        if value < 0 or value > MAX_RESPONSE_BYTES:
            raise ValueError(f"响应帧 {label} 越界：{value}")
        return value

    def _exact(n: int) -> bytes:
        chunks, left = [], n
        while left:
            chunk = fh.read(left)
            if not chunk:
                raise ValueError(f"响应载荷提前结束（缺 {left} 字节）")
            chunks.append(chunk)
            left -= len(chunk)
        return b"".join(chunks)

    try:
        code = _length_line("exit")
        out_len = _length_line("stdout 长度")
        err_len = _length_line("stderr 长度")
        if out_len + err_len > MAX_RESPONSE_BYTES:
            raise ValueError(f"响应载荷越界：{out_len} + {err_len} 字节")
        out = _exact(out_len) if out_len else b""
        err = _exact(err_len) if err_len else b""
    finally:
        fh.close()
    return code, out, err



def run_request(doc: Dict[str, Any], argv: List[str], cwd: Optional[str] = None,
                timeout: float = SOCKET_TIMEOUT) -> Tuple[int, bytes, bytes]:
    """客户端：把一条命令交给守护执行 → (exit, stdout 字节, stderr 字节)。

    任何连接层失败都**抛异常**——调用方（CLI / 启动器）据此静默回退到进程内执行。
    """
    req = json.dumps({"proto": PROTO, "token": doc["token"], "argv": [str(a) for a in argv],
                      "cwd": cwd or os.getcwd()}, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(req) > MAX_REQUEST_BYTES:
        raise ValueError("请求超过上限 %d 字节" % MAX_REQUEST_BYTES)
    with socket.create_connection((BIND_HOST, int(doc["port"])), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(req)
        return read_framed(sock)
