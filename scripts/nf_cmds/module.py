"""CLI 处理器：module 族（自 scripts/nf.py 抽出；按子命令拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import ROOT, _machine_fail


def _module_contract(args) -> int:
    import json as _json
    from core import machine_contract as mctl

    if args.write:
        rows = mctl.apply(ROOT, write=True)
        # `outputs` 行补全（2026-10-01 接线）：同一份契约块里的 outputs 行此前有一条
        # 独立实现（`apply_outputs`：只给「outputs 为空 + 有事件载荷证据」的模块补，
        # 幂等），却**只被单测调用、没有任何用户可达路径**——文档写的
        # `nf module contract --write` 正是「补机读块」。实测当前真仓 changed=0
        # （12 件候选、0 件需改）⇒ 接线不改变今天的产物，只让该能力真正可达。
        outs = mctl.apply_outputs(ROOT, write=True)
        print("== nf module contract --write ==")
        print("  ✓ L0 → L1/L2 retro-fit 完成：%d 件" % len(rows))
        for r in rows:
            print("    %-52s %s" % (r["path"], r["level"]))
        fixed = [r for r in outs if r.get("changed")]
        print("  ✓ outputs 行补全：%d 件（证据取自事件载荷；幂等）" % len(fixed))
        for r in fixed:
            print("    %-52s %s" % (r["path"],
                                    "、".join(r.get("tokens") or []) or "—"))
        return 0
    c_issues, c_warns, c_stats = mctl.scan(ROOT)
    if args.json:
        print(_json.dumps({"kind": "module-contract",
                           "issues": c_issues, "warns": c_warns,
                           "stats": c_stats}, ensure_ascii=False,
                          indent=2, sort_keys=True))
    else:
        print("== nf module contract（机读块覆盖）==")
        print("  仍为 L0（无机读块）：%d 件" % len(c_stats.get("l0_list") or []))
        for i in c_issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in c_warns:
            print("  [WARN] %s" % w)
        if not c_issues and not (c_stats.get("l0_list") or []):
            print("  ✓ 全库模块均有机器契约（L0 = 0）")
    return 1 if c_issues else 0


def _module_types(args) -> int:
    import json as _json
    from core import io_types as iot

    if getattr(args, "harvest", False):
        from core import payload_harvest as ph
        h = ph.apply(ROOT, write=True)
        print("== nf module types --harvest ==")
        print("  正文载荷收割：新增 %d · 收窄 %d · 冲突 %d"
              % (len(h["added"]), len(h["narrowed"]), len(h["conflicts"])))
        for c in h["conflicts"][:5]:
            print("  [WARN] 类型冲突（只报告不改）：%s" % c)
        print("  类型面：%s" % ph.stats(ROOT))
        return 0
    if getattr(args, "backlog", False):
        from core import payload_harvest as ph
        if args.write:
            doc = ph.backlog(ROOT, write=True)
            print("  ✓ 类型积压台账已写入：%d 项 untyped（protocol/type_backlog.json）"
                  % doc["count"])
            return 0
        b_issues, b_stats = ph.verify_backlog(ROOT)
        print("== nf module types --backlog ==")
        print("  不可推断的 untyped：%d 项" % b_stats["untyped"])
        for i in b_issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        return 1 if b_issues else 0
    if args.write:
        rows = iot.apply(ROOT, write=True)
        cov = iot.coverage(ROOT)
        print("== nf module types --write ==")
        print("  ✓ 已补标 %d 件（机读契约模块 %d · 类型覆盖 %.1f%%）"
              % (sum(1 for r in rows if r["changed"]),
                 cov["modules_with_contract"], cov["coverage"]))
        return 0
    t_issues, t_warns, _t = iot.scan(ROOT)
    cov = iot.coverage(ROOT)
    if args.json:
        print(_json.dumps({"kind": "module-types",
                           "issues": t_issues, "warns": t_warns,
                           "stats": cov}, ensure_ascii=False,
                          indent=2, sort_keys=True))
    else:
        print("== nf module types（I/O 类型面）==")
        print("  机读契约模块 %d · L0 未承载 %d · 已标注 %d/%d 字段（%.1f%%）"
              % (cov["modules_with_contract"], cov["l0_modules"],
                 cov["typed_fields"],
                 cov["typed_fields"] + cov["untyped_fields"], cov["coverage"]))
        for i in t_issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in t_warns:
            print("  [WARN] %s" % w)
        if not t_issues:
            print("  ✓ 无可证类型不匹配（untyped 为如实缺口，不判死）")
    return 1 if t_issues else 0


def _module_signature(args) -> int:
    import json as _json
    from core import module_signature as ms

    if args.write:
        rel = ms.write(ROOT)
        print("== nf module signature --write ==")
        print("  ✓ 边界基线已重冻结：%s（%d 模块）"
              % (rel, len(ms.signatures(ROOT))))
        return 0
    sig_issues, sig_warns, sig_stats = ms.verify(ROOT)
    if args.json:
        print(_json.dumps({"kind": "module-signature",
                           "issues": sig_issues, "warns": sig_warns,
                           "stats": sig_stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf module signature（边界冻结）==")
        print("  模块 %d · 已签 %d" % (sig_stats.get("modules", 0),
                                      sig_stats.get("signed", 0)))
        for i in sig_issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for w in sig_warns:
            print("  [WARN] %s" % w)
        if not sig_issues:
            print("  ✓ 全部模块边界与基线一致（改边界须显式重签）")
    return 1 if sig_issues else 0


def _module_verify(args) -> int:
    from core import module_lifecycle as ml

    issues, stats = ml.verify_modules(args.root)
    print("== nf module verify ==")
    print("  统计：模块 %d / active %d / deprecated %d / retired %d"
          % (stats["modules"], stats["active"],
             stats["deprecated"], stats["retired"]))
    if issues:
        for issue in issues:
            print("  [FAIL] %s" % issue, file=sys.stderr)
        return 1
    print("  ✓ 无 deprecated/retired 模块被引用（引用门禁全绿）")
    return 0


def _module_ls(args) -> int:
    import json as _json
    from core import module_lifecycle as ml

    rows = []
    for rel in ml.iter_module_files(args.root):
        txt = ml.read_text(args.root, rel)
        status, _ = ml.get_status(txt)
        if args.status and status != args.status:
            continue
        rows.append((status, rel))
    if args.json:
        print(_json.dumps({
            "kind": "module-ls",
            "status": args.status or None,
            "rows": [{"status": s, "file": f} for s, f in sorted(rows)],
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("== nf module ls ==")
    for status, rel in rows:
        print("  %-10s %s" % (status, rel))
    print("  合计 %d" % len(rows))
    return 0


def _module_file_ops(args) -> int:
    from core import module_lifecycle as ml

    fpath = args.file
    # 形状闸门（2026-10-01）：`nf module status <目录>` 此前落到 open(dir) 抛
    # `[Errno 13] Permission denied: 'docs'`（带指引但**回吐 OS 层裸错误**）——
    # 与 attest/sig/diff 同规，先判形状再读。
    if os.path.exists(fpath) and not os.path.isfile(fpath):
        return _machine_fail(
            args, "目标不是文件：%s（修复指引：file 须是**在场模块 md**；"
                  "`nf module ls` 可枚举现有模块）" % fpath, 1)
    with open(fpath, encoding="utf-8") as fh:
        txt = fh.read()
    before, _ = ml.get_status(txt)
    if args.module_cmd == "status":
        print("== nf module status ==")
        print("  %s → %s" % (fpath, before))
        return 0
    target = "deprecated" if args.module_cmd == "deprecate" else "active"
    if before == target:
        # 重复调用安全（agent 密集调用会重发同一写命令）：已经是目标态就**不谎报流转**。
        print("== nf module %s ==" % args.module_cmd)
        print("  · 已是 %s（无变化；重复调用安全）" % target)
        return 0
    new_txt = ml.set_status(txt, target,
                            reason=getattr(args, "reason", ""),
                            module_file=fpath)
    if new_txt != txt:
        from core import atomic_write      # 就地改模块头：原子写（半截件不留）
        atomic_write.write_text(fpath, new_txt)
    print("== nf module %s ==" % args.module_cmd)
    print("  ✓ 状态流转：%s → %s（%s）" % (before, target, fpath))
    print("  复核：python scripts/nf.py module verify（引用门禁，verify check24 同语义）")
    return 0


def _cmd_module(args) -> int:
    """nf module：模块生命周期（v2.8.0 波B S5）。ls/verify 只读；deprecate/restore 写文件状态位。"""
    try:
        sub = args.module_cmd
        if sub == "contract":
            return _module_contract(args)
        if sub == "types":
            return _module_types(args)
        if sub == "signature":
            return _module_signature(args)
        if sub == "verify":
            return _module_verify(args)
        if sub == "ls":
            return _module_ls(args)
        return _module_file_ops(args)
    except (OSError, ValueError) as exc:
        # 极端渗透 D8：`nf module status NO-SUCH` 此前把裸 `[Errno 2] No such file or directory`
        # 抛给用户（零指引）。按 NF「错误消息即微型文档」纪律给出可操作指引。
        if isinstance(exc, FileNotFoundError):
            print("  ✗ 模块文件不存在：%s" % args.file, file=sys.stderr)
            print("  修复指引：file 须是**在场**模块 md 路径（如 "
                  "04_模块库/通用类/M00_数据槽总线.md，或 community/<包>/modules/<文件>.md）；"
                  "`python scripts/nf.py module ls` 可枚举现有模块", file=sys.stderr)
        else:
            return _machine_fail(
                args, "%s（修复指引：确认该文件含合法状态位，写法见 01 §1.5；"
                      "`nf module ls` 可枚举）" % exc)
        return 1
