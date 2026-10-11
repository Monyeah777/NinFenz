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
    try:
        if cwd:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = nf.main(list(argv))
            except SystemExit as exc:            # argparse/显式 sys.exit
                rc = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    finally:
        os.chdir(old)
    return int(rc or 0), out.getvalue(), err.getvalue()


def spawn_cli(argv, cwd=None):
    """真 spawn（对照面）→ (rc, stdout, stderr)。"""
    import subprocess
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "nf.py")] + list(argv),
                          cwd=str(cwd or ROOT), capture_output=True, text=True,
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
