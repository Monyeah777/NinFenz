"""Rust 只读快线（engine/rust · nf-rs）的 Python 客户端：可选加速 + 干净回退。

内部差距（2026-10-22）：engine/rust 已把多个只读判据面**逐字节对账**（stats 3.7× /
layers 4.2× / receipts 6.4× / conformance 封缄 130×，见 engine/rust/README.md），但 Python
运行期**零调用**——Rust 快线只在 CI 对账里当 oracle。本模块把「定位二进制 → 常驻 worker /
直跑 CLI → 回退 Python」落成一条 stdlib-only 的调用面。

为什么是「可选加速」而非「替换真源」
------------------------------------
真源仍在 Python 侧（ADR-0005：Rust/.NET 是只读第二实现，不替代 verify.sh）。所以本模块：

- **只做搬运与回退**：二进制不在场 / worker 起不来 / 任何连接层错误 → 返回 None，调用方
  回退 Python 真源（今天的既有行为）；
- **不写仓库文件**：worker 状态只落 NF_HOME（复用 `core.storage.default_home` 单源）；
- **只读面**：只跑 nf-rs 的只读判据，不提供任何 `--write` 语义；
- **显式 opt-in**：`NF_ENGINE=rust`（或 `--engine rust`）才走本路径，缺省仍是 Python。

协议（与 `core/daemon.py` 同形，版本化极简）
------------------------------------------
请求 = 一行 JSON：``{"proto":1,"token":"…","argv":["stats","--root","…","--json"]}``；
响应 = 三行明文头 + 原始字节：``<exit>\\n<out_len>\\n<err_len>\\n`` + stdout 字节 + stderr 字节。

依赖姿态：stdlib-only（socket/json/subprocess/pathlib）。SDP 叶子；不 import 任何 core 模块
（NF_HOME 单源在函数内惰性取用，避免抬高本模块的反向依赖）。
"""
from __future__ import annotations

import json
import atexit
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROTO = 1

ENV_DISABLE = "NF_NO_RUST"
ENV_ENGINE = "NF_ENGINE"

BIND_HOST = "127.0.0.1"
STATE_FILENAME = "rust_worker.json"
MAX_RESPONSE_BYTES = 16 << 20
MAX_STATE_BYTES = 64 << 10

#: 候选二进制路径（release 优先，其次 debug；与 test_rust_fastlane.CANDIDATES 同源）。
CANDIDATES: Tuple[str, ...] = (
    "engine/rust/target/release/nf-rs.exe",
    "engine/rust/target/release/nf-rs",
    "engine/rust/target/debug/nf-rs.exe",
    "engine/rust/target/debug/nf-rs",
)

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 30.0
_START_WAIT = 3.0
_START_INTERVAL = 0.05

#: `_start()` 拉起的子进程句柄（回收它，避免解释器退出时的 ResourceWarning——与 core/daemon.py
#: 的 `_CHILD` 同一条纪律）。
_CHILD: Optional[subprocess.Popen] = None
_PERSIST_LOCK = threading.Lock()
_PERSIST: Optional[Dict[str, Any]] = None


def _reap_child() -> None:
    """回收 `_start()` 拉起的 worker 句柄（否则解释器退出时报 ResourceWarning）。"""
    global _CHILD
    if _CHILD is None:
        return
    try:
        # 短超时：worker 常驻时应继续活着（wait 超时即放弃）；若已被测试 taskkill 回收则立即返回。
        _CHILD.wait(timeout=0.3)
    except Exception:                                    # noqa: BLE001 - 回收失败不影响结果
        pass
    _CHILD = None


atexit.register(_reap_child)


def _close_persistent_locked() -> None:
    global _PERSIST
    if _PERSIST is not None:
        try:
            _PERSIST["sock"].close()
        except OSError:
            # 关闭失败只影响资源回收；持久连接状态随后仍置空并重建。
            pass
    _PERSIST = None


def _close_persistent() -> None:
    with _PERSIST_LOCK:
        _close_persistent_locked()


atexit.register(_close_persistent)


def _persistent(doc: Dict[str, Any], timeout: float) -> Optional[Dict[str, Any]]:
    """取/建持久连接（调用方持 `_PERSIST_LOCK`）。"""
    global _PERSIST
    port = doc.get("port")
    token = doc.get("token")
    if not isinstance(port, int) or not isinstance(token, str) or not token:
        return None
    if (_PERSIST is not None and _PERSIST.get("port") == port
            and _PERSIST.get("token") == token):
        try:
            _PERSIST["sock"].settimeout(timeout)
            return _PERSIST
        except OSError:
            # 陈旧/半关闭 socket：清掉后走下方的一次重建路径。
            _close_persistent_locked()
    _close_persistent_locked()
    sock = None
    try:
        sock = socket.create_connection((BIND_HOST, port),
                                        timeout=min(timeout, _CONNECT_TIMEOUT))
        sock.settimeout(timeout)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            # TCP_NODELAY 是延迟优化；平台拒绝时连接仍可正确工作。
            pass
        _PERSIST = {"port": port, "token": token, "sock": sock,
                    "fh": sock.makefile("rb")}
    except OSError:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                # 建连失败路径的关闭失败不覆盖原始连接错误。
                pass
        _PERSIST = None
        return None
    return _PERSIST


def repo_root() -> Path:
    """仓库根（本模块在 desktop/src/core/ 下，上溯三级）。"""
    return Path(__file__).resolve().parents[3]


def disabled() -> bool:
    """NF_NO_RUST=1 → 强制不走 Rust（调试/隔离用）。"""
    return (os.environ.get(ENV_DISABLE) or "").strip().lower() in (
        "1", "true", "yes", "on")


def requested() -> bool:
    """NF_ENGINE=rust|auto|1 → 显式请求走 Rust 加速。"""
    return (os.environ.get(ENV_ENGINE) or "").strip().lower() in (
        "rust", "auto", "1", "true", "yes", "on")


def binary(root: Optional[Path] = None) -> Optional[Path]:
    """定位 nf-rs 可执行件；不在场返回 None。"""
    base = root or repo_root()
    for rel in CANDIDATES:
        p = base / rel
        if p.is_file():
            return p
    return None


def state_path() -> Path:
    """worker 状态文件落点：`<NF_HOME>/rust_worker.json`（单源 = storage.default_home）。"""
    try:
        from core import storage
        return storage.default_home() / STATE_FILENAME
    except Exception:
        # 取不到单源时退回同形缺省（仍是用户态，不落仓库）。
        return Path.home() / ".NinFenz" / STATE_FILENAME


def _load_state(sp: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = sp.read_bytes()
        if len(raw) > MAX_STATE_BYTES:
            return None
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        # 状态文件缺失/损坏等价于 worker 不可用，由上层走受控回退。
        return None
    return doc if isinstance(doc, dict) else None


def _read_frame(fh) -> tuple[int, bytes]:
    """读取 Rust worker 三行头 + 载荷；负数/超长/截断一律拒绝。"""
    head = [fh.readline(64) for _ in range(3)]
    if any(not line or not line.strip() or not line.endswith(b"\n") for line in head):
        raise ValueError("响应头缺失或超长")
    try:
        code, out_len, err_len = (int(line.strip()) for line in head)
    except ValueError as exc:
        raise ValueError("响应头不是整数") from exc
    if out_len < 0 or err_len < 0 or out_len + err_len > MAX_RESPONSE_BYTES:
        raise ValueError("响应长度越界")
    out = fh.read(out_len) if out_len else b""
    _err = fh.read(err_len) if err_len else b""
    if len(out) != out_len:
        raise ValueError("响应载荷提前结束")
    return code, out


def _talk(doc: Dict[str, Any], argv: List[str], timeout: float) -> Optional[Tuple[int, bytes]]:
    """按状态文件里的 port/token 发一帧 → (exit_code, stdout 字节)；任何连接层错误 → None。"""
    port = doc.get("port")
    token = doc.get("token")
    if not isinstance(port, int) or not isinstance(token, str) or not token:
        return None
    frame = json.dumps({"proto": PROTO, "token": token, "argv": list(argv)},
                       ensure_ascii=False) + "\n"
    with _PERSIST_LOCK:
        for attempt in (0, 1):
            if attempt:
                _close_persistent_locked()
            conn = _persistent(doc, timeout)
            if conn is None:
                return None
            try:
                conn["sock"].sendall(frame.encode("utf-8"))
                fh = conn["fh"]
                code, out = _read_frame(fh)
                return (code, out)
            except (OSError, ValueError):
                _close_persistent_locked()
        return None


def _kill_pid(pid: int) -> None:
    """回收指定 pid（只用于**本模块自己**从 state 文件里读到的旧 worker）。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        # 旧 worker 已退出或无法回收时无需故障升级；状态文件校验会决定是否重建。
        pass


def _start(root: Path, sp: Path) -> bool:
    """非阻塞拉起常驻 worker，并**有界**等待状态文件出现。"""
    global _CHILD
    _close_persistent()          # 旧连接随旧 worker 失效
    exe = binary(root)
    if exe is None:
        return False
    # 重启前先回收旧 worker（state 文件里的 pid）：否则每次超时重启都会留下一只孤儿。
    old_doc = _load_state(sp)
    if old_doc:
        old_pid = old_doc.get("pid")
        if isinstance(old_pid, int) and old_pid > 0:
            _kill_pid(old_pid)
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        if sp.exists():
            sp.unlink()
    except OSError:
        # 状态目录不可写时 worker 不可启动，由调用方回退 Python 真源。
        return False
    cmd = [str(exe), "serve", "--state", str(sp), "--root", str(root)]
    flags = 0
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP：脱离控制台、不随父进程死。
        flags = 0x00000008 | 0x00000200
    try:
        # 覆盖句柄前先回收已退出的旧 worker：不 wait 的话，旧句柄在 GC 时仍「运行中」→ ResourceWarning。
        old = _CHILD
        if old is not None:
            try:
                old.wait(timeout=0.0)
            except (subprocess.TimeoutExpired, OSError):
                # 已退出子进程的回收是尽力而为；worker 状态文件才是活性依据。
                pass
        _CHILD = subprocess.Popen(cmd, cwd=str(root), stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=flags, start_new_session=(os.name != "nt"))
    except OSError:
        return False
    deadline = time.monotonic() + _START_WAIT
    while time.monotonic() < deadline:
        if _load_state(sp) is not None:
            return True
        time.sleep(_START_INTERVAL)
    return False


def _run_cli(exe: Path, root: Path, argv: List[str], timeout: float) -> Optional[Tuple[int, bytes]]:
    """worker 不可用时的兜底：直跑一次 CLI 子进程（仍比 Python 真源快，但付进程启动税）。"""
    try:
        proc = subprocess.run([str(exe), *argv], cwd=str(root), capture_output=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        # CLI 兜底不可启动时返回 None，调用方回退 Python 真源。
        return None
    return (proc.returncode, proc.stdout)


def run_face(argv: List[str], root: Optional[Path] = None,
             timeout: float = _READ_TIMEOUT) -> Optional[Tuple[int, bytes]]:
    """跑一条只读判据面 → (exit_code, stdout 字节)；完全不可用 → None（调用方回退 Python）。

    顺序：常驻 worker → 拉起 worker 再试一次 → 直跑 CLI 子进程。任一环节失败都往下走；
    二进制不在场 / NF_NO_RUST=1 直接 None。
    """
    if disabled():
        return None
    base = Path(root) if root else repo_root()
    exe = binary(base)
    if exe is None:
        return None
    sp = state_path()

    doc = _load_state(sp)
    if doc and doc.get("proto") == PROTO and doc.get("root") == str(base):
        res = _talk(doc, argv, timeout)
        if res is not None:
            return res
    if _start(base, sp):
        doc = _load_state(sp)
        if doc:
            res = _talk(doc, argv, timeout)
            if res is not None:
                return res
    return _run_cli(exe, base, argv, timeout)


def run_json(argv: List[str], root: Optional[Path] = None,
             timeout: float = _READ_TIMEOUT) -> Optional[Any]:
    """跑一条只读面并解析为 JSON（仅在 exit==0 且可解析时返回对象，否则 None）。"""
    res = run_face(argv, root=root, timeout=timeout)
    if res is None:
        return None
    code, out = res
    if code != 0:
        return None
    try:
        doc = json.loads(out.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        # Rust 输出不可解析时按该快线不可用处理，保留 Python 诊断回退。
        return None
    if not isinstance(doc, (dict, list)):
        return None
    return doc


def worker_stats(timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """worker 只读计数（requests / bytes_in / bytes_out）；不可用 → None。"""
    doc = _load_state(state_path())
    if not doc:
        return None
    frame = json.dumps({"proto": PROTO, "token": doc.get("token"), "op": "stats"}) + "\n"
    with _PERSIST_LOCK:
        conn = _persistent(doc, timeout)
        if conn is None:
            return None
        try:
            conn["sock"].sendall(frame.encode("utf-8"))
            fh = conn["fh"]
            code, out = _read_frame(fh)
            if code != 0:
                return None
            got = json.loads(out.decode("utf-8"))
            if not isinstance(got, dict):
                return None
            return got
        except (OSError, ValueError, UnicodeDecodeError):
            _close_persistent_locked()
            # 观测帧不可解析时关闭连接；worker 仍可由下一条请求重建。
            return None


__all__ = ["PROTO", "ENV_DISABLE", "ENV_ENGINE", "binary", "disabled", "requested",
           "repo_root", "run_face", "run_json", "state_path", "worker_stats"]
