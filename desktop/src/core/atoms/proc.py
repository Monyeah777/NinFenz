"""进程原子（**受控副作用**，本包唯一的非纯面）：跑一个参数列表命令并取回输出。

纯度例外是显式登记的，不是含糊的「差不多」：

- run_capture 会真起进程，因此结果**不是**输入的函数（环境变了输出就变）——它只负责
  「跑一次、把 code/out/err 原样交回」，**不做任何判断**（不比较、不超时重试、不判红）；
- run_twice 跑两遍同一 thunk 并**原样返回两份结果**，比较留给能力层（CAP_DETERMINISTIC
  的口径在能力层，原子不知道「两遍相等」意味着什么）。

安全面：只接受 argv 列表，**永不**用 shell=True（purity_scan R6）；启动失败 / 超时都折算成
code=None + err 文本，不向调用方抛异常（少一种崩溃面）。
"""
from __future__ import annotations

import os
import signal
import subprocess  # nosec B404 - 只跑 argv 列表（无 shell、无动态拼接）
from collections.abc import Callable, Sequence
from typing import Any

from . import _wake


def run_capture(argv: Sequence[str], cwd: Any | None = None, env: dict | None = None,
                timeout: float = 120.0) -> dict[str, Any]:
    """→ {"code": int | None, "out": str, "err": str}；起不来 / 超时 → code=None。

    timeout 是**执行边界**（防挂死），不是判据：超时与否由调用方按 code=None 自行处置。
    """
    _wake("proc.run_capture")
    command = [str(part) for part in argv]
    try:
        proc = subprocess.run(  # nosec B603
            command,
            cwd=None if cwd is None else str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"code": None, "out": "", "err": str(exc)}
    return {"code": proc.returncode, "out": proc.stdout, "err": proc.stderr}


def kill_tree(pid: int) -> None:
    """回收指定进程及其子进程树（只作用于调用方给出的 PID）。"""
    _wake("proc.kill_tree")
    try:
        if os.name == "nt":
            subprocess.run(  # nosec B603/B607 - taskkill 由 Windows 固定解析
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=15)
        else:
            os.killpg(pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        # 进程可能已自行退出；调用方后续 communicate 仍会兜底。
        pass


def popen_capture(argv: Sequence[str], cwd: Any | None = None, env: dict | None = None,
                  timeout: float = 120.0, *, new_session: bool = False) -> dict[str, Any]:
    """启动并捕获一个进程；超时则回收整棵进程树，返回 `timed_out=True`。"""
    _wake("proc.popen_capture")
    command = [str(part) for part in argv]
    kwargs = {"start_new_session": True} if new_session else {}
    try:
        proc = subprocess.Popen(  # nosec B603 - argv 列表、无 shell
            command, cwd=None if cwd is None else str(cwd), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", **kwargs)
    except (OSError, ValueError) as exc:
        return {"code": None, "out": "", "err": str(exc), "timed_out": False}
    try:
        out, err = proc.communicate(timeout=timeout)
        return {"code": proc.returncode, "out": out or "", "err": err or "",
                "timed_out": False}
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        out, err = proc.communicate(timeout=15)
        return {"code": 124, "out": out or "", "err": err or "", "timed_out": True}


def run_twice(thunk: Callable[[], Any]) -> tuple[Any, Any]:
    """跑同一 thunk 两遍 → (第一次结果, 第二次结果)；**不比较**。"""
    _wake("proc.run_twice")
    return thunk(), thunk()
