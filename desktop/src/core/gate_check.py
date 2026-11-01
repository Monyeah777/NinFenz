"""门禁执行编排：计划期定键 → 并行执行 → 按钉住的键落盘（秒级 check 的调度面）。

分层：本模块**不 spawn**，跑一个模块的动作由调用方注入（`invoke`）。
于是编排逻辑可以无进程测试，而真跑（subprocess + unittest）留给 CLI/测试入口。

三条纪律（与 gate_verdict 配套）：
  1. **先计划期定键，再并行执行**（并行期算键会被瞬态文件抖掉）；
  2. **命中即不跑**，但缓存的 FAIL 判定照样算红——绝不把红洗成绿；
  3. **不可缓存的节点每次真跑**（读面不可信时缓存=旧绿，见 gate_select.cacheable）；
     慢车道节点在快车道**让位**（打印名单，不静默跳过）。

判据：tests/test_gate_check.py
"""
from __future__ import annotations

import concurrent.futures as cf
import time
from pathlib import Path

from core import gate_select as gs
from core import gate_verdict as gv


def plan(changed, root: str = ".", faces=None, tests_dir=None, quick_only: bool = True,
         use_cache: bool = True) -> dict:
    """计划期：定键 + 查缓存（**此刻不应有任何测试在跑**）。"""
    tdir = Path(tests_dir) if tests_dir is not None else None
    got = gs.select(changed, doc=faces, tests_dir=tdir, root=root)
    faces = faces if faces is not None else gs.load_faces(root)
    picked = got["quick"] if quick_only else got["run"]
    cached, to_run, uncacheable = [], [], []
    for mod, _why in picked:
        rec = faces.get(mod) or {}
        reads = rec.get("reads") or []
        code = [f"desktop/tests/{mod}.py"]
        if not use_cache or not reads or not gs.cacheable(mod, rec, tdir):
            uncacheable.append(mod)
            to_run.append((mod, None))
            continue
        (hit, value), ckey, entry, tag = gv.lookup(mod, reads, root, code)
        if hit:
            cached.append((mod, value))
        else:
            to_run.append((mod, (tag, ckey, entry)))
    return {"cached": cached, "to_run": to_run, "uncacheable": uncacheable,
            "deferred": [m for m, _w in got["slow"]] if quick_only else [],
            "skipped": got["skip"], "run": got["run"], "quick": got["quick"]}


def _execute_one(job, invoke, timeout: int) -> tuple:
    mod, pinned = job
    rc, seconds = invoke(mod, timeout)
    if pinned is not None:
        gv.store(pinned[0], pinned[1], pinned[2], {"rc": rc, "seconds": seconds})
    return mod, rc, seconds


def execute(plan_doc: dict, invoke, workers: int = 6, timeout: int = 600) -> dict:
    """并行执行待跑集合；`invoke(mod, timeout) -> (rc, 秒数)`。"""
    jobs = list(plan_doc["to_run"])
    started = time.perf_counter()
    results: dict = {mod: int(value.get("rc", -1)) for mod, value in plan_doc["cached"]}
    fresh: list = []
    with cf.ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [pool.submit(_execute_one, job, invoke, timeout) for job in jobs]
        for fut in futures:
            mod, rc, seconds = fut.result()
            results[mod] = rc
            fresh.append((mod, rc, seconds))
    return {"results": results, "fresh": fresh, "cached": plan_doc["cached"],
            "uncacheable": plan_doc["uncacheable"], "deferred": plan_doc["deferred"],
            "wall": round(time.perf_counter() - started, 2)}


def failed(result: dict) -> list:
    """红名单（含缓存的 FAIL——它们同样是红）。"""
    return sorted(mod for mod, rc in result["results"].items() if rc != 0)


def check(changed, invoke, root: str = ".", workers: int = 6, timeout: int = 600,
          faces=None, tests_dir=None, quick_only: bool = True,
          use_cache: bool = True) -> dict:
    """一步式：计划 → 执行 → 汇总。"""
    plan_doc = plan(changed, root=root, faces=faces, tests_dir=tests_dir,
                    quick_only=quick_only, use_cache=use_cache)
    result = execute(plan_doc, invoke, workers=workers, timeout=timeout)
    result["failed"] = failed(result)
    result["planned"] = len(plan_doc["cached"]) + len(plan_doc["to_run"])
    result["skipped"] = plan_doc["skipped"]
    return result

