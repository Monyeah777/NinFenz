"""守护协议体量上限（`daemon._parse_request` / `_check_argv_size`）回归测试。

动机（本轮守护面模糊测试）：请求体虽限 1 MB，但**单条 argv 无上限**——实测一条 200 KB 的
参数会被照单执行，CLI 回吐 200 KB 的 argparse 用法（放大）。本件把「参数=命令/选项/标识符」
的口径钉住，越界即拒（归「请求不可读」，exit 2）。
"""
import io
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core import daemon as dm  # noqa: E402


class _Reader:
    """最小可用的逐行读桩（`_parse_request` 只依赖 `readline`）。"""

    def __init__(self, lines):
        self._lines = list(lines)

    def readline(self, limit: int = 1 << 20) -> bytes:      # noqa: ARG002
        raw = self._lines.pop(0) if self._lines else b""
        # 与 `daemon._LineReader.readline` 同口径：行尾换行不外传。
        return raw[:-1] if raw.endswith(b"\n") else raw


class _ChunkSocket:
    """最小 socket 桩：按固定块回放，用于验证跨行总预算。"""

    def __init__(self, *chunks):
        self._chunks = list(chunks)

    def recv(self, _size):
        return self._chunks.pop(0) if self._chunks else b""


class _FrameSocket:
    """`read_framed` 只依赖 `makefile('rb')`。"""

    def __init__(self, payload):
        self._payload = payload

    def makefile(self, _mode):
        return io.BytesIO(self._payload)


def _nfreq(argv, token="t"):
    lines = [("NFREQ %d %s\n" % (dm.PROTO, token)).encode(),
             b".\n", ("%d\n" % len(argv)).encode()]
    lines += [(a + "\n").encode("utf-8") for a in argv]
    return _Reader(lines)


class DaemonArgvLimitTest(unittest.TestCase):
    def test_normal_argv_passes(self):
        req = dm._parse_request(_nfreq(["stats", "--check"]))
        self.assertEqual(["stats", "--check"], req["argv"])

    def test_oversized_single_argument_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            dm._parse_request(_nfreq(["run", "A" * (dm.MAX_ARGV_CHARS + 1)]))
        self.assertIn("修复指引", str(ctx.exception))

    def test_oversized_total_is_refused(self):
        chunk = "B" * 4096
        argv = ["x"] + [chunk] * ((dm.MAX_ARGV_TOTAL // 4096) + 2)
        with self.assertRaises(ValueError):
            dm._check_argv_size(argv)

    def test_json_frame_is_checked_too(self):
        import json
        huge = json.dumps({"proto": dm.PROTO, "token": "t",
                           "argv": ["A" * (dm.MAX_ARGV_CHARS + 1)]}).encode()
        with self.assertRaises(ValueError):
            dm._parse_request(_Reader([huge]))

    def test_non_list_argv_is_left_to_later_validation(self):
        """`op=stats` 这类无 argv 的请求不受本判据影响（类型校验另有其处）。"""
        # 显式断言（N12）：纯「不抛异常」不算判据。
        self.assertIsNone(dm._check_argv_size(None))
        self.assertIsNone(dm._check_argv_size("not-a-list"))

    def test_multiline_request_has_a_total_byte_budget(self):
        """单行都小于 1 MiB，但多行累计也必须有硬上限（NFREQ 可带 4096 行）。"""
        half = b"A" * (dm.MAX_REQUEST_BYTES // 2 + 1) + b"\n"
        reader = dm._LineReader(_ChunkSocket(half, half))
        self.assertTrue(reader.readline())
        with self.assertRaises(ValueError):
            reader.readline()

    def test_invalid_utf8_in_plain_frame_is_refused(self):
        lines = [f"NFREQ {dm.PROTO} t\n".encode(), b".\n", b"1\n", b"\xff\n"]
        with self.assertRaises(ValueError):
            dm._parse_request(_Reader(lines))

    def test_json_protocol_rejects_duplicate_keys_and_nonstandard_constants(self):
        bad = [
            b'{"proto":1,"token":"good","token":"evil","argv":["--version"]}',
            b'{"proto":1,"token":"good","argv":["--version"],"extra":NaN}',
            (b"[" * 2000) + b"0" + (b"]" * 2000),
        ]
        for payload in bad:
            with self.subTest(payload=payload[:40]), self.assertRaises(ValueError):
                dm._parse_request(_Reader([payload]))

    def test_response_frame_rejects_negative_and_oversized_lengths(self):
        for payload in (b"0\n-1\n0\n", b"0\n0\n-1\n",
                        f"0\n{dm.MAX_RESPONSE_BYTES + 1}\n0\n".encode()):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                dm.read_framed(_FrameSocket(payload))

    def test_output_capture_has_a_hard_memory_cap(self):
        buf = dm._BoundedBytesIO(4)
        self.assertEqual(4, buf.write(b"1234"))
        with self.assertRaises(ValueError):
            buf.write(b"x")

    def test_server_socket_cannot_be_rebound_by_another_local_process(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        dm._configure_server_socket(sock)
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET,
                                                socket.SO_EXCLUSIVEADDRUSE))
        elif os.name == "nt":
            self.assertEqual(0, sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR))
        else:
            self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR))

    def test_cwd_must_be_an_existing_directory(self):
        root = Path(tempfile.mkdtemp(prefix="nf_daemon_cwd_"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        inside = root / "sub"
        inside.mkdir()
        self.assertEqual(str(inside.resolve()), dm._validated_cwd(root, str(inside)))
        self.assertEqual(str(root.parent.resolve()), dm._validated_cwd(root, str(root.parent)))
        with self.assertRaises(ValueError):
            dm._validated_cwd(root, str(root / "missing"))
        with self.assertRaises(ValueError):
            dm._validated_cwd(root, "bad\x00cwd")


if __name__ == "__main__":
    unittest.main()
