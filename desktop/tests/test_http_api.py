"""本地 HTTP 面单测——起真服务（端口 0）打真请求，判安全边界与判定语义。

判据覆盖：三个端点可用；判定是**判定**（invalid 也回 200）；请求本身不成立才 4xx；
Origin 白名单挡跨站；体量上限生效；非回环地址拒绝启动；请求体不落进仓库。
"""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import evidence, http_api


class _Server(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_http_t_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "d").mkdir()
        (self.root / "d" / "a.md").write_text("# A\n\n正文\n", encoding="utf-8")
        self.srv = http_api.make_server("127.0.0.1", 0, str(self.root), max_body=4096)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)

    def _stop(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)

    def _get(self, path, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     headers=headers or {}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _post(self, path, body, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body,
                                     headers=headers or {}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def _bundle(self, key=None, tamper=False):
        data, _info = evidence.build(str(self.root), ["d/a.md"], key=key,
                                     created_at="2026-01-01T00:00:00Z")
        if not tamper:
            return data
        import zipfile
        with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
            members = {n: zf.read(n) for n in zf.namelist()}
        members["payload/d/a.md"] = "改".encode()
        return evidence._zip_bytes(list(members.items()))


class TestEndpoints(_Server):
    def test_health(self):
        code, doc = self._get("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["api"], http_api.API_VERSION)
        self.assertIn("POST /api/verify", doc["endpoints"])

    def test_verify_ok_is_200(self):
        code, doc = self._post("/api/verify", self._bundle())
        self.assertEqual(code, 200)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["verdict"], "ok")

    def test_verify_invalid_is_also_200(self):
        """判定不成立 ≠ 服务错误：invalid 必须回 200，否则前端会把两者混成一件事。"""
        code, doc = self._post("/api/verify", self._bundle(tamper=True))
        self.assertEqual(code, 200)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["verdict"], "invalid")

    def test_verify_non_zip_is_400ish(self):
        code, doc = self._post("/api/verify", b"not a zip")
        self.assertEqual(code, 200)
        self.assertFalse(doc["ok"])
        self.assertIn("不是 zip", doc["error"])
        self.assertIn("修复指引", doc["fix"])

    def test_check_ok(self):
        body = json.dumps({"object": "# A\n\n正文\n", "policy": {
            "schema": "nf-check-policy/1", "id": "t",
            "rules": [{"id": "u", "kind": "utf8", "fix": "转 UTF-8"}]}}).encode()
        code, doc = self._post("/api/check", body,
                               headers={"Content-Type": "application/json"})
        self.assertEqual(code, 200)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["verdict"], "ok")

    def test_check_bad_policy_guides(self):
        body = json.dumps({"object": "x", "policy": {"schema": "nope"}}).encode()
        code, doc = self._post("/api/check", body)
        self.assertEqual(code, 200)
        self.assertFalse(doc["ok"])
        self.assertIn("修复指引", json.dumps(doc, ensure_ascii=False))

    def test_unknown_route_404(self):
        code, doc = self._get("/api/nope")
        self.assertEqual(code, 404)
        self.assertFalse(doc["ok"])


class TestSafety(_Server):
    def test_bad_origin_403(self):
        code, doc = self._post("/api/verify", self._bundle(),
                               headers={"Origin": "http://evil.example"})
        self.assertEqual(code, 403)
        self.assertIn("Origin", doc["error"])

    def test_bad_origin_with_large_body_still_gets_json(self):
        """回 403 前必须把请求体读掉：否则客户端看到的是连接异常而不是可执行指引。

        分片实测（2026-11-05）：403 分支漏了 drain，偶发 BadStatusLine/RemoteDisconnected。
        """
        code, doc = self._post("/api/verify", b"x" * 8192,
                               headers={"Origin": "http://evil.example"})
        self.assertEqual(code, 403)
        self.assertIn("Origin", doc["error"])

    def test_same_origin_allowed(self):
        code, _doc = self._post("/api/verify", self._bundle(),
                                headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(code, 200)

    def test_body_cap_413(self):
        code, doc = self._post("/api/verify", b"x" * 8192)
        self.assertEqual(code, 413)
        self.assertIn("修复指引", doc["fix"])

    def test_non_loopback_refused(self):
        with self.assertRaises(ValueError) as ctx:
            http_api.make_server("0.0.0.0", 0, str(self.root))
        self.assertIn("只绑 127.0.0.1", str(ctx.exception))

    def test_no_repo_pollution(self):
        self._post("/api/verify", self._bundle())
        leftovers = [p.name for p in self.root.iterdir() if p.name not in ("d",)]
        self.assertEqual(leftovers, [])


class TestPage(_Server):
    """本地工作台页：零构建、零外链、CSP 锁死（离线与内网都能跑，也不给第三方脚本执行位）。"""

    def _raw(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers or {}), exc.read()

    def test_index_and_verify_alias(self):
        for path in ("/", "/verify"):
            code, headers, body = self._raw(path)
            self.assertEqual(code, 200)
            self.assertIn("text/html", headers.get("Content-Type", ""))
            self.assertIn("证据复验", body.decode("utf-8"))
            self.assertIn("/assets/verify.js", body.decode("utf-8"))

    def test_csp_locked(self):
        _code, headers, _body = self._raw("/")
        csp = headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("https:", csp)

    def test_assets_served(self):
        code, headers, js = self._raw("/assets/verify.js")
        self.assertEqual(code, 200)
        self.assertIn("javascript", headers.get("Content-Type", ""))
        self.assertIn("/api/verify", js.decode("utf-8"))
        code2, headers2, css = self._raw("/assets/verify.css")
        self.assertEqual(code2, 200)
        self.assertIn("text/css", headers2.get("Content-Type", ""))
        self.assertTrue(css)

    def test_no_external_resources(self):
        """离线优先：页面与其资源不得引用任何外部地址（含 CDN / 字体 / 图片）。"""
        for path in ("/", "/assets/verify.js", "/assets/verify.css"):
            _code, _headers, body = self._raw(path)
            text = body.decode("utf-8")
            self.assertNotIn("https://", text)
            self.assertNotIn("http://", text)

    def test_unknown_asset_404(self):
        code, _headers, _body = self._raw("/assets/nope.js")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
