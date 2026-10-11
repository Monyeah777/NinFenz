# -*- coding: utf-8 -*-
"""core.interop 回归：分派 / 通知不应答 / 错误码 / 批量 / stdio 坏帧不杀会话。"""
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import interop as ip            # noqa: E402
from core import lsp_framing as framing   # noqa: E402


def _d():
    d = ip.Dispatcher()
    d.register("add", lambda p: (p or {}).get("a", 0) + (p or {}).get("b", 0))
    d.register("boom", lambda _p: 1 / 0)
    return d


class DispatchTest(unittest.TestCase):
    def test_request_returns_result(self):
        out = _d().handle({"jsonrpc": "2.0", "id": 1, "method": "add", "params": {"a": 2, "b": 3}})
        self.assertEqual([{"jsonrpc": "2.0", "id": 1, "result": 5}], out)

    def test_notification_has_no_reply_but_runs(self):
        seen = []
        d = ip.Dispatcher()
        d.register("note", lambda p: seen.append(p))
        self.assertEqual([], d.handle({"jsonrpc": "2.0", "method": "note", "params": 1}))
        self.assertEqual([1], seen)

    def test_unknown_method(self):
        out = _d().handle({"jsonrpc": "2.0", "id": 7, "method": "nope"})
        self.assertEqual(ip.METHOD_NOT_FOUND, out[0]["error"]["code"])

    def test_invalid_request_keeps_id(self):
        out = _d().handle({"id": 9, "method": "add"})
        self.assertEqual(ip.INVALID_REQUEST, out[0]["error"]["code"])
        self.assertEqual(9, out[0]["id"])
        self.assertEqual(ip.INVALID_REQUEST, _d().handle("nope")[0]["error"]["code"])

    def test_handler_exception_is_internal_error(self):
        out = _d().handle({"jsonrpc": "2.0", "id": 2, "method": "boom"})
        self.assertEqual(ip.INTERNAL_ERROR, out[0]["error"]["code"])

    def test_batch(self):
        out = _d().handle([{"jsonrpc": "2.0", "id": 1, "method": "add", "params": {"a": 1, "b": 1}},
                           {"jsonrpc": "2.0", "method": "add", "params": {"a": 9, "b": 9}}])
        self.assertEqual(1, len(out))
        self.assertEqual(2, out[0]["result"])

    def test_methods_sorted(self):
        self.assertEqual(["add", "boom"], _d().methods())


class StdioTest(unittest.TestCase):
    def _serve(self, frames):
        buf = io.BytesIO()
        for m in frames:
            framing.write_message(buf, m)
        buf.seek(0)
        out = io.BytesIO()
        rc = ip.serve_stdio(_d(), buf, out)
        out.seek(0)
        got = []
        while True:
            m = framing.read_message(out)
            if m is None or m is framing.BAD_FRAME:
                break
            got.append(m)
        return rc, got

    def test_round_trip(self):
        rc, got = self._serve([{"jsonrpc": "2.0", "id": 1, "method": "add", "params": {"a": 4, "b": 5}},
                               {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 1}}])
        self.assertEqual(0, rc)
        self.assertEqual([{"jsonrpc": "2.0", "id": 1, "result": 9}], got)

    def test_bad_frame_does_not_kill_session(self):
        buf = io.BytesIO()
        buf.write(b"Content-Length: 5\r\n\r\n{bad}")      # 先写坏帧（头合法、正文不可解析）
        framing.write_message(buf, {"jsonrpc": "2.0", "id": 3, "method": "add", "params": {"a": 1, "b": 1}})
        buf.seek(0)
        out = io.BytesIO()
        rc = ip.serve_stdio(_d(), buf, out)
        out.seek(0)
        first = framing.read_message(out)
        second = framing.read_message(out)
        self.assertEqual(0, rc)
        self.assertEqual(ip.PARSE_ERROR, first["error"]["code"])
        self.assertEqual(2, second["result"], "坏帧后必须继续服务（旧坑：一帧坏就收摊）")


class ThreeTransportsTest(unittest.TestCase):
    """P-I1：**同一分派核心**挂三条传输，必须给出同一结果。"""

    REQ = {"jsonrpc": "2.0", "id": 42, "method": "add", "params": {"a": 20, "b": 22}}

    def _via_stdio(self):
        buf = io.BytesIO()
        framing.write_message(buf, self.REQ)
        buf.seek(0)
        out = io.BytesIO()
        ip.serve_stdio(_d(), buf, out)
        out.seek(0)
        return framing.read_message(out)

    def _via_lines(self):
        buf = io.BytesIO((json.dumps(self.REQ) + "\n").encode("utf-8"))
        out = io.BytesIO()
        ip.serve_lines(_d(), buf, out)
        return json.loads(out.getvalue().decode("utf-8").strip())

    def _via_http(self):
        import urllib.request
        server, _thread = ip.serve_http(_d())
        try:
            port = server.server_address[1]
            req = urllib.request.Request(
                "http://127.0.0.1:%d/" % port, method="POST",
                data=json.dumps(self.REQ).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

    def test_same_result_across_transports(self):
        got = {"stdio": self._via_stdio(), "lines": self._via_lines(), "http": self._via_http()}
        self.assertEqual({"jsonrpc": "2.0", "id": 42, "result": 42}, got["stdio"])
        self.assertEqual(got["stdio"], got["lines"], got)
        self.assertEqual(got["stdio"], got["http"], got)

    def test_lines_bad_line_continues(self):
        buf = io.BytesIO(b"{not json}\n" + (json.dumps(self.REQ) + "\n").encode("utf-8"))
        out = io.BytesIO()
        self.assertEqual(0, ip.serve_lines(_d(), buf, out))
        rows = [json.loads(x) for x in out.getvalue().decode("utf-8").strip().splitlines()]
        self.assertEqual(ip.PARSE_ERROR, rows[0]["error"]["code"])
        self.assertEqual(42, rows[1]["result"])


if __name__ == "__main__":
    unittest.main()
