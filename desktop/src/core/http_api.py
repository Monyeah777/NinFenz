"""本地 HTTP 面（v0）：只绑回环、只读、无客户端可控路径、体量上限。

为什么有它（内部差距 2026-11-04）：复验器只有 CLI 面——要验一份证据，对方得装 Python、
装仓库、记参数。「不用装也能验」的最小落点是本机 HTTP：浏览器、前端、别的语言都能直接 POST。

安全边界照方案写死：只绑 127.0.0.1（非回环地址直接拒绝启动）、Origin 白名单（CSRF）、
请求体上限、**不接收客户端给的任何文件系统路径**（一切落盘都在进程私有临时目录）。

端点（v0，全部幂等 + 纯读）：
  GET  /api/health   → 服务与契约版本
  POST /api/verify   → 请求体 = 自包含证据包（zip 字节）→ 四词判定
  POST /api/check    → 请求体 = {object: UTF-8 文本, policy: nf-check-policy/1} → verdict

纪律：判定结果是**判定**，不是 HTTP 错误——invalid / revoked / expired 一律 200；4xx 只表示
「请求本身不成立」（格式错、超限、来源不允许）。反过来做，前端就会把「证据不成立」和
「服务挂了」混成一件事。
"""
from __future__ import annotations

import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from core import check_policy, evidence, json_doc, web_pages

API_VERSION = "nf-http/1"
MAX_BODY = 8 * 1024 * 1024
LOOPBACK = ("127.0.0.1", "localhost", "::1")
_GUIDE = "修复指引："
_ZIP_MAGIC = b"PK\x03\x04"


def _json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def _health() -> dict[str, Any]:
    return {"ok": True, "api": API_VERSION, "tool": "nf",
            "evidence_schema": evidence.SCHEMA,
            "check_policy_schema": check_policy.SCHEMA,
            "endpoints": ["GET /api/health", "POST /api/verify", "POST /api/check"],
            "page": "/verify"}


def _verify_body(body: bytes, root: str) -> dict[str, Any]:
    """请求体 = 自包含证据包字节 → 四词判定（落盘只进临时目录）。"""
    if not body.startswith(_ZIP_MAGIC):
        return {"ok": False, "error": "请求体不是 zip 证据包",
                "fix": _GUIDE + "本端点只收自包含证据包（nf evidence pack 的 .zip）；"
                       "单 JSON 形态请用 CLI：nf evidence verify <json> --root <成员根>"}
    with tempfile.TemporaryDirectory(prefix="nf_http_") as tmp:
        path = os.path.join(tmp, "bundle.zip")
        with open(path, "wb") as fh:
            fh.write(body)
        try:
            res = evidence.verify(path)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc),
                    "fix": _GUIDE + "本端点只收自包含证据包（nf evidence pack 的 .zip）"}
    return {"ok": res["verdict"] == "ok", "verdict": res["verdict"],
            "level": res["level"], "root": res["root"], "count": res["count"],
            "issues": res["issues"]}


def _check_body(body: bytes, root: str) -> dict[str, Any]:
    """请求体 = {object, policy} → 单对象体检（对象与策略只写临时目录）。"""
    try:
        doc = json_doc.loads(body.decode("utf-8"), dict, what="请求体")
    except (ValueError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": f"请求体不是合法 JSON 对象：{exc}",
                "fix": _GUIDE + "请 POST JSON：{\"object\": \"<文本>\", \"policy\": {...}}"}
    if not isinstance(doc, dict):
        return {"ok": False, "error": "请求体顶层应为对象",
                "fix": _GUIDE + "请 POST {\"object\": ..., \"policy\": ...}"}
    text, policy = doc.get("object"), doc.get("policy")
    if not isinstance(text, str) or not isinstance(policy, dict):
        return {"ok": False, "error": "缺 object（字符串）或 policy（对象）",
                "fix": _GUIDE + "object 必须是 UTF-8 文本；policy 必须是 nf-check-policy/1 对象"}
    with tempfile.TemporaryDirectory(prefix="nf_http_") as tmp:
        obj = os.path.join(tmp, "object.txt")
        with open(obj, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        try:
            res = check_policy.check(obj, policy)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc),
                    "fix": _GUIDE + "策略须是合法的 nf-check-policy/1"
                           "（见 docs/ccos/check-policy-v0.md）"}
    return {"ok": res["verdict"] == "ok", "verdict": res["verdict"],
            "policy_id": res["policy_id"], "policy_digest": res["policy_digest"],
            "object": {"sha256": res["object"]["sha256"], "bytes": res["object"]["bytes"]},
            "findings": res["findings"], "failed": res["failed"], "warned": res["warned"]}


class _Handler(BaseHTTPRequestHandler):
    """单文件处理器：只认三个端点；其余一律 404。"""

    server_version = "nf-http/1"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:      # 静音：别把请求日志打成输出
        return

    # -- 公共 ----------------------------------------------------------
    def _send(self, code: int, payload: dict[str, Any]) -> None:
        data = _json_bytes(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, body: bytes, ctype: str,
                    extra: dict[str, str] | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, val in (extra or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self) -> bool:
        """CSRF 护栏：带了 Origin 就必须是本机同端口（浏览器跨站请求会被挡）。"""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        port = self.server.server_address[1]
        host = self.headers.get("Host") or ""
        allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}",
                   f"http://{host}"}
        return origin in allowed

    def _drain(self) -> None:
        """把请求体读掉（**回 4xx 前必备**）。

        为什么：不读就回错误，客户端往往还在写请求体，于是它看到的是「远端关闭连接」而不是我们
        给的可执行指引（2026-11-05 分片实测：403 分支漏了这一步，偶发 BadStatusLine）。
        与 413 分支同一口径：先读掉（最多 limit+1 字节）再回。
        """
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return
        limit = int(getattr(self.server, "max_body", MAX_BODY))
        if length > 0:
            self.rfile.read(min(length, limit + 1))

    def _body(self) -> tuple[bytes | None, str]:
        """读请求体（有上限）→ (字节, 拒绝原因)。超限时先**把体读掉**再回 4xx。

        为什么必须读掉：不读就回 413，客户端往往还在写请求体，会看到「远端关闭连接」而不是
        我们给的错误说明——用户拿到的是一条网络异常，不是一个可执行指引。
        """
        if self.headers.get("Transfer-Encoding"):
            return None, "不支持分块传输（请带 Content-Length）"
        try:
            length = int(self.headers.get("Content-Length") or "")
        except ValueError:
            return None, "缺 Content-Length（无法判定请求体长度）"
        limit = int(getattr(self.server, "max_body", MAX_BODY))
        if length < 0:
            return None, "Content-Length 非法"
        if length > limit:
            self.rfile.read(min(length, limit + 1))
            return None, f"请求体超过上限（上限 {limit} 字节）"
        return self.rfile.read(length), ""

    # -- 路由 ----------------------------------------------------------
    def do_GET(self) -> None:
        if not self._origin_ok():
            self._send(403, {"ok": False, "error": "来源不允许（Origin 校验失败）",
                             "fix": _GUIDE + "浏览器请从 http://127.0.0.1 同端口访问"})
            return
        route = self.path.split("?")[0]
        if route == "/api/health":
            self._send(200, _health())
            return
        if route in ("/", "/verify", "/index.html"):
            self._send_bytes(web_pages.html(), "text/html; charset=utf-8",
                             {"Content-Security-Policy": web_pages.CSP})
            return
        if route == "/assets/verify.js":
            self._send_bytes(web_pages.js(), "text/javascript; charset=utf-8")
            return
        if route == "/assets/verify.css":
            self._send_bytes(web_pages.css(), "text/css; charset=utf-8")
            return
        self._send(404, {"ok": False, "error": "未知端点",
                         "fix": _GUIDE + "可用端点见 GET /api/health"})

    def do_POST(self) -> None:
        if not self._origin_ok():
            self._drain()          # 先读掉请求体：否则客户端看到的是连接异常而不是 403
            self._send(403, {"ok": False, "error": "来源不允许（Origin 校验失败）",
                             "fix": _GUIDE + "浏览器请从 http://127.0.0.1 同端口访问"})
            return
        body, why = self._body()
        if body is None:
            self._send(413, {"ok": False, "error": why,
                             "fix": _GUIDE + f"请带 Content-Length 且不超过 "
                                     f"{int(getattr(self.server, 'max_body', MAX_BODY))} 字节"})
            return
        route = self.path.split("?")[0]
        root = str(getattr(self.server, "root", "."))
        try:
            if route == "/api/verify":
                self._send(200, _verify_body(body, root))
                return
            if route == "/api/check":
                self._send(200, _check_body(body, root))
                return
        except (OSError, ValueError) as exc:      # 兜底：绝不把异常变成断连
            self._send(500, {"ok": False, "error": str(exc),
                             "fix": _GUIDE + "这是服务侧异常，请带上请求内容报告；"
                                    "判定结论未产生，不要当成证据不成立"})
            return
        self._send(404, {"ok": False, "error": "未知端点",
                         "fix": _GUIDE + "可用端点见 GET /api/health"})


def make_server(host: str = "127.0.0.1", port: int = 0, root: str = ".",
                max_body: int = MAX_BODY) -> ThreadingHTTPServer:
    """建服务（未启动）。host 必须是回环——公网绑定一律拒绝启动。"""
    if host not in LOOPBACK:
        raise ValueError(f"拒绝绑定非回环地址：{host}"
                         "（修复指引：请只绑 127.0.0.1 / localhost / ::1——"
                         "本服务是本地工作台，不是网络服务）")
    srv = ThreadingHTTPServer((host, int(port)), _Handler)
    srv.daemon_threads = True
    srv.root = root                                    # type: ignore[attr-defined]
    srv.max_body = int(max_body)                       # type: ignore[attr-defined]
    return srv


def serve(host: str = "127.0.0.1", port: int = 8765, root: str = ".") -> int:
    """前台起服务（Ctrl-C 停）。启动信息走 stderr，避免污染可管道化的输出。"""
    import sys
    try:
        srv = make_server(host, port, root)
    except ValueError as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"  ✗ 端口不可用：{exc}（{_GUIDE}换端口：nf serve --http --port <N>）",
              file=sys.stderr)
        return 2
    actual = srv.server_address[1]
    print(f"== nf serve --http（{API_VERSION}）==", file=sys.stderr)
    print(f"  监听：http://{host}:{actual}", file=sys.stderr)
    print(f"  端点：{', '.join(_health()['endpoints'])}", file=sys.stderr)
    print("  停止：Ctrl-C", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:      # Ctrl-C 是正常停止路径，不是失败（不留异常帧）
        pass
    finally:
        srv.server_close()
    return 0
