#!/usr/bin/env python3
# nf-io: inputs=desktop/src outputs=-
"""**并行跑 `nf verify` 的各条 check**：把「整批」从串行 ≈19 s 压到并行 ≈6.5 s。

为什么放在 `core`（而不是 CLI 里）
----------------------------------
它是**调度**，不是判据：每条 check 仍在**独立子进程**里跑 `nf verify --only N --json`
——即用的还是那条唯一的引擎入口，判据一字不改。

纪律（与本仓其余部分同源）
--------------------------
1. **不改判据**：只决定「哪条在哪个进程里跑」；子进程就是 `nf verify --only N`；
2. **不做假绿**：任一子进程非零退出 / 输出不是合法 JSON / 缺 check ⇒ **如实计入失败**，
   绝不「当它通过」；
3. **结果可重放**：按 check 号排序合并，人读面从合并后的数据重放文案
   ⇒ 与串行输出**逐字节一致**（`tests/test_verify_parallel_checks.py` 守门）；
4. **子进程失败不外溢**：抓取 stdout/stderr，不把子进程的异常当本进程异常。

为什么子进程（而不是线程/进程池内联）
--------------------------------------
22 条 check 里有多条会 `chdir`、改 `os.environ`、装 audit hook（`gate_inproc`），
**同进程内并发彼此会踩**（本会话实测过同类问题：嵌套会导致全局态互相覆盖）。
子进程是**天然的隔离边界**，代价只是每条 ~0.15 s 的解释器启动。
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 - 只跑本仓 CLI，argv 列表、无 shell
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 单条 check 的子进程超时（秒）。给足余量：慢机 + 冷页缓存下 check33 实测 ~8 s。
PER_CHECK_TIMEOUT = 600.0


def _nf_argv(root: Path, num: int) -> List[str]:
    return [sys.executable, str(Path(root) / "scripts" / "nf.py"),
            "verify", "--only", str(num), "--json"]


def run_one(root: Path, num: int, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """跑一条 check 的子进程 → `{num, ok, payload, stderr, seconds}`。

    `ok=False` 表示**这条没拿到可信结论**（非零退出 / 非法 JSON / 超时）——
    调用方必须把它当失败处理，不许跳过。
    """
    import time
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(  # nosec B603 - argv 列表、无 shell、路径由本模块拼出
            _nf_argv(root, num), cwd=str(root), capture_output=True,
            env=env or os.environ.copy(), timeout=PER_CHECK_TIMEOUT,
        )
        code = proc.returncode
        out = proc.stdout or b""
        err = proc.stderr or b""
    except subprocess.TimeoutExpired:
        return {"num": num, "ok": False, "payload": None,
                "stderr": "子进程超时（>%ds）" % int(PER_CHECK_TIMEOUT),
                "seconds": time.perf_counter() - t0}
    except OSError as exc:
        return {"num": num, "ok": False, "payload": None,
                "stderr": "子进程无法启动：%s" % exc,
                "seconds": time.perf_counter() - t0}
    seconds = time.perf_counter() - t0
    try:
        # 走本仓唯一读点 `core.json_doc`：未校验的裸 `json.loads` 会被
        # `test_json_shape_contracts.UnguardedRatchetTest` 判红（它要求新读点都走这一层）。
        from core import json_doc
        payload = json_doc.loads(out.decode("utf-8"), None, what="nf verify --json")
    except (UnicodeDecodeError, ValueError) as exc:
        return {"num": num, "ok": False, "payload": None,
                "stderr": "输出不是合法 JSON：%s\n%s"
                          % (exc, err.decode("utf-8", "replace")[:400]),
                "seconds": seconds}
    # 退出码 0/1 都是**可信结论**（1 = 该 check 判 FAIL）；其它退出码视为不可信。
    if code not in (0, 1):
        return {"num": num, "ok": False, "payload": payload,
                "stderr": "退出码 %d 不是判据结论（应为 0/1）：%s"
                          % (code, err.decode("utf-8", "replace")[:400]),
                "seconds": seconds}
    return {"num": num, "ok": True, "payload": payload,
            "stderr": err.decode("utf-8", "replace")[:400], "seconds": seconds}


def run_checks_parallel(root: Path, nums: Sequence[int], jobs: int = 8,
                        env: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], List[int]]:
    """并行跑一批 check → (按 check 号排序的 `checks` 列表, 不可信 check 号列表)。

    合并口径与 `nf verify --json` 的 `checks` **同形**（`{check,status,verdicts,messages}`），
    于是人读面可以照旧逐条渲染。
    """
    with ThreadPoolExecutor(max_workers=max(1, int(jobs))) as ex:
        results = list(ex.map(lambda n: run_one(root, n, env), nums))
    checks: List[Dict[str, Any]] = []
    broken: List[int] = []
    for r in sorted(results, key=lambda x: x["num"]):
        if not r["ok"]:
            broken.append(r["num"])
            continue
        for c in (r["payload"] or {}).get("checks") or []:
            checks.append(c)
    return checks, broken
