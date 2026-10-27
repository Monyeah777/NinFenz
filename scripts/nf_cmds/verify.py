"""CLI 处理器：verify（门禁单进程引擎入口；自 scripts/nf.py 抽出，按职责拆小函数）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import _machine_fail


def _verify_trust_gate(args, ge, rt):
    """H1（2026-10-22 安全审计）：执行前的信任门。返回 rc 或 None。"""
    import json as _json

    if getattr(args, "trust_repo", False):
        print("WARN: --trust-repo 已启用：将执行目标仓库自带的门禁脚本（含内嵌 Python，"
              "CWE-94 面），风险自担", file=sys.stderr)
    _trusted, _why = ((True, "显式 --trust-repo") if getattr(args, "trust_repo", False)
                      else rt.trust_status(str(ge.ROOT)))
    if _trusted:
        return None
    _msg = rt.refusal_message(str(ge.ROOT), _why)
    if args.json:
        print(_json.dumps({"kind": "nf-verify", "schema": "nf-verify/1", "ok": False,
                           "fails": 1, "checks": [], "pending": [], "complete": False,
                           "gate_of_record": "bash verify.sh",
                           "error": {"code": "untrusted_repo", "message": _why}},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf verify（门禁单进程引擎 · 已因信任门拒绝执行）==")
    print(_msg, file=sys.stderr)
    return 2


def _verify_parallel(args, ge, rt, only) -> int:
    import json as _json

    # **并行**：每条 check 在独立子进程里跑 `nf verify --only N --json`（判据一字不改），
    # 再按 check 号排序合并。逐字节一致的守门判据见 `test_verify_parallel_checks`。
    from core import verify_checks as _vc
    _jobs = int(getattr(args, "jobs", 0) or 0)
    nums = sorted(ge.REGISTRY)
    _saved_trust = os.environ.get(rt.ENV_TRUST)
    if getattr(args, "trust_repo", False):
        os.environ[rt.ENV_TRUST] = "1"
    try:
        payloads, broken = _vc.run_checks_parallel(ge.ROOT, nums, jobs=_jobs)
    finally:
        if _saved_trust is None:
            os.environ.pop(rt.ENV_TRUST, None)
        else:
            os.environ[rt.ENV_TRUST] = _saved_trust
    if broken:
        print("并行子 check 不可信：%s（修复指引：去掉 --jobs 用串行复现）"
              % ",".join(str(b) for b in broken), file=sys.stderr)
        return 2
    fails = sum(1 for c in payloads
                for s in (c.get("verdicts") or []) if s == "FAIL")
    pending = sorted(ge.PENDING)
    if args.json:
        print(_json.dumps({
            "kind": "nf-verify", "schema": "nf-verify/1",
            "ok": fails == 0, "fails": fails, "checks": payloads,
            "pending": [int(n) for n in pending],
            "complete": not pending, "gate_of_record": "bash verify.sh",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if fails else 0
    print("== nf verify（门禁单进程引擎 · 判据与 verify.sh 逐字等价）==")
    for c in payloads:
        for status, msg in zip(c.get("verdicts") or [], c.get("messages") or []):
            print("  [%s] %s" % (status, msg))
    print("  已迁入 %d 条 · FAIL %d" % (len(payloads), fails))
    if pending:
        print("  ⚠ 未迁入 %d 条（仍在 verify.sh 里，**未在本次结论内**）：%s"
              % (len(pending), " ".join(str(n) for n in pending)))
        print("  ⚠ 本条结论**不等于全量门禁**——全量请跑：bash verify.sh")
    return 1 if fails else 0


def _verify_serial(args, ge, rt, only, memo) -> int:
    import json as _json

    _saved_trust = os.environ.get(rt.ENV_TRUST)
    if getattr(args, "trust_repo", False):
        os.environ[rt.ENV_TRUST] = "1"
    try:
        verdicts = ge.run_checks(
            ge.ROOT, only, memo, use_cache=bool(getattr(args, "cached", False)))
    finally:
        if _saved_trust is None:
            os.environ.pop(rt.ENV_TRUST, None)
        else:
            os.environ[rt.ENV_TRUST] = _saved_trust

    fails = sum(v.fails for v in verdicts)
    pending = sorted(set(ge.PENDING) - (set(only) if only else set()))

    # 退出码**只看 FAIL**，与门禁（`verify.sh` 只按 FAIL 判死）同口径。
    # 「未迁入」是**覆盖面**问题，不是判据失败——把它算进退出码会有两个坏后果：
    #   ① 语义错位：引擎会把「还有 19 条没搬进来」报成「门禁红」；
    #   ② 实测连带故障：响应缓存只收退出码 0 的响应 ⇒ `nf verify` 永远不入缓存
    #      （实测 5 miss / 0 hit，热跑仍是 72 s）。
    # 故未迁入只在人读面**大声声明**（并在机器面给 pending 列表），不动退出码。

    if args.json:
        print(_json.dumps({
            "kind": "nf-verify",
            "schema": "nf-verify/1",
            "ok": fails == 0,
            "fails": fails,
            "checks": [{"check": int(v.name.replace("check", "")), "status": v.status,
                        "verdicts": [s for s, _ in v.verdicts],
                        # `messages` 让机器面**自足**：并行子进程跑 `--only N --json` 之后，
                        # 人读面能按同一批数据重放出**逐字相同**的文案（否则并行态只剩
                        # PASS/FAIL，文案无处可取）。顺序与 `verdicts` 一一对应。
                        "messages": [m for _, m in v.verdicts]}
                       for v in verdicts],
            "pending": [int(n) for n in pending],
            "complete": not pending,
            "gate_of_record": "bash verify.sh",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if fails else 0

    print("== nf verify（门禁单进程引擎 · 判据与 verify.sh 逐字等价）==")
    for v in verdicts:
        for status, msg in v.verdicts:
            print("  [%s] %s" % (status, msg))
    print("  已迁入 %d 条 · FAIL %d" % (len(verdicts), fails))
    if pending:
        print("  ⚠ 未迁入 %d 条（仍在 verify.sh 里，**未在本次结论内**）：%s"
              % (len(pending), " ".join(str(n) for n in pending)))
        print("  ⚠ 本条结论**不等于全量门禁**——全量请跑：bash verify.sh")
    return 1 if fails else 0


def run(args) -> int:
    """nf verify：门禁单进程引擎入口（已迁入的 check 与 verify.sh 判据逐字等价）。

    **纪律**：本命令不重写任何判据——执行体是 `core.gate_engine`，它对已迁入的 check
    要么委托既有 `core.*`，要么在进程内跑 verify.sh 的 heredoc 原文；未迁入的如实报
    「未迁入」，**不假装绿**。全量门禁的权威入口仍是 `bash verify.sh`。
    """
    from core import gate_engine as ge
    from core import repo_trust as _rt

    rc = _verify_trust_gate(args, ge, _rt)
    if rc is not None:
        return rc

    ge.build_registry()
    only = [int(x) for x in str(args.only).split(",") if x.strip()] if args.only else None
    if only:
        unknown = sorted(set(only) - set(ge.REGISTRY))
        if unknown:
            return _machine_fail(
                args,
                "check %s 尚未迁入引擎（现已迁入：%s）——请用 `bash verify.sh` 跑全量"
                % (",".join(str(u) for u in unknown),
                   ",".join(str(n) for n in sorted(ge.REGISTRY))), 2)

    # 确定性输出：耗时是**不确定性面**，默认不进输出。
    # 实测教训（test_daemon_parity）：直跑与守护的耗时必然不同，带上它两边就不逐字节一致。
    # 故本命令**自己**把开关置上（而不是依赖守护侧注入）——直跑与守护走同一条代码路径，
    # 判据只有一个，避免「两条路径各自设一次」再漂移（实测踩过：只设守护侧 ⇒ 仍差 28 字节）。
    os.environ["NF_VERIFY_QUIET_TIME"] = "1"
    memo = ge.Memo() if args.memo else None
    _jobs = int(getattr(args, "jobs", 0) or 0)
    if _jobs > 1 and not only:
        return _verify_parallel(args, ge, _rt, only)
    return _verify_serial(args, ge, _rt, only, memo)
