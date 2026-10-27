"""CLI 处理器：daemon 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from nf_cmds.common import ROOT, _machine_fail, _portable_path


def _daemon_start(args) -> int:
    from core import daemon as dm

    ok, msg = dm.start(Path(ROOT), idle_timeout=args.idle,
                       watch=bool(getattr(args, "watch", False)))
    doc = dm.read_state() or {}
    print(("  ✓ " if ok else "  ✗ ") + msg)
    if ok:
        # 缓存/监听是**守护进程内**的状态，必须在守护侧取（客户端进程里看不到）。
        st = dm.query_stats(doc)
        if st is None:
            print("  响应缓存：无法查询（守护未响应 stats）")
        elif st.get("enabled"):
            print("  响应缓存：已启用（树没变即整条复用；代际 %s）" % st.get("generation"))
        else:
            print("  响应缓存：未启用（目录监听不可用——平台未实现或打开失败，已自动降级）")
    if ok:
        print("  端口 %s · 状态文件 %s"
              % (doc.get("port"), _portable_path(dm.state_path())))
    return 0 if ok else 1


def _daemon_stop(args) -> int:
    from core import daemon as dm

    ok, msg = dm.stop()
    print(("  ✓ " if ok else "  · ") + msg)
    return 0 if ok else 1


def _daemon_status(args) -> int:
    import json as _json
    import time as _time

    from core import daemon as dm

    t0 = _time.perf_counter()
    alive = dm.ping()
    rtt = (_time.perf_counter() - t0) * 1000
    doc = dm.read_state() or {}
    if args.json:
        print(_json.dumps({"kind": "nf-daemon", "running": bool(alive),
                           "port": doc.get("port"), "pid": doc.get("pid"),
                           "proto": doc.get("proto"),
                           "root": _portable_path(doc.get("root")),
                           "rtt_ms": round(rtt, 2) if alive else None,
                           "cache": dm.query_stats(doc) if alive else None,
                           "state_file": _portable_path(dm.state_path())},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if alive else 1
    print("== nf daemon（执行层常驻守护）==")
    print("  状态：%s" % ("在线" if alive else "未运行"))
    if doc:
        print("  端口 %s · pid %s · proto %s" % (doc.get("port"), doc.get("pid"),
                                                 doc.get("proto")))
        print("  仓库根：%s" % _portable_path(doc.get("root")))
    print("  状态文件：%s" % _portable_path(dm.state_path()))
    if alive:
        print("  往返时延：%.1f ms（同一进程内热跑；含协议解析与源码指纹比对）" % rtt)
        st = dm.query_stats(doc)
        if st is None:
            print("  响应缓存：无法查询（守护未响应 stats）")
        elif st["enabled"]:
            print("  响应缓存：已启用 · 代际 %s · 条目 %d · 命中 %d / 未命中 %d（树一变即整批作"
                "废）"
                  % (st["generation"], st["entries"], st["hits"], st["misses"]))
        else:
            print("  响应缓存：未启用（未开 --watch，或目录监听不可用——行为与常规守护一致）")
    else:
        print("  → 拉起：nf daemon start（或用 scripts/nf 启动器，它会自动走守护）")
    return 0 if alive else 1


def _daemon_exec(args) -> int:
    from core import daemon as dm

    argv = [str(a) for a in (args.argv or [])]
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("  ✗ 缺命令（用法：nf daemon exec stats --check）", file=sys.stderr)
        return 2
    doc = dm.read_state()
    if not (doc and dm.ping(doc)):
        if getattr(args, "no_start", False):
            print("  ✗ 守护不在运行（--no-start）", file=sys.stderr)
            return 1
        ok, msg = dm.start(Path(ROOT))
        if not ok:
            print("  ✗ " + msg, file=sys.stderr)
            return 1
        doc = dm.read_state()
    try:
        code, out, err = dm.run_request(doc, argv)
    except OSError as exc:
        return _machine_fail(
            args, "守护未响应：%s（修复指引：nf daemon start 后重试）" % exc, 1)
    sys.stdout.write(out.decode("utf-8", "replace"))
    sys.stderr.write(err.decode("utf-8", "replace"))
    return code


def _daemon_shell_init(args) -> int:
    from core import daemon as dm

    # 零子进程客户端：当前 shell 内一次函数调用 + 一次套接字往返（真毫秒级）。
    # `--shell` 与位置参数是同一件事的两种拼法；**此前两者都没被读**（`--shell` 声明了
    # 却没人用 = 传了也没用的静默空转，2026-10-01 判据扫描抓到）——现统一读一处，
    # 声明面与执行面同源；目前只支持 bash（choices 已限，后端也只有 BASH 变体）。
    shell = str(getattr(args, "shell_opt", None) or getattr(args, "shell", None) or "bash")
    if shell != "bash":
        return _machine_fail(
            args, "--shell 目前只支持 bash（修复指引：`eval \"$(nf daemon shell-init "
                  "bash)\"`；其它 shell 需先落对应启动脚本后端）", 2)
    print(dm.SHELL_INIT_BASH.replace("{py}", sys.executable).replace("{root}", ROOT),
          end="")
    return 0


def _daemon_bench(args) -> int:
    import json as _json
    import subprocess as _sp
    import time as _time

    from core import daemon as dm

    probes = (["--version"], ["stats", "--check"], ["layers", "--verify"], ["doctor"])
    doc = dm.read_state()
    if not (doc and dm.ping(doc)):
        ok, msg = dm.start(Path(ROOT))
        if not ok:
            return _machine_fail(args, msg, 1)
        doc = dm.read_state()
    if not (doc and dm.ping(doc)):
        # 守护拉起后仍不可达：机器面须是失败信封，不许冒内部错误（2026-10-10 CI 实测：
        # 无守护时 daemon bench --json 会抛 WinError 10061 连接被拒，stdout 非 JSON）。
        return _machine_fail(
            args, "守护未就绪（已尝试拉起但不可达）（修复指引：先 nf daemon stop 清掉"
                  "陈旧状态后重试，或稍后重跑）", 1)
    rows = []
    for argv in probes:
        cold = []
        for _ in range(max(1, args.runs)):
            t0 = _time.perf_counter()
            _sp.run([sys.executable, os.path.join(ROOT, "scripts", "nf.py")] + argv,
                    cwd=ROOT, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            cold.append((_time.perf_counter() - t0) * 1000)
        warm = []
        for _ in range(max(1, args.runs)):
            t0 = _time.perf_counter()
            try:
                dm.run_request(doc, argv)
            except OSError as exc:
                return _machine_fail(
                    args, "守护未响应（%s）：%s（修复指引：nf daemon start 后重试）"
                          % (" ".join(argv), exc), 1)
            warm.append((_time.perf_counter() - t0) * 1000)
        rows.append({"argv": argv, "cold_ms": round(min(cold), 1),
                     "daemon_ms": round(min(warm), 1),
                     "speedup": round(min(cold) / max(min(warm), 0.001), 1)})
    if args.json:
        print(_json.dumps({"kind": "nf-daemon-bench", "runs": max(1, args.runs),
                           "probes": rows}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("== nf daemon bench（直跑 vs 守护，取 %d 次最小）==" % max(1, args.runs))
    print("  %-22s %10s %10s %8s" % ("命令", "直跑 ms", "守护 ms", "加速"))
    for r in rows:
        print("  %-22s %10.1f %10.1f %7.1fx"
              % (" ".join(r["argv"]), r["cold_ms"], r["daemon_ms"], r["speedup"]))
    return 0


def run(args) -> int:
    """nf daemon：执行层常驻守护（毫秒级响应）。

    动机（实测）：裸解释器启动 146 ms、`nf --version` 401 ms——每条命令有 ~400 ms 固定成本；
    热进程内同一命令只要 1–5 ms。故把命令执行搬进常驻进程，客户端只做一次往返。
    """
    sub = args.daemon_cmd
    if sub == "start":
        return _daemon_start(args)
    if sub == "stop":
        return _daemon_stop(args)
    if sub == "status":
        return _daemon_status(args)
    if sub == "exec":
        return _daemon_exec(args)
    if sub == "shell-init":
        return _daemon_shell_init(args)
    if sub == "bench":
        return _daemon_bench(args)
    print("  ✗ 未知 daemon 子命令：%s" % sub, file=sys.stderr)
    return 2
