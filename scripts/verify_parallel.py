#!/usr/bin/env python3
# nf-io: inputs=desktop/tests outputs=-
"""**并行跑测试套件**（L-D）：按模块切分、多进程执行、汇总成 unittest 同形结论。

为什么需要（实测）
------------------
门禁 check12 就是 `python -m unittest discover -s tests`，全量实测 **1255 s（≈21 分钟）**，
是全量门禁的绝对主峰。而其中两个最大头是**真实工作量**、已无法再去重或内化：

- `test_daemon_parity`（~200 s）：必须起真进程做「直跑 vs 守护」对账；
- `test_cli_error_framing`（108.7 s）：逐个无参扫 157 条命令路径。

⇒ 唯一剩下的杠杆是**并行**（本机 20 核，CI runner 4 核）。

纪律（三条，与门禁其余部分同源）
--------------------------------
1. **不改任何判据**：本脚本只决定「谁在哪个进程里跑」，不碰断言、不跳用例、
   **不用 `-k`/`--ignore` 排除任何模块**；
2. **不做假绿**：任一模块非零退出即计 FAIL；子进程崩溃/超时**如实计入**并保留其输出；
3. **输出与串行同形**：逐模块打印 `Ran N tests` 与 `FAIL/ERROR:` 行，
   便于与 `python -m unittest discover` 的结论**逐条对照**（这是等价性证据的取数方式）。

用法
----
    python scripts/verify_parallel.py                 # 默认 8 路
    python scripts/verify_parallel.py -j 4            # 指定并行度（CI 4 核用）
    python scripts/verify_parallel.py --serial        # 串行（对照/取证用）
    python scripts/verify_parallel.py --json          # 机器面
退出码：0 = 全绿；1 = 有 FAIL/ERROR；2 = 用法或环境错误。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess  # nosec B404 - 只跑本仓测试模块（argv 列表、无 shell）
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "desktop" / "tests"
#: 逐模块跑：与 `unittest discover` 的口径一致（模块级隔离，不是用例级）。
_RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
_BAD = re.compile(r"^(FAIL|ERROR): (\S+)", re.M)

#: **独占跑**的模块（并行段全部结束后再串行跑它们）。
#:
#: 判据（2026-10-16 实测得出）：**执行层守护是每 `NF_HOME` 一个的全局单例**——
#: `nf daemon start/stop` 影响的是整个用户态环境，而不是某个测试的私有资源。
#: 这些模块会拉起/停掉它，并行跑时实测出现「A 模块停守护、B 模块正在读帧」⇒
#: `daemon.read_framed` 读到空行崩掉（`test_daemon_parity` 因此报
#: `readinto` 异常，单模块墙钟被拖到 498 s）。
#: 这不是代码缺陷，而是**共享单例资源**的必然——故串行段是**正确性要求**，不是性能妥协。
EXCLUSIVE = (
    "test_daemon",            # 38 处守护相关
    "test_daemon_limits",     # 3 处
    "test_daemon_parity",     # 28 处（直跑 vs 守护逐字节对账）
    "test_launcher",          # 39 处（启动器快路依赖守护在场）
    "test_session_watch",     # 2 处（与守护共用 response_cache）
    "test_watch",             # 11 处（响应缓存 + 目录监听）
    # 2026-10-17 实测补入：这两个模块会**遍历整条 CLI 面**，其中 `daemon bench` 等子命令
    # 直接打守护单例。并行时实测 `daemon bench --json` 会回来一个**没有面判别键**的降级
    # dict（另一个 worker 刚起/停了守护）⇒ `test_every_runnable_json_face_is_self_describing`
    # 红，而单跑该模块是绿的。
    "test_cli_json_face",
    "test_cli_error_framing",
)


def _modules() -> list[str]:
    return sorted(p.stem for p in TESTS.glob("test_*.py"))


def _run_one(mod: str, timeout: float) -> dict:
    """跑一个测试模块 → {mod, rc, ran, bad, out, seconds}。"""
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # nosec B603 - argv 列表、无 shell、路径由本模块枚举
            [sys.executable, "-m", "unittest", "tests.{}".format(mod), "-v"],
            cwd=str(ROOT / "desktop"), env=env, capture_output=True,
            timeout=timeout,
        )
        rc, out = proc.returncode, (proc.stdout or b"") + (proc.stderr or b"")
        note = ""
    except subprocess.TimeoutExpired as exc:
        rc = -9
        out = (exc.stdout or b"") + (exc.stderr or b"")
        note = "模块超时（>{}s）".format(int(timeout))
    except OSError as exc:                       # 环境问题：如实计入，不当通过
        rc, out, note = -1, b"", "无法启动子进程：{}".format(exc)
    text = out.decode("utf-8", "replace")
    m = _RAN.search(text)
    return {
        "mod": mod,
        "rc": rc,
        "ran": int(m.group(1)) if m else 0,
        "bad": [b[1] for b in _BAD.findall(text)],
        "seconds": time.perf_counter() - t0,
        "note": note,
        "text": text,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="并行跑测试套件（只改调度，不改判据）")
    ap.add_argument("-j", "--jobs", type=int, default=8, help="并行度（缺省 8）")
    ap.add_argument("--timeout", type=float, default=1800.0, help="单模块超时秒数")
    ap.add_argument("--serial", action="store_true", help="串行（对照用）")
    ap.add_argument("--json", action="store_true", help="机器面")
    ap.add_argument("--exclusive", default=",".join(EXCLUSIVE),
                    help="**独占跑**的模块（逗号分隔）：它们与全局单例资源打交道，"
                         "并行会互相踩；缺省见 EXCLUSIVE")
    a = ap.parse_args(argv)

    mods = _modules()
    if not mods:
        print("找不到测试模块（{}）".format(TESTS), file=sys.stderr)
        return 2

    exclusive = {m for m in (x.strip() for x in a.exclusive.split(",")) if m}
    # 独占件从并行集里摘出来（顺序仍按字母序，保证可复现）
    excl_mods = [m for m in mods if m in exclusive]
    par_mods = [m for m in mods if m not in exclusive]

    t0 = time.perf_counter()
    if a.serial:
        results = [_run_one(m, a.timeout) for m in mods]
    else:
        with cf.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
            results = list(ex.map(lambda m: _run_one(m, a.timeout), par_mods))
        # 独占段**在并行段全部结束之后**串行跑：不与任何模块并发。
        # 为什么必须如此（2026-10-16 实测）：守护是**每 NF_HOME 一个**的全局单例，
        # 而多个模块都会拉起/停掉它（test_daemon_parity / test_daemon / test_watch …）。
        # 并行时实测出现「一个模块停守护、另一个模块的请求正在读帧」⇒
        # `read_framed` 读到空行崩掉（test_daemon_parity 的 498 s 里就挂在这）。
        # 这不是代码缺陷，是**共享单例资源**的必然：故串行段是正确性要求，不是妥协。
        results += [_run_one(m, a.timeout) for m in excl_mods]
    wall = time.perf_counter() - t0

    total = sum(r["ran"] for r in results)
    bad = [r for r in results if r["rc"] != 0]
    bad_marks = [(r["mod"], b) for r in results for b in r["bad"]]

    if a.json:
        print(json.dumps({
            "modules": len(mods), "ran": total, "wall_seconds": round(wall, 3),
            "jobs": 1 if a.serial else a.jobs,
            "failed_modules": [{"mod": r["mod"], "rc": r["rc"], "note": r["note"],
                                "bad": r["bad"]} for r in bad],
            "bad_marks": bad_marks,
        }, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for r in results:
            if r["rc"] != 0:
                print("=" * 70)
                print("模块 {} 退出码 {} {}".format(r["mod"], r["rc"], r["note"]))
                print(r["text"].rstrip()[-4000:])
        print("=" * 70)
        mode = "serial" if a.serial else "{} jobs".format(a.jobs)
        print("Ran {} tests across {} modules using {}（wall {:.1f}s）".format(
            total, len(mods), mode, wall))
        for mod, mark in bad_marks:
            print("{}: {}".format(mark, mod))
        tail = "" if not bad else "：" + " ".join(r["mod"] for r in bad)
        print(("FAILED" if bad else "OK")
              + "（失败模块 {} 个{}）".format(len(bad), tail))
    return 1 if bad else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
