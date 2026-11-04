#!/usr/bin/env python3
"""发布结论一键复跑（release conclusion）：干净树 → checks-only → N 分片 → 汇总。

为什么有它（2026-11-04 实测教训）：verify.sh 的 full 档单进程在本机要 35–40 分钟；
而发布结论只要求「check1-42 全过」。本脚本把这件事拆成三步可复跑，并把**我自己踩过的坑**
做成闸门：

- **脏树直接拒跑**：在改到一半的树上跑分片会产生「与输入无关的假红」（实测：文档改到一半
  去跑分片，报了一堆 conformance/living-docs 失败，全是中间态）。脏树时按 rc=2 退出。
- **先跑 checks-only**：快、抓结构性红（结构/契约/回执/纯度），失败就不必再花 40 分钟跑测试。
- **分片并行 + 并集断言**：执行器自带「分片并集 == discover 全集」断言，因此分片跑与全量跑
  判据等价；并行只改墙钟。

用法：
  python scripts/release_conclusion.py                # 缺省 8 分片并行
  python scripts/release_conclusion.py --jobs 4       # 并发数（缺省取 8）
  python scripts/release_conclusion.py --dry-run      # 只打印计划，不执行
  python scripts/release_conclusion.py --json         # 机读汇总
与 nf release（发布编排/冻结链）分工：那个管「按什么次序冻结」，本件管「冻结后能不能发布」。
执行器：bash verify.sh --checks-only + python scripts/verify_tests.py --shard i/n
退出码：0 全过 / 1 有失败 / 2 前置不满足（脏树、参数错）。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SHARDS = 8
GUIDE = "修复指引："


def porcelain_lines(text: str) -> list[str]:
    """git status --porcelain 输出 → 非空行列表（脏树判据的纯函数，便于单测）。"""
    return [ln for ln in (text or "").splitlines() if ln.strip()]


def dirty_guard(lines: list[str], allow_dirty: bool) -> str:
    """脏树闸门 → 拒绝原因（空串 = 放行）。"""
    if not lines or allow_dirty:
        return ""
    sample = "；".join(ln.strip() for ln in lines[:5])
    return (f"工作树不干净（{len(lines)} 处变更：{sample}）（{GUIDE}先提交或收干净再跑——"
            "在改到一半的树上跑分片会产生与输入无关的假红；确需跑加 --allow-dirty）")


def aggregate(results: list[dict]) -> dict:
    """分片结果汇总 → {ok, total, failed, wall}（纯函数，便于单测）。"""
    failed = [r for r in results if int(r.get("rc") or 0) != 0]
    return {"ok": bool(results) and not failed,
            "total": len(results),
            "failed": [{"shard": r.get("shard"), "rc": r.get("rc")} for r in failed],
            "wall": round(sum(float(r.get("wall") or 0.0) for r in results), 1)}


def _run(argv: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def _git_status() -> list[str]:
    try:
        proc = _run(["git", "status", "--porcelain"], 120)
    except (OSError, subprocess.SubprocessError):
        return []
    return porcelain_lines(proc.stdout)


def _step_checks_only(verbose: bool) -> tuple[int, float]:
    t0 = time.perf_counter()
    if verbose:
        print("[1/2] bash verify.sh --checks-only …", flush=True)
    try:
        proc = _run(["bash", "verify.sh", "--checks-only"], 3600)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"  ✗ checks-only 起不来：{exc}", file=sys.stderr)
        return 1, time.perf_counter() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = [ln for ln in out.splitlines() if ln.strip()][-1:]
    if verbose:
        print(f"  => rc={proc.returncode} · {tail[0] if tail else '（无输出）'}", flush=True)
    return int(proc.returncode), time.perf_counter() - t0


def _shard_one(index: int, total: int) -> dict:
    t0 = time.perf_counter()
    argv = [sys.executable, "scripts/verify_tests.py", "--shard",
            f"{index}/{total}", "--json"]
    try:
        proc = _run(argv, 3600)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"shard": f"{index}/{total}", "rc": 1,
                "wall": round(time.perf_counter() - t0, 1), "detail": str(exc)}
    return {"shard": f"{index}/{total}", "rc": int(proc.returncode),
            "wall": round(time.perf_counter() - t0, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="release_conclusion",
                                 description="发布结论一键复跑（干净树 → checks-only → 分片）")
    ap.add_argument("--jobs", type=int, default=DEFAULT_SHARDS,
                    help=f"并发分片数（缺省 {DEFAULT_SHARDS}；1 = 串行）")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="允许在脏树上跑（默认拒绝：脏树会产生与输入无关的假红）")
    ap.add_argument("--skip-checks", action="store_true", help="跳过 checks-only 步骤")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    ap.add_argument("--json", action="store_true", help="机读汇总")
    args = ap.parse_args(argv)

    jobs = max(1, min(int(args.jobs), DEFAULT_SHARDS * 2))
    plan = {"root": str(ROOT), "shards": jobs, "checks_only": not args.skip_checks,
            "steps": ["git status --porcelain", "bash verify.sh --checks-only"]
                     + [f"python scripts/verify_tests.py --shard {i}/{jobs}"
                        for i in range(jobs)]}

    dirty = _git_status()
    blocked = dirty_guard(dirty, args.allow_dirty)
    if args.dry_run:
        payload = {"schema": "nf-release-conclusion/1", "dry_run": True, "plan": plan,
                   "dirty": dirty, "blocked": blocked}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not blocked else 2
    if blocked:
        print(f"  ✗ {blocked}", file=sys.stderr)
        return 2
    if dirty:
        print(f"  [WARN] 脏树放行（{len(dirty)} 处变更）——结果可能含中间态假红",
              file=sys.stderr)

    t0 = time.perf_counter()
    checks_rc = 0
    if not args.skip_checks:
        checks_rc, _checks_wall = _step_checks_only(not args.json)
        if checks_rc != 0:
            payload = {"schema": "nf-release-conclusion/1", "ok": False,
                       "checks_only_rc": checks_rc,
                       "note": "checks-only 未过：结构性红不必再花时间跑测试",
                       "wall": round(time.perf_counter() - t0, 1)}
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                  if args.json else "  ✗ checks-only 未过 → 停止")
            return 1

    if not args.json:
        print(f"[2/2] 分片 ×{jobs}（并发 {jobs}）…", flush=True)
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(_shard_one, i, jobs) for i in range(jobs)]
        for fut in concurrent.futures.as_completed(futures):
            row = fut.result()
            results.append(row)
            if not args.json:
                mark = "✓" if row["rc"] == 0 else "✗"
                print(f"  {mark} 分片 {row['shard']} · rc={row['rc']} · {row['wall']} s",
                      flush=True)
    summary = aggregate(results)
    payload = {"schema": "nf-release-conclusion/1", "ok": summary["ok"] and checks_rc == 0,
               "checks_only_rc": checks_rc,
               "shards": sorted(results, key=lambda r: r["shard"]),
               "failed": summary["failed"], "shard_wall_s": summary["wall"],
               "wall_s": round(time.perf_counter() - t0, 1)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== 发布结论 ==")
        print(f"  checks-only：rc={checks_rc}")
        print(f"  分片：{len(results)} 片 · 失败 {len(summary['failed'])} 片 · "
              f"分片墙钟合计 {summary['wall']} s · 总墙钟 {payload['wall_s']} s")
        verdict = "可发布（check1-42 测试侧与结构侧全过）" if payload["ok"] else "不可发布"
        print(f"  => {verdict}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    sys.exit(main())
