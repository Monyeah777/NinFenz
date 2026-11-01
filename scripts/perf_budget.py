#!/usr/bin/env python3
"""性能预算（CLI）：声明 → 实测 N 次 → 落证据 → 判新鲜度与预算。

用法：
  python scripts/perf_budget.py              # 只读校验（缺记录/过期/超预算即 exit 1）
  python scripts/perf_budget.py --list       # 列声明与最近实测
  python scripts/perf_budget.py --record     # 全部实测并写证据（缺省）
  python scripts/perf_budget.py --record --only nf_score
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))

from core import perf_budget as pb  # noqa: E402


def _rec_line(r) -> str:
    """一条证据的展示口径（唯一处）：中位 / P95 / σ / min-max——方差字段缺失（旧记录）如实留空。"""
    if not r:
        return "（无实测记录）"
    tail = ""
    if r.get("p95_ms") is not None:
        tail += " · P95 %6.0f" % float(r.get("p95_ms") or 0)
    if r.get("stdev_ms") is not None:
        tail += " · σ %5.1f" % float(r.get("stdev_ms") or 0)
    return ("实测中位 %6.0f%s ms（%s · min %.0f / max %.0f）"
            % (float(r.get("median_ms") or 0), tail, r.get("measured_at"),
               float(r.get("min_ms") or 0), float(r.get("max_ms") or 0)))


def _resolve_shell() -> str:
    """POSIX shell 落点：复用 `core.posix_shell` 的解析顺序（**唯一真相**），但不代它退出。

    修 2026-10-10 审计 P3 W6：此处此前写死 `C:/comfyui/Git/bin/bash.exe`——那是**某一台机器**
    的安装位，换机即失效，且把作者机路径带进了仓库。解析不到返回空串（不 `sys.exit`：性能
    记录应继续，缺 shell 的那条如实记 exit=1，而不是把整次 `--record` 打掉）。
    """
    from core import posix_shell as ps
    try:
        return ps.posix_shell()
    except SystemExit:
        return ""


def _runner(cmd: str, runs: int):
    """真跑 N 次 → (last_exit_code, [ms,...])；argv 列表执行（无 shell）。"""
    argv = shlex.split(cmd)
    if not argv:
        return 1, []
    if argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    elif argv[0] in ("bash", "sh"):
        found = shutil.which(argv[0]) or _resolve_shell()
        if found:
            argv[0] = found
    times, code = [], 1
    for _ in range(max(1, runs)):
        t0 = time.perf_counter()
        try:
            p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800)
            code = p.returncode
        except (OSError, subprocess.SubprocessError):
            code = 1
        times.append((time.perf_counter() - t0) * 1000.0)
    return code, times


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="性能预算（ISO 25010 性能效率面）")
    ap.add_argument("--record", action="store_true", help="实测并写证据")
    ap.add_argument("--only", default="all", help="all / <目标 id>（缺省 all）")
    ap.add_argument("--list", action="store_true", help="列声明与最近实测")
    args = ap.parse_args(argv)

    if args.list:
        doc, issues = pb.load(ROOT)
        for i in issues:
            print("  ✗ %s" % i, file=sys.stderr)
        if not doc:
            return 1
        ev = doc.get("evidence") or {}
        print("== 性能预算（%d 条） · 参考机 %s ==" % (len(doc.get("entries") or []),
                                                      doc.get("reference_host", "?")))
        for e in doc["entries"]:
            r = ev.get(e["id"]) or {}
            print("  %-16s 预算 %7.0f ms · %s"
                  % (e["id"], pb.budget_of(e), _rec_line(r)))
        return 0 if not issues else 1

    if args.record:
        bad, doc = pb.record(ROOT, only=args.only, runner=_runner)
        print("== 性能预算实测（only=%s） ==" % args.only)
        for eid, r in sorted((doc.get("evidence") or {}).items()):
            flag = "✗ 超预算" if eid in bad else "✓"
            print("  %s %-16s 中位 %7.0f · P95 %7.0f · σ %6.1f ms · 预算 %7.0f ms · exit=%s"
                  % (flag, eid, float(r.get("median_ms") or 0), float(r.get("p95_ms") or 0),
                     float(r.get("stdev_ms") or 0), float(r.get("budget_ms") or 0),
                     r.get("exit_code")))
        if bad:
            print("  ✗ 超预算：%s（修复指引：定位退化点或评审后调整预算）" % "、".join(bad),
                  file=sys.stderr)
        return 1 if bad else 0

    issues, warns, stats = pb.scan(ROOT)
    print("== 性能预算校验 ==")
    print("  声明 %d 条 · 有记录 %d 条 · 超预算 %d 条"
          % (stats["declared"], stats["recorded"], stats["over_budget"]))
    for w in warns:
        print("  [WARN] %s" % w)
    for i in issues[:10]:
        print("  ✗ %s" % i, file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓/✗ 即 UnicodeEncodeError（同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
