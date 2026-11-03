#!/usr/bin/env python3
"""A 桶证据内核门禁（check43 的执行体候选）。

跑三组测试：gate_core_selftest / a_bucket_smoke / evidence_mcp。
退出码 0 = 全绿；1 = 有红；2 = 运行器异常。
不新增判据逻辑，只做「把最值钱的 A 桶模块接入持续门禁」的执行面。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ["test_gate_core_selftest.py", "test_a_bucket_smoke.py", "test_evidence_mcp.py"]


def main() -> int:
    failed = []
    for pat in PATTERNS:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "desktop/tests",
             "-p", pat, "-q"],
            cwd=str(ROOT), capture_output=True, text=True)
        line = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = line[-1] if line else ""
        if proc.returncode == 0:
            print("  [PASS] %s · %s" % (pat, tail))
        else:
            failed.append(pat)
            print("  [FAIL] %s · %s" % (pat, tail))
            if proc.stderr:
                print(proc.stderr[-800:])
    print("A 桶证据内核：%d 组 · 通过 %d · 失败 %d"
          % (len(PATTERNS), len(PATTERNS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):   # 钉 UTF-8 stdio
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
