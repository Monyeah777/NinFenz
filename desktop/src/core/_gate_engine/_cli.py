"""core.gate_engine 私有实现分片：命令行/输出面（parser、信任开关、机器/人读输出）。

只经 core.gate_engine 门面导入；本文件不含判据逻辑，只做编排与呈现。
"""
from __future__ import annotations

import argparse
import os
from typing import Any

from core import repo_trust

from ._part1 import PENDING, Verdict


def _parser() -> argparse.ArgumentParser:
    """命令行面（单进程引擎）。"""
    ap = argparse.ArgumentParser(description="门禁单进程引擎（骨架）")
    ap.add_argument("--only", default="", help="逗号分隔的 check 号（默认全部已迁入）")
    ap.add_argument("--memo", action="store_true", help="打开内容寻址 memo（默认关）")
    ap.add_argument("--json", action="store_true", help="机器面")
    ap.add_argument("--repeat", type=int, default=1, help="连跑 N 遍（看 memo 收益）")
    ap.add_argument("--trust-repo", dest="trust_repo", action="store_true",
                    help="显式信任目标仓库（H1）：允许执行其 verify.sh 内嵌代码；外来仓库默认拒绝")
    ap.add_argument("--quiet-time", action="store_true",
                    help="输出里不带墙钟耗时（**确定性输出**用；见下）")
    return ap


def _quiet_flags(a) -> bool:
    """静默判定（--quiet-time 或环境变量；环境变量同时回写 args）。

    不确定性面**默认不进输出**（2026-10-15 实测教训）：`nf verify` 曾被
    test_daemon_parity 抓到「直跑 vs 守护」输出逐字节不同（3480 vs 3478 字节），
    根因就是我在人读面里打了墙钟耗时——而守护与直跑的耗时必然不同。
    机器可比面的纪律是「同输入同字节」，故耗时只在显式要（--repeat>1）或在
    人读面且未被要求静默时才出现。
    """
    quiet = a.quiet_time or os.environ.get("NF_VERIFY_QUIET_TIME") == "1"
    if os.environ.get("NF_VERIFY_QUIET_TIME") == "1":
        a.quiet_time = True
    return quiet


def _only_ids(only_text: str):
    """--only 文本 → check 号列表（空串 → None = 全部已迁入）。"""
    return [int(x) for x in only_text.split(",") if x.strip()] if only_text else None


def _apply_trust_env(trust_repo: bool):
    """H1：只在跑 check 区间内置信任开关；返回原值供还原。

    H1 修复（2026-11-04 实测）：--trust-repo 此前直接写进程级 NF_TRUST_REPO=1 且**从不还原**
    ——同进程里后续任何一次信任门判定都会被这条残留放行（信任门被环境泄漏绕过；分片实测
    当场抓到：一个先跑过 --trust-repo 的用例让后面的「拒绝不可信仓库」判据失效）。
    """
    saved = os.environ.get(repo_trust.ENV_TRUST)
    if trust_repo:
        os.environ[repo_trust.ENV_TRUST] = "1"
    return saved


def _restore_trust_env(saved) -> None:
    """按原值还原信任开关（出区间即还原，不留环境泄漏）。"""
    if saved is None:
        os.environ.pop(repo_trust.ENV_TRUST, None)
    else:
        os.environ[repo_trust.ENV_TRUST] = saved


def _json_payload(allv: list[Verdict], quiet: bool, wall: float,
                  m: Any) -> dict[str, Any]:
    """机器面 payload（耗时/ memo 只在非静默时进输出）。"""
    payload: dict[str, Any] = {
        "checks": [{"name": v.name, "status": v.status, "cached": v.cached,
                    "fails": v.fails, "warns": v.warns} for v in allv],
        "pending": len(PENDING),
    }
    if not quiet:
        payload["wall_seconds"] = round(wall, 4)
        payload["memo"] = None if m is None else {"hits": m.hits, "misses": m.misses}
    return payload


def _print_summary(allv: list[Verdict], pf: int, wall: float, a,
                   m: Any, quiet: bool) -> None:
    """人读面汇总（静默时只打确定性结果行）。"""
    print("=" * 50)
    if quiet:
        print("引擎结果：已迁入 %d 条 / 未迁入 %d 条；FAIL=%d"
              % (len(allv), len(PENDING), pf))
        return
    print("引擎结果：已迁入 %d 条 / 未迁入 %d 条；FAIL=%d WARN=%d"
          % (len(allv), len(PENDING), pf, sum(v.warns for v in allv)))
    print("墙钟 %.3f s（repeat=%d%s）"
          % (wall, a.repeat, "" if m is None else
             "，memo 命中 %d / 未命中 %d" % (m.hits, m.misses)))
    for v in sorted(allv, key=lambda x: -x.seconds)[:5]:
        print("  最慢：%-10s %8.1f ms%s" % (v.name, v.seconds * 1000,
                                          "（memo）" if v.cached else ""))
