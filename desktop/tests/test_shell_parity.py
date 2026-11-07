"""跨入口同证据（M2-T9）：同一对象 / 同一证据包经 CLI 与本地 HTTP 面必须得到同一判定。

判据：判定与摘要不依赖入口——相同输入在 python scripts/nf.py 上得到的
object.sha256 / verdict / policy_digest（check）与 verdict / root / count / level
（evidence verify），必须与 POST /api/check / POST /api/verify 逐键相同；
两入口判定分歧即「同证据」不可复算，证据面就是摆设。

确定性 / 离线：固定 created_at、临时根目录、服务只绑 127.0.0.1（端口 0）、
tearDownClass 关闭；CLI 子进程显式 UTF-8 解码，不依赖控制台代码页。
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import evidence, http_api

_REPO = Path(__file__).resolve().parents[2]
_NF = _REPO / "scripts" / "nf.py"
#: 固定签发时刻：测的是「两入口同判」，不是墙钟。
_PIN = "2026-01-01T00:00:00Z"
#: 含 UTF-8 中文与多行——对象字节在任何入口都不该被改写（换行/编码归一都会改摘要）。
_OBJECT = "# 跨入口同证据\n\n本内容由 AI 生成，含中文与换行。\n第二行正文。\n"


def _policy():
    """nf-check-policy/1：至少 utf8 + count_at_least 两条。

    形状同 docs/ccos/check-policy-v0.md。
    """
    return {
        "schema": "nf-check-policy/1",
        "id": "shell-parity",
        "rules": [
            {"id": "utf8-only", "kind": "utf8", "severity": "fail",
             "fix": "另存为 UTF-8"},
            {"id": "min-bytes", "kind": "count_at_least", "field": "bytes", "n": 8,
             "severity": "fail", "fix": "补足内容长度（≥8 字节）"},
        ],
    }


def _run_cli(argv):
    """跑真 CLI 子进程 → 解析 --json 输出（失败带可执行诊断，不吞退出码）。"""
    proc = subprocess.run([sys.executable, str(_NF), *argv], cwd=str(_REPO),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)
    if proc.returncode != 0:
        raise AssertionError(
            f"CLI 退出码 {proc.returncode}：{argv}\n"
            f"stderr={proc.stderr[:800]!r}\nstdout={proc.stdout[:800]!r}")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise AssertionError(f"CLI --json 输出不是 JSON：{exc}；"
                             f"stdout={proc.stdout[:800]!r}") from exc


class TestCrossEntryParity(unittest.TestCase):
    """同一输入、两个入口、同一判定。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="nf_shell_parity_")
        cls.root = Path(cls._tmp.name)
        (cls.root / "d").mkdir()
        # 对象按字节落盘：与 HTTP 侧 "w"/newline="" 的写入口径一致（摘要只认字节）。
        cls.obj = cls.root / "d" / "obj.md"
        cls.obj.write_bytes(_OBJECT.encode("utf-8"))
        cls.policy_path = cls.root / "policy.json"
        cls.policy_path.write_text(
            json.dumps(_policy(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # 证据包落临时文件；固定 created_at 保证 root/count/level 可复算。
        bundle_bytes, cls.info = evidence.build(
            str(cls.root), ["d/obj.md"], created_at=_PIN)
        cls.bundle = cls.root / "evidence.zip"
        cls.bundle.write_bytes(bundle_bytes)
        cls.srv = http_api.make_server("127.0.0.1", 0, str(cls.root))
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.srv.shutdown()
            cls.srv.server_close()
            cls.thread.join(timeout=5)
        finally:
            cls._tmp.cleanup()

    def _post(self, path, body, ctype="application/octet-stream"):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=body,
            headers={"Content-Type": ctype}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    # -- 1) 同对象同摘要同判定 -------------------------------------------
    def test_check_cli_and_http_agree(self):
        """同一对象 + 同一策略：CLI 与 POST /api/check 的摘要与判定必须逐键相同。"""
        body = json.dumps({"object": _OBJECT, "policy": _policy()},
                          ensure_ascii=False).encode("utf-8")
        code, http_doc = self._post("/api/check", body, "application/json")
        self.assertEqual(code, 200)
        cli_doc = _run_cli(["check", str(self.obj), "--policy",
                            str(self.policy_path), "--json"])

        self.assertEqual(http_doc["object"]["sha256"], cli_doc["object"]["sha256"],
                         "两入口对同一对象算出的 sha256 不同")
        self.assertEqual(http_doc["verdict"], cli_doc["verdict"],
                         "两入口对同一对象+策略的判定不同")
        self.assertEqual(http_doc["policy_digest"], cli_doc["policy_digest"],
                         "两入口对同一策略算出的 policy_digest 不同")
        # 摘要来自对象字节本身：两个入口都不得改写对象（换行/编码归一即改摘要）
        self.assertEqual(hashlib.sha256(_OBJECT.encode("utf-8")).hexdigest(),
                         http_doc["object"]["sha256"])
        self.assertEqual("ok", http_doc["verdict"])

    # -- 2) 同证据同判定 -------------------------------------------------
    def test_evidence_cli_and_http_agree(self):
        """同一证据包：CLI 与 POST /api/verify 的 verdict/root/count/level 必须相同。"""
        code, http_doc = self._post("/api/verify", self.bundle.read_bytes())
        self.assertEqual(code, 200)
        cli_doc = _run_cli(["evidence", "verify", str(self.bundle), "--json"])

        for key in ("verdict", "root", "count", "level"):
            self.assertEqual(http_doc[key], cli_doc[key],
                             f"两入口对同一证据包的 {key} 不同（同证据不同判 = 不可复算）")
        self.assertEqual("ok", http_doc["verdict"])
        self.assertEqual(1, http_doc["count"])
        self.assertEqual("digest_only", http_doc["level"])


if __name__ == "__main__":
    unittest.main()
