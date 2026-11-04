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
  python scripts/release_conclusion.py                # 缺省串行（8 片依次跑，墙钟换正确性）
  python scripts/release_conclusion.py --jobs 8       # 并发：只建议给独立 runner（单机有争用）
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
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: **分区数**与**并发数**是两件事（2026-11-04 实测教训）：
#: - 分区（--shards）默认 8：每个分区是**独立进程**（各自 import 一套模块），因此分区并集 = 全量
#:   且互不污染。单片跑全量（--shards 1）会变成「所有测试共享一个进程」，su^ite 级顺序敏感性
#:   全部暴露（实测：单片全量出现 8 处 red，同内容 8 片独立进程全绿）。
#: - 并发（--jobs）默认 1 = 顺序执行：分片是为「CI 矩阵各跑一片（不同机器）」设计的；同一台机
#:   并发多片会在守护端口/临时目录/计时判据上互相干扰（实测 8 片并发有假红）。
DEFAULT_SHARDS = 8
DEFAULT_JOBS = 1
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


def payload_drift_guard(manifest: dict | None, head: str) -> str:
    """npm payload 与 HEAD 的耦合闸门 → 拒绝原因（空串 = 放行）。

    为什么必须前置（2026-11-04 实测踩了三次）：npm 门槛要求 payload 清单里的 source_commit
    == HEAD，而 payload 是**忽略文件**——所以「工作树干净」并不代表「payload 是最新的」。
    不前置的话，要跑满 8 片（约 30 分钟）才在最后一处看见「payload 与 HEAD 不一致」，
    而且报出来的只是某个分片的一条红。
    """
    if not isinstance(manifest, dict):
        return ""                        # payload 不在场：忽略面（发布前才 stage）
    commit = str(manifest.get("source_commit") or "")
    if not commit or not head:
        return ""
    if head.startswith(commit) or commit.startswith(head):
        return ""
    return (f"npm payload 与 HEAD 不一致（清单 {commit[:12]} ≠ HEAD {head[:12]}）"
            f"（{GUIDE}在 packaging/npm 里跑 node tools/stage-payload.mjs 重新暂存——"
            "它只写忽略文件，不产生提交；暂存后再跑本件）")


def read_payload_manifest(path) -> dict | None:
    """读 payload 清单 → dict 或 None（坏件也当不在场：这条只是前置提示，不是判据本体）。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        doc = json.loads(raw)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def aggregate(results: list[dict]) -> dict:
    """分片结果汇总 → {ok, total, failed, wall}（纯函数，便于单测）。"""
    failed = [r for r in results if int(r.get("rc") or 0) != 0]
    return {"ok": bool(results) and not failed,
            "total": len(results),
            "failed": [{"shard": r.get("shard"), "rc": r.get("rc")} for r in failed],
            "wall": round(sum(float(r.get("wall") or 0.0) for r in results), 1)}


def _run(argv: list[str], timeout: float) -> dict:
    """跑**本仓固定命令** → {code, out, err}。

    统一走 core 的受控进程原子：本件不再自己起 subprocess（那是 SAST 面要逐处标注的东西，
    而受控原子已经把「argv 列表 / 无 shell / 超时即回收」写死在一处）。
    """
    src = str(ROOT / "desktop" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from core.atoms import proc as proc_atom  # 局部导入：模块级只留纯逻辑
    return proc_atom.run_capture(argv, cwd=str(ROOT), timeout=timeout)


def _git_status() -> list[str]:
    proc = _run(["git", "status", "--porcelain"], 120)
    if proc.get("code") is None:
        # git 不可用（非 git 检出/权限）：按「无脏树信息」处理，不阻断——判据只做门禁不放行
        return []
    return porcelain_lines(proc.get("out") or "")


def _step_checks_only(verbose: bool) -> tuple[int, float]:
    t0 = time.perf_counter()
    if verbose:
        print("[1/2] bash verify.sh --checks-only …", flush=True)
    proc = _run(["bash", "verify.sh", "--checks-only"], 3600)
    out = (proc.get("out") or "") + (proc.get("err") or "")
    tail = [ln for ln in out.splitlines() if ln.strip()][-1:]
    rc = proc.get("code")
    if verbose:
        print(f"  => rc={rc} · {tail[0] if tail else '（无输出）'}", flush=True)
    return (1 if rc is None else int(rc)), time.perf_counter() - t0


def _shard_one(index: int, total: int) -> dict:
    t0 = time.perf_counter()
    argv = [sys.executable, "scripts/verify_tests.py", "--shard",
            f"{index}/{total}", "--json"]
    proc = _run(argv, 3600)
    rc = proc.get("code")
    row = {"shard": f"{index}/{total}", "rc": 1 if rc is None else int(rc),
           "wall": round(time.perf_counter() - t0, 1)}
    if row["rc"] != 0:
        # 失败必须自带证据：只报「某片红了」等于把诊断成本丢给下一个人（实测教训：
        # 全量串行红了一次却因为没留分片输出，只能整轮重跑取证）。
        out = (proc.get("out") or "") + (proc.get("err") or "")
        row["tail"] = [ln for ln in out.splitlines() if ln.strip()][-40:]
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="release_conclusion",
                                 description="发布结论一键复跑（干净树 → checks-only → 分片）")
    ap.add_argument("--shards", type=int, default=DEFAULT_SHARDS,
                    help=f"分区数（缺省 {DEFAULT_SHARDS}；每片独立进程，并集 == 全量）")
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                    help=f"并发数（缺省 {DEFAULT_JOBS} = 顺序跑；>1 只建议给独立 runner）")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="允许在脏树上跑（默认拒绝：脏树会产生与输入无关的假红）")
    ap.add_argument("--skip-checks", action="store_true", help="跳过 checks-only 步骤")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    ap.add_argument("--json", action="store_true", help="机读汇总")
    args = ap.parse_args(argv)

    shards = max(1, min(int(args.shards), 32))
    concurrency = max(1, min(int(args.jobs), shards))
    plan = {"root": str(ROOT), "shards": shards, "concurrency": concurrency,
            "checks_only": not args.skip_checks,
            "steps": ["git status --porcelain",
                      "packaging/npm/payload/payload-manifest.json 的 source_commit == HEAD",
                      "bash verify.sh --checks-only"]
                     + [f"python scripts/verify_tests.py --shard {i}/{shards}"
                        for i in range(shards)]}

    dirty = _git_status()
    blocked = dirty_guard(dirty, args.allow_dirty)
    head = (_run(["git", "rev-parse", "HEAD"], 60).get("out") or "").strip()
    manifest = read_payload_manifest(ROOT / "packaging" / "npm" / "payload"
                                     / "payload-manifest.json")
    payload_blocked = payload_drift_guard(manifest, head)
    if args.dry_run:
        payload = {"schema": "nf-release-conclusion/1", "dry_run": True, "plan": plan,
                   "dirty": dirty, "blocked": blocked, "payload_blocked": payload_blocked}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not (blocked or payload_blocked) else 2
    if blocked:
        print(f"  ✗ {blocked}", file=sys.stderr)
        return 2
    if payload_blocked:
        print(f"  ✗ {payload_blocked}", file=sys.stderr)
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
        print(f"[2/2] 分片 ×{shards}（并发 {concurrency}）…", flush=True)
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_shard_one, i, shards) for i in range(shards)]
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
        failed_rows = [r for r in results if r["rc"] != 0]
        if failed_rows:
            print("== 失败分片输出（末 40 行）==")
            for row in sorted(failed_rows, key=lambda r: r["shard"]):
                print(f"-- 分片 {row['shard']}（rc={row['rc']}）--")
                for line in row.get("tail") or []:
                    print(f"  {line}")
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
