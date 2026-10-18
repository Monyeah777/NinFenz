#!/usr/bin/env python3
"""check12 的测试执行器：**按测试粒度分片并行**（只改执行方式，不改任何判据）。

为什么（2026-10-17 实测）：check12 = 3100+ tests / ~1080 s，占全量门禁 95%；单进程串行是纯
执行成本。隔离修好后（`desktop/tests/__init__.py`：NF_HOME 兜底临时目录；守护端口由内核分配），
测试之间不再共享状态，于是可把同一批测试放进 N 个进程——判据一条不动。

纪律（写进判据，不是口头承诺）：
1. **全集等价**：分片里的测试 id 由**一次 discover**产出，逐项分完（不按文件名猜），
   分片并集必须逐项等于 discover 集，否则 exit 1；
2. **失败不被吞**：任一分片非零即整体非零，并打印该分片末 40 行；
3. **可回退**：`--jobs 1` = 串行口径（排障用）；`NF_TEST_JOBS=1` 同义；
4. **可复现分片**：按「历史耗时 LPT（并列按测试 id）」分配，同输入必得同一分片；
5. **不猜权重**：权重来自 `protocol/check12_weights.json`（`--write-weights` 实测生成），
   缺文件按均匀权重——只影响均衡，不影响判据。

用法：
    python scripts/verify_tests.py                    # 默认 jobs=4（或 NF_TEST_JOBS）
    python scripts/verify_tests.py --jobs 1           # 串行（等价历史 discover）
    python scripts/verify_tests.py --write-weights    # 逐模块实测 → 写权重（棘轮基线）
    python scripts/verify_tests.py --list             # 只打印发现到的测试数
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "desktop"
TESTS = DESKTOP / "tests"
WEIGHTS_REL = "protocol/check12_weights.json"
SHARD_TIMEOUT_S = 5400.0

#: 落盘一律走 core.atomic_write（脚本面纪律：不得有裸写 sink）；权重是**仓内**协议件。
sys.path.insert(0, str(DESKTOP / "src"))
from core import atomic_write  # noqa: E402 - 先用后置（scripts 面统一写法）


def discover_ids() -> list:
    """一次 discover → 全部测试 id（与 unittest 默认 pattern 同口径）。"""
    sys.path.insert(0, str(DESKTOP))
    suite = unittest.TestLoader().discover(str(TESTS), pattern="test*.py")
    ids = []

    def walk(node):
        if isinstance(node, unittest.TestSuite):
            for child in node:
                walk(child)
        else:
            ids.append(node.id())

    walk(suite)
    return sorted(set(ids))


def module_of(test_id: str) -> str:
    """test id → 模块名（`test_x.Class.test_y` 与 `tests.test_x...` 都归一为 `test_x`）。

    discover 的 top_level_dir 是 tests 目录，故真实 id 形如 `test_x.Class.test_y`（无包前缀）；
    两种形态都归一，权重键与 `--mods` 过滤因此稳定。
    """
    parts = test_id.split(".")
    if parts and parts[0] == "tests" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else ""


def load_weights() -> dict:
    try:
        doc = json.loads((ROOT / WEIGHTS_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("modules") if isinstance(doc, dict) else None
    return {str(k): float(v) for k, v in (rows or {}).items() if isinstance(v, (int, float))}


def test_weights(ids: list, weights: dict) -> dict:
    """每测试权重 = 所属模块实测耗时 / 该模块测试数（模块内均分；缺数据按 1.0）。"""
    per_module = {}
    for tid in ids:
        per_module.setdefault(module_of(tid), []).append(tid)
    out = {}
    for mod, group in per_module.items():
        share = weights.get(mod, float(len(group))) / max(1, len(group))
        for tid in group:
            out[tid] = share
    return out


def assign(ids: list, ws: dict, jobs: int) -> list:
    """LPT：按权重降序塞进当前最轻的分片（并列按测试 id，保证确定性）。"""
    bins = [[] for _ in range(jobs)]
    load = [0.0] * jobs
    for tid in sorted(ids, key=lambda x: (-ws.get(x, 1.0), x)):
        i = min(range(jobs), key=lambda k: (load[k], k))
        bins[i].append(tid)
        load[i] += ws.get(tid, 1.0)
    return bins


def run_shard(ids: list, index: int) -> dict:
    """跑一个分片：测试清单与 NF_HOME 都放在 TemporaryDirectory 里（自动清理，不写删文件 sink）。"""
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="nf_shard_%d_" % index) as spec_dir:
        spec = Path(spec_dir) / "tests.json"
        atomic_write.write_text(spec, json.dumps({"tests": ids}, ensure_ascii=False))
        with tempfile.TemporaryDirectory(prefix="nf_shard_home_%d_" % index) as home:
            env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                       NARRATIVE_FORGE_HOME=home)
            try:
                proc = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--run-shard", str(spec)],
                    cwd=str(DESKTOP), env=env, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=SHARD_TIMEOUT_S)
                rc, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired:
                rc, out = 124, "分片超时（%.0f s）" % SHARD_TIMEOUT_S
    return {"index": index, "rc": rc, "out": out,
            "wall": round(time.perf_counter() - t0, 1), "tests": len(ids)}


def run_shard_mode(spec_path: str) -> int:
    """子进程侧：按测试 id 清单跑。"""
    sys.path.insert(0, str(DESKTOP))
    sys.path.insert(0, str(TESTS))
    tests = json.loads(Path(spec_path).read_text(encoding="utf-8"))["tests"]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for tid in tests:
        suite.addTests(loader.loadTestsFromNames([tid]))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def measure_weights(ids: list) -> dict:
    """逐模块实测（每模块一个子进程）→ {module: seconds}。"""
    per_module = {}
    for tid in ids:
        per_module.setdefault(module_of(tid), []).append(tid)
    out = {}
    mods = sorted(per_module)
    for i, mod in enumerate(mods, 1):
        res = run_shard(per_module[mod], i)
        out[mod] = round(res["wall"], 2)
        print("  [%3d/%3d] %7.1f s  %s" % (i, len(mods), res["wall"], mod), flush=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="check12 分片执行器")
    ap.add_argument("mods", nargs="*", help="只跑这些模块（排障用；缺省=全量 discover）")
    ap.add_argument("--jobs", type=int, default=0,
                    help="分片数（0=读 NF_TEST_JOBS，缺省 4；1=串行）")
    ap.add_argument("--write-weights", action="store_true",
                    help="逐模块实测并写 protocol/check12_weights.json")
    ap.add_argument("--list", action="store_true", help="只打印发现的测试数")
    ap.add_argument("--run-shard", default="", help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true", help="输出结构化摘要")
    args = ap.parse_args(argv)

    if args.run_shard:
        return run_shard_mode(args.run_shard)

    ids = discover_ids()
    if args.mods:
        want = {m[len("tests."):] if m.startswith("tests.") else m for m in args.mods}
        ids = [t for t in ids if module_of(t) in want]
        if not ids:
            print("指定模块里没有测试：%s（修复指引：模块名形如 tests.test_xxx）"
                  % ", ".join(sorted(want)), file=sys.stderr)
            return 2
    if args.list:
        print(json.dumps({"tests": len(ids), "modules": len({module_of(t) for t in ids})},
                         ensure_ascii=False))
        return 0

    if args.write_weights:
        t0 = time.perf_counter()
        measured = measure_weights(ids)
        doc = {"schema": "nf-check12-weights/1",
               "note": "check12 逐模块墙钟基线（--write-weights 实测；P0 棘轮与分片均衡共用）",
               "measured_at": time.strftime("%Y-%m-%d"),
               "total_s": round(sum(measured.values()), 1),
               "modules": measured}
        atomic_write.write_text(
            ROOT / WEIGHTS_REL,
            json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print("  ✓ 权重已写入 %s：模块 %d · 合计 %.1f s（墙钟 %.1f s）"
              % (WEIGHTS_REL, len(measured), doc["total_s"],
                 time.perf_counter() - t0))
        return 0

    jobs = args.jobs or int(os.environ.get("NF_TEST_JOBS") or 4)
    jobs = max(1, min(jobs, len(ids)))
    ws = test_weights(ids, load_weights())
    bins = assign(ids, ws, jobs)
    flat = [t for b in bins for t in b]
    if sorted(flat) != ids:
        print("分片测试集与 discover 不一致（漏/重）：%d vs %d" % (len(flat), len(ids)),
              file=sys.stderr)
        return 1

    t0 = time.perf_counter()
    if jobs == 1:
        results = [run_shard(bins[0], 0)]
    else:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=len(bins)) as ex:
            results = [f.result() for f in [ex.submit(run_shard, b, i)
                                            for i, b in enumerate(bins)]]
    wall = time.perf_counter() - t0
    failed = [r for r in results if r["rc"] != 0]

    if args.json:
        print(json.dumps({"schema": "nf-verify-tests/1", "jobs": jobs,
                          "wall_s": round(wall, 1), "tests": len(ids),
                          "failed_shards": len(failed),
                          "shards": [{"index": r["index"], "rc": r["rc"],
                                      "wall_s": r["wall"], "tests": r["tests"]}
                                     for r in results]},
                         ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for r in results:
            tail = " ".join(r["out"].strip().splitlines()[-1:])[:110]
            print("  分片%d：测试 %d · %.1f s · rc=%d  %s"
                  % (r["index"], r["tests"], r["wall"], r["rc"], tail))
        print("  合计 %d 条测试 · %d 分片 · 墙钟 %.1f s" % (len(ids), jobs, wall))
    for r in failed:
        print("---- 分片%d 失败（rc=%d）末 40 行 ----" % (r["index"], r["rc"]), file=sys.stderr)
        print("\n".join((r["out"] or "").splitlines()[-40:]), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    # stdio 钉 UTF-8：Windows 控制台 GBK 下 ✓ 即 UnicodeEncodeError（仓库约定同 nf.py）
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
