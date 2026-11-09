# -*- coding: utf-8 -*-
"""P-I3 进程内 CLI harness：同进程跑 scripts/nf.py 入口，捕获 stdout/stderr/退出码。

定位（重要）：本 harness **只替代「廉价且不需要真进程语义」的 spawn**，例如版本/帮助/参数错误面。
需要真进程语义的断言（信号、真实 fd、进程隔离、真实退出码传递）**继续用 subprocess**——
本 harness 不替代它们，也不得据它放松任何既有判据。

等价性不是假设，而是**逐例差分证明**：见 tests/test_cli_harness_equivalence.py。
"""
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_NF = None


def _load_nf():
    """加载 scripts/nf.py 为模块（只加载一次；导入成本即 harness 的冷启动）。"""
    global _NF
    if _NF is None:
        spec = importlib.util.spec_from_file_location("nf_cli", str(ROOT / "scripts" / "nf.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nf_cli"] = mod
        spec.loader.exec_module(mod)
        _NF = mod
    return _NF


def run_cli(argv, cwd=None):
    """同进程跑 → (rc, stdout, stderr)。rc 取返回值或 SystemExit.code。"""
    nf = _load_nf()
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    old_stdin = sys.stdin
    try:
        if cwd:
            os.chdir(cwd)
        # 真进程等价面使用 stdin=DEVNULL。进程内路径也必须显式给 EOF，否则
        # `nf lsp` / `nf serve` 一类会读 stdin 的命令会继承宿主的交互终端并永久等待。
        sys.stdin = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = nf.main(list(argv))
            except SystemExit as exc:            # argparse/显式 sys.exit
                rc = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        sys.stdin = old_stdin
        os.chdir(old)
    return int(rc or 0), out.getvalue(), err.getvalue()


def spawn_cli(argv, cwd=None):
    """真 spawn（对照面）→ (rc, stdout, stderr)。"""
    import subprocess
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py")] + list(argv),
                          cwd=str(cwd or ROOT), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL,
                          encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def equivalent(argv, cwd=None):
    """差分：两种跑法是否 (rc, stdout, stderr) 逐字节相同 → (bool, 差异说明)。"""
    a = run_cli(argv, cwd=cwd)
    b = spawn_cli(argv, cwd=cwd)
    if a == b:
        return True, ""
    diffs = []
    for label, x, y in (("rc", a[0], b[0]), ("stdout", a[1], b[1]), ("stderr", a[2], b[2])):
        if x != y:
            diffs.append("%s: harness=%r spawn=%r" % (label, str(x)[:80], str(y)[:80]))
    return False, "; ".join(diffs)


class _Completed:
    """`subprocess.CompletedProcess` 的**最小形状替身**（只暴露调用方真用到的三个属性）。

    为什么要它：本仓大量测试写的是 `r = subprocess.run([...]); r.stdout / r.returncode`。
    把那些调用点迁到进程内时，若改成解包元组 `rc, out, err = ...`，每个调用点都要改一遍
    （面大、易错）。给一个同形对象后，迁移就是**把 `subprocess.run` 换成 `run_cli_proc`**，
    断言一字不动——最小侵入，等价性也更容易逐条核对。
    """

    def __init__(self, rc: int, stdout: str, stderr: str) -> None:
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self) -> str:                                  # pragma: no cover - 诊断用
        return "<Completed rc=%s stdout=%d stderr=%d>" % (
            self.returncode, len(self.stdout), len(self.stderr))


def run_cli_proc(nf_argv, cwd=None, env=None, **_ignored):
    """进程内跑 CLI，返回 `subprocess.run(..., capture_output=True, text=True)` 形状的对象。

    **只替代不需要真进程语义的调用**（与 `run_cli` 同一条纪律）：信号、真实 fd、进程隔离、
    父进程退出码传递这些仍须 `subprocess`。

    实测收益（本机）：真 spawn 单次 **143.7 ms**；进程内首次 33 ms（导入 nf.py 的一次性成本）、
    之后单次 **≈0 ms**。门禁 check12 的最大热点 `test_cli_error_framing` 单文件 416 次 spawn，
    即为此面而迁。

    `env` 用于「注入不可用配置」类用例（如 `NARRATIVE_FORGE_HOME` 指向一个文件）：
    进程内跑不能靠子进程环境，故临时改本进程环境，结束后**原样还原**。
    `**_ignored` 用来吞掉 `capture_output=` / `text=` / `encoding=` / `errors=` / `timeout=`
    这些对进程内跑法无意义的实参——调用点因此可以原样保留。
    """
    argv = list(nf_argv)
    # 调用方普遍写 `[sys.executable, NF, *argv]` 或 `[sys.executable, "-X", "utf8", NF, *]`：
    # 去掉解释器与解释器开关，只留脚本路径之后的 CLI 参数。
    # 注意 `sys.executable` 是**绝对路径**（`C:\…\python.exe`），故按 basename 前缀判，
    # 不能拿整串 `== "python"` 去比（早期就这么写错，导致 6/6 全不一致）。
    if argv:
        head = os.path.basename(str(argv[0])).lower()
        if head.startswith(("python", "py.exe", "py")):
            argv = argv[1:]
            # 解释器开关要连**它的值**一起吃掉：`-X utf8` 的值是独立一段 argv，
            # 只吃 `-X` 会把 `utf8` 留在原地（实测直接导致 6/6 全不一致）。
            takes_value = ("-X", "-W", "-Q", "-m", "-c", "--check-hash-based-pycs")
            while argv and str(argv[0]).startswith("-"):
                opt = str(argv[0])
                argv = argv[1:]
                if opt in takes_value and argv:
                    argv = argv[1:]
    if argv and os.path.basename(str(argv[0])) in ("nf.py", "nf"):
        argv = argv[1:]

    old_env = None
    if env is not None:
        old_env = dict(os.environ)
        os.environ.clear()
        os.environ.update({str(k): str(v) for k, v in env.items()})
        reset_process_caches()
    try:
        rc, out, err = run_cli(argv, cwd=cwd)
    finally:
        if old_env is not None:
            os.environ.clear()
            os.environ.update(old_env)
            reset_process_caches()
    return _Completed(rc, out, err)


def reset_process_caches():
    """清掉「按路径/根键」的进程内缓存，让改了 env / cwd 的下一跑不吃旧值。

    与 `core.daemon` 的既有纪律同源（守护每次请求前也清按路径键的缓存，保留内容键缓存）：
    本 harness 只清**按路径/配置**的缓存——内容键缓存键即内容，天然不陈旧。
    """
    for mod in ("registry_loader", "storage", "config"):
        try:
            m = __import__("core.%s" % mod, fromlist=["_"])
        except Exception:                       # noqa: BLE001 - 缓存清理尽力而为
            continue
        for fn in ("reset_cache", "clear_cache", "_reset", "reset"):
            f = getattr(m, fn, None)
            if callable(f):
                try:
                    f()
                except Exception:               # noqa: BLE001
                    pass
                break
