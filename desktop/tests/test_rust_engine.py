#!/usr/bin/env python3
"""Rust 只读快线客户端（core.rust_engine）的常驻回归。

为什么（2026-10-22）：nf-rs 的只读面已与 Python 真源**逐字节对账**（test_rust_fastlane），
但「Python 运行期可选加速」这条链（定位二进制 → 常驻 worker → CLI 直跑 → 回退 Python）
此前没有判据——没有它，「可选加速 + 干净回退」就是一句无人核的声称。本判据钉住：

① 二进制发现：不在场即 None（fail-closed），在场即路径；
② 逐字节对账：stats --json / layers --verify --json 经 `run_face` 与 Python 真源同字节（LF 口径）；
③ 常驻 worker 往返：第一次拉起 worker、状态文件在隔离 NF_HOME 下生成、第二次命中 worker；
④ 回退纪律：NF_NO_RUST=1 / 二进制不在场 → run_face 返回 None（调用方回退 Python）；
⑤ 只读纪律：JSON 读面可解析；写面/人类可读面不在 `_rust_engine_argv` 映射内（由 nf.py 侧守）。

二进制不在场即跳过（crate 未构建不阻塞门禁；engine/rust/target 是忽略面，不入仓）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import layer_model  # noqa: E402
from core import repo_stats  # noqa: E402
from core import rust_engine as re  # noqa: E402
from core import conformance_report  # noqa: E402


def _py_stats_bytes() -> bytes:
    issues, stats = repo_stats.check(str(ROOT))
    assert not issues, "语料应零 issue，否则本判据的前提（全绿语料）不成立"
    return (json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _py_layers_bytes() -> bytes:
    issues, stats = layer_model.scan(str(ROOT))
    assert not issues, "语料应零 issue，否则本判据的前提（全绿语料）不成立"
    doc = {"kind": "layers-verify", "ok": not issues, "issues": issues, "stats": stats}
    return (json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _kill_worker(doc: dict) -> None:
    pid = doc.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        pass


class RustEngineClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nf-rust-engine-")
        self._saved_home = os.environ.get("NARRATIVE_FORGE_HOME")
        os.environ["NARRATIVE_FORGE_HOME"] = self._tmp.name

    def tearDown(self) -> None:
        sp = re.state_path()
        doc = re._load_state(sp)
        if doc:
            _kill_worker(doc)
        if self._saved_home is None:
            os.environ.pop("NARRATIVE_FORGE_HOME", None)
        else:
            os.environ["NARRATIVE_FORGE_HOME"] = self._saved_home
        self._tmp.cleanup()

    def test_binary_discovery(self) -> None:
        exe = re.binary(ROOT)
        if exe is None:
            self.skipTest("nf-rs 未构建（engine/rust/target 忽略面）")
        self.assertTrue(exe.is_file())
        self.assertIsNone(re.binary(Path(tempfile.gettempdir())))

    def test_stats_parity_via_cli(self) -> None:
        if re.binary(ROOT) is None:
            self.skipTest("nf-rs 未构建")
        res = re.run_face(["stats", "--root", str(ROOT), "--json"], root=ROOT)
        self.assertIsNotNone(res)
        code, out = res
        self.assertEqual(code, 0)
        self.assertEqual(out, _py_stats_bytes())

    def test_layers_parity_via_cli(self) -> None:
        if re.binary(ROOT) is None:
            self.skipTest("nf-rs 未构建")
        res = re.run_face(["layers", "--root", str(ROOT), "--verify", "--json"], root=ROOT)
        self.assertIsNotNone(res)
        code, out = res
        self.assertEqual(code, 0)
        self.assertEqual(out, _py_layers_bytes())

    def test_worker_roundtrip_and_isolation(self) -> None:
        if re.binary(ROOT) is None:
            self.skipTest("nf-rs 未构建")
        # 第一次：拉起 worker（状态文件应落在隔离 NF_HOME 下）。
        res1 = re.run_face(["stats", "--root", str(ROOT), "--json"], root=ROOT)
        self.assertIsNotNone(res1)
        sp = re.state_path()
        doc = re._load_state(sp)
        self.assertIsNotNone(doc)
        self.assertEqual(doc.get("proto"), re.PROTO)
        self.assertTrue(str(sp).startswith(self._tmp.name))
        # 第二次：命中常驻 worker（状态 root 匹配 → 直连，不再拉起）。
        res2 = re.run_face(["stats", "--root", str(ROOT), "--json"], root=ROOT)
        self.assertIsNotNone(res2)
        self.assertEqual(res1[1], res2[1])

    def test_disabled_returns_none(self) -> None:
        os.environ[re.ENV_DISABLE] = "1"
        try:
            self.assertIsNone(re.run_face(["stats", "--root", str(ROOT), "--json"], root=ROOT))
        finally:
            os.environ.pop(re.ENV_DISABLE, None)

    def test_missing_binary_returns_none(self) -> None:
        saved = re.binary
        re.binary = lambda root=None: None  # type: ignore[assignment]
        try:
            self.assertIsNone(re.run_face(["stats", "--root", str(ROOT), "--json"], root=ROOT))
        finally:
            re.binary = saved  # type: ignore[assignment]

    def test_run_json_parses(self) -> None:
        if re.binary(ROOT) is None:
            self.skipTest("nf-rs 未构建")
        doc = re.run_json(["stats", "--root", str(ROOT), "--json"], root=ROOT)
        self.assertIsNotNone(doc)
        self.assertIn("core_modules", doc)

    def test_stale_persistent_socket_is_closed_and_rebuilt(self) -> None:
        class _Sock:
            def __init__(self, stale=False):
                self.stale = stale
                self.closed = False

            def settimeout(self, _timeout):
                if self.stale:
                    raise OSError("stale socket")

            def setsockopt(self, *_args):
                pass

            def makefile(self, _mode):
                return mock.Mock()

            def close(self):
                self.closed = True

        stale = _Sock(stale=True)
        fresh = _Sock()
        old = re._PERSIST
        re._PERSIST = {"port": 45678, "token": "token", "sock": stale, "fh": mock.Mock()}
        try:
            with mock.patch.object(re.socket, "create_connection", return_value=fresh):
                got = re._persistent({"port": 45678, "token": "token"}, 1.0)
            self.assertTrue(stale.closed)
            self.assertIs(fresh, got["sock"])
        finally:
            re._close_persistent_locked()
            re._PERSIST = old

    def test_conformance_run_parity(self) -> None:
        """`conformance run --json` 与 `nf conformance --json` 逐字节相等（除行尾）。"""
        if re.binary(ROOT) is None:
            self.skipTest("nf-rs 未构建")
        live = conformance_report.run(str(ROOT))
        issues, _stats = conformance_report.verify_committed(str(ROOT), live=live)
        want = (json.dumps({"kind": "conformance", "report": live, "issues": issues},
                           ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        res = re.run_face(["conformance", "run", "--root", str(ROOT), "--json"], root=ROOT)
        self.assertIsNotNone(res)
        code, got = res
        self.assertIn(code, (0, 1))
        self.assertEqual(want.replace(b"\r\n", b"\n"), got.replace(b"\r\n", b"\n"))


if __name__ == "__main__":
    unittest.main()
