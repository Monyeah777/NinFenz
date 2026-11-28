"""daemon 私有子模块 _server：服务端：连接处理/隔离、主循环、stats/ping、start/stop、进程入口。

门面 core.daemon 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._cache import reset_response_cache, set_watcher
from ._const import BIND_HOST, HANDSHAKE_TIMEOUT, PROTO
from ._proto import _configure_server_socket, read_framed, run_request
from ._state import clear_state, read_state, write_state

#: `start()` 拉起的子进程句柄（回收它，避免解释器退出时的 ResourceWarning）。
_CHILD: Optional[Any] = None



def _internal_error_frame(exc: BaseException) -> bytes:
    """一条**请求级**内部异常 → 结构化错误帧载荷（退出码由调用方置 1）。

    为什么留这一层（2026-10-10 审计 X0，P0）：CLI 面已有兜底（`nf.guarded_main`），但守护在
    「进 CLI 之前 / 出 CLI 之后」还有一段自己的活（常驻语料层同步、响应缓存查找、源码重载、
    结果落盘）。那段里的任何异常此前都会顺着 `_handle_conn` → `serve_forever` 冒出去，
    **整条守护进程退出**——而客户端只会看到 rc=1 与零输出（与「命令本身失败」不可区分）。

    口径与 `nf` 的内层错误面同源：一句「内部错误 + 修复指引」，不吐 traceback；`NF_DEBUG=1`
    时调用方改为上抛（排障），本函数不自行决定是否吞掉。
    """
    return ("  ✗ 守护内部错误：%s（修复指引：重跑同一条命令；若仍复现，请带着这条消息提 issue"
            "——该异常已被单条请求隔离，守护未退出）\n" % exc).encode("utf-8")



def _serve_conn(conn: socket.socket, token: str, root: Path) -> bool:
    """处理一条连接并做**连接级隔离**（2026-10-10 审计 X0 同族）。

    为何单独成函数：主循环的圈复杂度/长度有棘轮上限，而这段是纯错误面——客户端中途断开
    （`send_framed` 抛 BrokenPipeError/ConnectionResetError）此前会让整个 `serve_forever` 退出，
    一条被中断的请求就带走常驻进程。现在记一行、继续 accept。
    """
    conn.settimeout(HANDSHAKE_TIMEOUT)
    # 惰性取门面：python -m core.daemon 的 __main__ 实例与 core.daemon 模块实例不同一，
    # 顶层 import 会在「以模块入口运行」时形成循环（实测 runpy 下 ImportError）。
    from core import daemon as _facade_mod
    try:
        return _facade_mod._handle_conn(conn, token, root)
    except OSError as exc:
        print("  [warn] 连接中断（守护继续）：%s" % exc, file=sys.stderr)
        return False
    except Exception as exc:                       # noqa: BLE001 - 最后一道隔离网
        if os.environ.get("NF_DEBUG"):
            raise                                  # 排障：显式要求时透出堆栈
        print("  [warn] 单条连接失败（守护继续）：%s" % exc, file=sys.stderr)
        return False



def serve_forever(root: Path, idle_timeout: float = 0.0, ready: Optional[Any] = None,
                  force: bool = False, watch: bool = False) -> int:
    """守护主循环（单线程串行）：直到收到 shutdown / 空闲超时 / 被中断。

    **一个 NF_HOME 只允许一个守护**（缺省 fail-closed）：状态文件只登记一个端口/令牌，若第二个
    守护直接起，它会覆盖状态、让先起的那个「失联」（CI 实测踩过：同一 NF_HOME 下先后起两个
    服务，后者的 `clear_state()` 把前者的广告位抹掉）。确需另起用 `force=True`。

    `watch=True` 时装上目录监听 → 开「只读命令的响应缓存」（树没变就整条复用）。监听不可用
    或中途失效时**自动降级**：缓存不命中、不复用，行为与今天一致。
    """
    if not force and ping(timeout=1.0):
        print("已有守护在运行（修复指引：先 `nf daemon stop`，或显式 force 另起）", file=sys.stderr)
        return 2
    # 确定性输出（2026-10-15）：守护与直跑必须**逐字节**同输出（test_daemon_parity 守门）。
    # 但有些命令的人读面默认带墙钟耗时，而两条路径的耗时必然不同 ⇒ 值必然分叉。
    # 故守护侧统一声明「不要不确定性面」，各命令按此关闭耗时字段（当前是 nf verify）。
    os.environ["NF_VERIFY_QUIET_TIME"] = "1"
    watcher = _setup_watch(root, watch)
    token = secrets.token_hex(32)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _configure_server_socket(srv)
    srv.bind((BIND_HOST, 0))              # 端口 0 = 内核分配（不抢占固定端口）
    srv.listen(8)
    port = int(srv.getsockname()[1])
    write_state({"proto": PROTO, "pid": os.getpid(), "port": port, "token": token,
                 "root": str(root), "started": int(time.time())})
    if ready is not None:
        ready(port)
    srv.settimeout(1.0)
    return _serve_loop(srv, token, root, idle_timeout, watcher)


def _setup_watch(root, watch):
    watcher = None
    if watch:
        from core import watch as _watch
        watcher = _watch.DirWatcher(root)
        if watcher.start():
            set_watcher(watcher)
        else:
            set_watcher(None)
            watcher = None
            print("目录监听不可用（平台未实现或打开失败）→ 不启用响应缓存，"
                  "行为与常规守护一致", file=sys.stderr)
    return watcher


def _serve_loop(srv, token, root, idle_timeout, watcher):
    last = time.time()
    try:
        while True:
            if idle_timeout and (time.time() - last) > idle_timeout:
                break
            try:
                conn, _addr = srv.accept()
            except socket.timeout:  # 空闲 accept 超时属正常循环（继续等下一条连接）
                continue
            except KeyboardInterrupt:
                break
            last = time.time()
            with conn:
                shutdown = _serve_conn(conn, token, root)
            if shutdown:
                break
    finally:
        # 先清状态再关端口：客户端「连不上」与「看不到登记」才是同一时刻的真相，
        # 否则中间会有一个「端口已死但状态还在」的窗口（CI 实测：就是这样让 stop() 报
        # 「守护未响应」而不是「没有守护」）。
        if watcher is not None:
            watcher.stop()
        set_watcher(None)
        from core import conformance_scan as _csc
        _csc.clear_resident()      # 常驻语料层随守护一起消失（进程内起服务的测试不留残影）
        reset_response_cache()
        clear_state()
        srv.close()
    return 0



def query_stats(doc: Optional[Dict[str, Any]] = None,
                timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """问守护要它的响应缓存/监听状态（**必须在守护进程内取**，见 `_handle_conn` 的 stats op）。"""
    doc = doc or read_state()
    if not doc:
        return None
    try:
        req = json.dumps({"proto": PROTO, "token": doc["token"], "op": "stats"}).encode("utf-8")
        with socket.create_connection((BIND_HOST, int(doc["port"])), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(req + b"\n")
            code, out, _err = read_framed(sock)
        if code != 0:
            return None
        got = json.loads(out.decode("utf-8"))
        return got if isinstance(got, dict) else None
    except Exception:                                    # noqa: BLE001 - 查不到就如实说查不到
        return None  # best-effort 显式忽略（不可读/不可用属预期，由上层门禁另行报出）



def ping(doc: Optional[Dict[str, Any]] = None, timeout: float = 2.0) -> bool:
    """守护是否在线（带令牌发一次 `--version`）。"""
    doc = doc or read_state()
    if not doc:
        return False
    try:
        code, _out, _err = run_request(doc, ["--version"], timeout=timeout)
        return code == 0
    except Exception:                                    # noqa: BLE001 - 探测失败即「不在线」
        return False



def start(root: Path, idle_timeout: float = float(os.environ.get("NF_DAEMON_IDLE", 3600.0)),
          wait: float = 30.0,
          watch: bool = False) -> Tuple[bool, str]:
    """拉起守护（后台子进程）→ (是否成功, 说明)。已在跑则直接返回 True。"""
    if ping():
        return True, "守护已在运行"
    global _CHILD
    import subprocess
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(root) / "desktop" / "src") + os.pathsep\
        + env.get("PYTHONPATH", "")
    args = [sys.executable, "-m", "core.daemon", "--serve",
            "--root", str(root), "--idle", str(int(idle_timeout))]
    if watch:
        args.append("--watch")
    kwargs: Dict[str, Any] = {"cwd": str(root), "env": env,
                              "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":                                  # Windows：脱离控制台、不闪窗
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)\
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    _CHILD = subprocess.Popen(args, **kwargs)             # noqa: S603 - argv 列表，无 shell
    deadline = time.time() + wait
    while time.time() < deadline:
        if ping():
            return True, "守护已启动"
        time.sleep(0.05)
    return False, "守护启动超时（修复指引：手动跑 python -m core.daemon --serve 看报错）"



def _reap_child() -> None:
    """回收 `start()` 拉起的子进程（否则解释器退出时报 ResourceWarning）。"""
    global _CHILD
    if _CHILD is None:
        return
    try:
        _CHILD.wait(timeout=5)
    except Exception:                                    # noqa: BLE001 - 回收失败不影响结果
        pass  # best-effort 显式忽略（清理/探测失败不影响主流程）
    _CHILD = None



def stop(timeout: float = 8.0) -> Tuple[bool, str]:
    """请守护自行退出（协议级 shutdown，不发信号、不删文件）。"""
    doc = read_state()
    if not doc:
        return False, "没有守护在运行"
    try:
        with socket.create_connection((BIND_HOST, int(doc["port"])), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(json.dumps({"proto": PROTO, "token": doc["token"],
                                     "op": "shutdown"}).encode("utf-8") + b"\n")
            read_framed(sock)
    except (ConnectionRefusedError, ConnectionResetError):
        # 登记在、端口却拒连 = 守护早已不在（登记过期）。这不是「停不下来」，而是「没有守护」：
        # 如实报这一条并清除过期登记，才能让下一次 stop 得到确定的答案。
        clear_state()
        return False, "没有守护在运行（状态登记已过期：%s:%s 拒连，已清除）"\
            % (BIND_HOST, doc["port"])
    except Exception as exc:                             # noqa: BLE001
        clear_state()
        return False, "守护未响应（已标记停用）：%s" % exc
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not ping(doc, timeout=0.5):
            _reap_child()
            return True, "守护已停止"
        time.sleep(0.05)
    return False, "守护仍在运行"



def main(argv: Optional[List[str]] = None) -> int:
    """`python -m core.daemon --serve --root <repo> [--idle S]`（内部入口）。"""
    import argparse
    ap = argparse.ArgumentParser(prog="core.daemon",
                                 description="NF 执行层常驻守护（内部入口）")
    ap.add_argument("--serve", action="store_true", help="前台跑守护循环（供 start 拉起）")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--idle", type=float, default=float(os.environ.get("NF_DAEMON_IDLE", 3600.0)),
                    help="空闲多少秒后自动退出（0=不退出）")
    ap.add_argument("--force", action="store_true",
                    help="已有守护在运行时仍另起一个（会顶掉先起者的状态登记，默认拒绝）")
    ap.add_argument("--watch", action="store_true",
                    help="启用目录监听 + 只读命令响应缓存（树没变即整条复用；不可用自动降级）")
    args = ap.parse_args(argv)
    if not args.serve:
        ap.print_help()
        return 2
    return serve_forever(Path(args.root).resolve(), idle_timeout=args.idle,
                         force=args.force, watch=args.watch)
