"""CLI 处理器：integrate 族（自 scripts/nf.py 抽出；行为逐字保留，由 nf.py re-export）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _file_shape_issue, _load_runs, _machine_fail,
                            _rel_out)

def _cmd_toolface(args):
    """nf toolface：浏览模块工具面（machine_contract.tool_face）。"""
    import json as _json
    from core import tool_face as tf

    issues, stats = tf.scan(ROOT)
    if args.json:
        print(_json.dumps({"kind": "toolface", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf toolface（模块工具面 · AI 裁量不入门禁）==")
        print("  模块 %d · 条目 %d · 候选工具链接 %d"
              % (stats["modules"], stats["entries"], stats["candidates"]))
        for f in stats["faces"]:
            print("  · %s（%s · %d 条目）"
                  % (f["module"], f["source"], f["entries"]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0

def _cmd_transparency(args):
    """nf transparency：透明日志（哈希链）校验 / 落盘。"""
    from core import transparency_log as tl
    if args.write:
        rel = tl.write(ROOT)
        print("  ✓ 已写入：%s（链头 %s…）" % (rel, tl.build(ROOT)["head"][:16]))
    issues, stats = tl.verify(ROOT)
    if args.json:
        import json as _json
        print(_json.dumps({"kind": "transparency", "issues": issues,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 链自洽（%d 节 · 链头 %s… · 在盘生成物一致）"
                  % (stats["links"], stats["head"]))
        print("  边界：%s" % tl.BOUNDARY)
    return 1 if issues else 0

def _cmd_locales(args):
    """nf locales：语言面自检；--write 重签文档译件的源件摘要。"""
    import json as _json
    from core import locales as lc

    if getattr(args, "write", False):
        res = lc.stamp(ROOT, write=True)
        if not res.get("ok"):
            print("  ✗ %s" % "；".join(res.get("issues") or []), file=sys.stderr)
            return 2
        print("  ✓ 已重签 %d 条文档译件的源件摘要" % len(res["stamped"]))
        return 0
    issues, stats = lc.check(ROOT)
    if getattr(args, "json", False):
        print(_json.dumps({"schema": "nf-locales-report/1", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if issues else 0
    print("== nf locales（语言面）==")
    print("  语言：%s · 文档译件 %d 件"
          % ("、".join(stats.get("locales", [])), stats.get("translations", 0)))
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0

def _cmd_events(args):
    """nf events：全仓事件背书核对。"""
    from core import registry_cross as rx
    import json as _json
    issues, warns, stats = rx.scan(ROOT)
    if args.json:
        print(_json.dumps({"kind": "events", "issues": issues, "warns": warns,
                           "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf events（全仓事件背书）==")
        print("  事件 %d · 跨包 %d · 无发布方挂账 %d"
              % (stats["events"], len(stats["cross_pkg"]),
                 len(warns) - len(stats["cross_pkg"])))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for wmsg in warns[:10]:
            print("  [note] %s" % wmsg)
        if not issues:
            print("  ✓ 每个被订阅的事件都有发布方（外部通道已显式挂账）")
    return 1 if issues else 0

def _cmd_driver(args):
    """nf driver：指令档机器面路由解析/自检。"""
    from core import driver
    import json as _json
    issues, warns, stats = driver.scan(ROOT)
    if args.workflow:
        r = driver.resolve(ROOT, args.workflow)
        if args.json:
            print(_json.dumps({"kind": "driver-resolve", "resolve": r,
                               "issues": issues, "warns": warns},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf driver %s ==" % args.workflow)
            print("  路径：%s" % ("MCP（机器面）" if r["mode"] == "mcp" else r["mode"]))
            if r.get("prompt"):
                print("  提示：%s" % r["prompt"])
            if r.get("tools"):
                print("  工具：%s" % "、".join(r["tools"]))
            print("  文本 fallback：%s" % r.get("fallback", "-"))
            print("  派发失败：%s" % r.get("on_dispatch_failure", "-"))
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
        return 1 if issues else 0
    if args.json:
        doc = driver.load(ROOT)
        print(_json.dumps({"kind": "driver", "driver": doc, "issues": issues,
                           "warns": warns, "stats": stats},
                          ensure_ascii=False, indent=2,
                          sort_keys=True))
    else:
        doc = driver.load(ROOT)
        print("== nf driver（指令档机器面路由）==")
        for name, wf in sorted((doc.get("workflows") or {}).items()):
            print("  %-12s MCP：%-28s fallback：%s"
                  % (name, "、".join(wf.get("mcp_tools") or []) or "-",
                     wf.get("fallback", "-")))
        for w in warns:
            print("  [note] %s" % w)
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
        if not issues:
            print("  ✓ 工作流映射/工具名/fallback/文档声明块全部一致（fail-closed 已声明）")
    return 1 if issues else 0

def _cmd_state_front(args):
    """nf state-front：条件先行排布（确定性；不调模型）。"""
    from core import state_front as sf
    import json as _json
    from pathlib import Path as _Path
    p = args.path if os.path.isabs(args.path) else os.path.join(ROOT, args.path)
    if not os.path.isfile(p):
        # 修复前：裸 OSError（还带**绝对路径**）直接回显——既无指引又漏本机路径。
        return _machine_fail(
            args, "目标不存在：%s（修复指引：给出在场文件路径——相对仓库根或绝对皆可；"
                  "本命令只做确定性排布，不调模型）" % args.path)
    try:
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return _machine_fail(args, str(exc), 1)
    if args.ab:
        man = sf.ab_manifest(text)
        if args.json:
            print(_json.dumps({"kind": "state-front-ab", **man},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf state-front --ab（三刺激件清单 · 不调模型）==")
            for k in ("front", "back", "none"):
                v = man[k]
                print("  %-6s chars %6d · sha256 %s · 状态块前置=%s"
                      % (k, v["chars"], v["sha256"][:16], v["state_front"]))
        return 0
    if args.check:
        issues = sf.check_order(text)
        if args.json:
            print(_json.dumps({"kind": "state-front-check", "issues": issues},
                              ensure_ascii=False, indent=2))
        else:
            print("== nf state-front --check（%s）==" % args.path)
            for i in issues:
                print("  [FAIL] %s" % i)
            if not issues:
                print("  ✓ 状态块已前置（条件先行）")
        return 1 if issues else 0
    out = sf.reorder(text, args.mode)
    if args.out:
        op = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
        _Path(op).parent.mkdir(parents=True, exist_ok=True)
        from core import atomic_write          # 重排产物：原子写
        atomic_write.write_text(op, out)
    if args.json:
        print(_json.dumps({"kind": "state-front", "mode": args.mode,
                           "chars": len(out),
                           "state_front": not sf.check_order(out)}, ensure_ascii=False))
    else:
        print("== nf state-front（%s → %s）==" % (args.path, args.mode))
        print("  输出长度 %d 字符 · 状态块前置=%s"
              % (len(out), not sf.check_order(out)))
        if args.out:
            print("  已写入：%s" % args.out)
    return 0

def _cmd_interop(args):
    """nf interop：互操作导出面（纯派生；--check 走门禁）。"""
    from core import interop_export as ie
    if args.list:
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "interop-kinds",
                               "rows": [{"kind": k, "label": v[1]}
                                        for k, v in ie.KINDS.items()]},
                              ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        for kind, (fn, label) in ie.KINDS.items():
            print("  %-9s %-38s 消费者：外部标准工具链" % (kind, label))
        return 0
    if args.check:
        issues, stats = ie.verify(ROOT)
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "interop-verify", "issues": issues,
                               "stats": stats},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for i in issues:
                print("  [FAIL] %s" % i, file=sys.stderr)
            if not issues:
                print("  ✓ 导出面一致（%s）" % ie.summary(stats))
        return 1 if issues else 0
    if args.all:
        from core import atomic_write      # 入仓面原子落盘（见下）
        # 落点同样按**仓库根**解析（缺省就是仓内 `results/interop`；给了相对路径时不再跟 cwd 跑）
        out_dir = (_rel_out(args.out) if args.out
                   else os.path.join(ROOT, "results", "interop"))
        os.makedirs(out_dir, exist_ok=True)
        written = []
        try:
            for kind in ie.KINDS:
                dest = os.path.join(out_dir, "%s.json" % kind)
                # 原子写（2026-09-30）：入仓面（check33 逐步字节比对）——半截产物会让
                # 「入仓面 == 实时派生」当场红；顺带收敛 Windows 偶发 EINVAL(22)。
                atomic_write.write_bytes(dest, ie.render(kind, ROOT))
                written.append(dest)
        except ValueError as exc:      # 源件在场但坏 ⇒ 干净失败（不是「空面照写」）
            return _machine_fail(args, str(exc), 1)
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "interop-write", "ok": True, "out": out_dir,
                               "written": written,
                               "note": "入仓面须与实时派生逐字节一致（由 verify check33 断言；"
                                       "改声明件后重跑本命令）"},
                              ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        for dest in written:
            print("written: %s" % dest)
        print("  （入仓面须与实时派生逐字节一致——由 verify check33 断言；"
              "改声明件后重跑本命令）")
        return 0
    try:
        blob = ie.render(args.kind, ROOT)
    except (OSError, ValueError) as exc:   # 源件在场但坏 ⇒ 干净失败（与 --all 同规）
        return _machine_fail(args, str(exc), 1)
    if args.out:
        # 形状闸门（2026-09-30 二扫）：单 kind 的 `--out` 收**文件**；给目录此前落到
        # `open` 抛 IsADirectoryError ⇒ 冒到 CLI 兜底报「内部错误 + Errno」（实测）。
        if os.path.isdir(args.out):
            return _machine_fail(
                args, "--out 落点是目录：%s（修复指引：单 kind 导出给**文件**路径，如 "
                      "out/openapi.json；要一次落盘全部 kind 用 "
                      "`nf interop --all --out <目录>`）" % args.out, 1)
        try:
            from core import atomic_write
            # 口径统一（2026-10-01）：相对 `--out` 按**仓库根**解析（与其余面的 `_rel_out` 同）。
            # 实测此前这里直接吃 `args.out` ⇒ 从任意 cwd 跑都落到 cwd，而同名旗标在其它面是仓根。
            atomic_write.write_bytes(_rel_out(args.out), blob)   # 原子写：半截导出件不留
        except OSError as exc:
            return _machine_fail(args, "写导出失败：%s（修复指引：给可写文件路径）"
                                 % exc, 1)
        print("written: %s（%d 字节，纯派生，勿手改）" % (args.out, len(blob)))
    else:
        sys.stdout.write(blob.decode("utf-8"))
    return 0

def _cmd_render(args) -> int:
    """nf render <pkg_dir> --fmt：协议多出口渲染（A3：protocol.yaml → rules）。"""
    from pathlib import Path
    from core.rules_render import render_protocol

    pkg_dir = Path(args.pkg_dir)
    if not (pkg_dir / "protocol.yaml").is_file():
        # 全命令面系统扫（2026-09-30）唯一余项：修复前这里漏成「内部错误：No such file …」
        print("  ✗ 不是协议包目录：%s（缺 protocol.yaml）"
              "（修复指引：给出含 protocol.yaml 的包目录，如 `community/技术文档域包`；"
              "`nf market --list` 可枚举已登记包）" % pkg_dir, file=sys.stderr)
        return 2
    # 形状闸门（2026-10-01）：`--dest <文件>` 此前落到 makedirs 抛 `[WinError 183]`，
    # 冒到 CLI 兜底报「内部错误」并回吐机器绝对路径（与 `--out`/`--store` 同类）。
    if args.dest and os.path.exists(args.dest) and not os.path.isdir(args.dest):
        return _machine_fail(
            args, "--dest 落点是文件：%s（修复指引：`--dest` 给**目录**（相对仓库根或绝对皆可，"
                  "不存在会自动建）；产物文件名由本命令决定）" % args.dest, 2)
    try:
        txt = render_protocol(args.pkg_dir, args.fmt)
    except (OSError, ValueError) as exc:
        print("  ✗ 渲染失败：%s（修复指引：核对包内 protocol.yaml 是否合 01 §6.1 Schema）" % exc,
              file=sys.stderr)
        return 1
    out_name = {"agents": "AGENTS.md", "claude": "CLAUDE.md", "skill": "SKILL.md"}[args.fmt]
    dest = Path(args.dest) if args.dest else Path.cwd()
    dest.mkdir(parents=True, exist_ok=True)
    out_path = dest / out_name
    from core import atomic_write          # 交付件：原子写（2026-10-01 全量普查补齐）
    atomic_write.write_text(out_path, txt)
    pkg_basename = os.path.basename(args.pkg_dir.rstrip("/\\"))
    print(f"== nf render {pkg_basename} → {args.fmt} ==")
    print(f"  ✓ {out_path}")
    return 0

def _cmd_bench(args):
    """nf bench：执行结果跑分（run / compare / report）。"""
    from core import bench
    from pathlib import Path
    import json as _json
    sub = getattr(args, "bench_cmd", None) or "run"
    if sub == "run":
        case_arg = args.case
        # 口径统一（2026-10-01）：相对路径按**仓库根**解析（与 `_rel_out` / `_rel_to_root` 同）。
        # 此前用 `os.path.abspath(case_arg)` ⇒ 按进程 cwd 解析，从 `desktop/` 里跑
        # `--case desktop/tests/…` 必判「用例件不存在」（夹具明明在仓内）。
        case_abs = os.path.abspath(case_arg if os.path.isabs(case_arg)
                                   else os.path.join(ROOT, case_arg))
        if os.path.isdir(case_abs):
            case_abs = os.path.join(case_abs, "case.json")
        case_path = os.path.relpath(case_abs, ROOT)
        # 输入校验前置（2026-09-30）：`--case` 给目录但目录里没有 `case.json` 时，此前
        # `load_case` 直接抛 OSError 冒到 CLI 兜底——报成「内部错误」并回吐机器绝对路径。
        # 形状闸门（2026-09-30 二扫）：**文件当目录用**也走这条——`--case README.md` 此前
        # 过了 is_file 检查，到 `load_case` 才抛 JSON 解析错误（无指引）。夹具件名恒为
        # `case.json`（docs/bench.md 与 fixtures 皆然），故按「目录含 case.json，或直接给
        # 该 case.json」收，其余一律干净拒。
        case_p = Path(ROOT, case_path)
        if not (case_p.is_file() and case_p.name == "case.json"):
            return _machine_fail(
                args, "用例件不存在：%s（修复指引：`--case` 给**含 case.json 的夹具目录**，"
                      "如 desktop/tests/fixtures/benchmark/suite/p02-campus-emotion；"
                      "也可直接给该 case.json 的路径；`nf bench report <runs.json>` "
                      "可先看已有跑次）" % case_path, 1)
        try:
            # 形状闸门（2026-09-30 同族扫）：`--artifact <目录>` 此前落到读盘抛裸 Errno。
            _ai = _file_shape_issue(
                args.artifact, "--artifact",
                "修复指引：给被评产物的 md **文件**路径（缺省 = 用例自带的 "
                "default_artifact）")
            if _ai:
                return _machine_fail(args, _ai, 1)
            artifact = args.artifact or bench.load_case(Path(ROOT, case_path))["default_artifact"]
            run = bench.evaluate(ROOT, case_path, artifact, model=args.model)
        except (OSError, ValueError, KeyError) as exc:
            return _machine_fail(args, str(exc), 1)
        if args.out:
            # 形状闸门 + 兜底（2026-09-30 二扫）：`--out <目录>` 此前落到 `open` 抛
            # IsADirectoryError，而这段写在 try 之外 ⇒ 一路冒到 CLI 兜底报「内部错误：
            # [Errno 13] Permission denied: '<作者机绝对路径>'」。
            outp = _rel_out(args.out)
            if os.path.isdir(outp):
                return _machine_fail(
                    args, "--out 落点是目录：%s（修复指引：给**文件**路径，如 "
                          "runs/<名>.json）" % args.out, 1)
            try:
                from core import atomic_write  # 跑分存档：原子写
                atomic_write.write_text(outp, _json.dumps(
                    run, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            except OSError as exc:
                return _machine_fail(args, "写跑分失败：%s（修复指引：给可写文件路径）"
                                     % exc, 1)
        if args.json:
            print(_json.dumps({"kind": "bench-run", **run},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf bench run：%s ==" % run["case"])
            print("  产物 %s（%s）· 模型 %s" % (run["artifact"],
                                              run["artifact_digest"][:12],
                                              run["model"] or "-"))
            for k, v in sorted(run["scores"].items()):
                print("  %-14s %.4f" % (k, v))
            print("  总分 %.2f（下限 %.0f）→ %s" % (run["total"], run["floor"],
                                                   run["verdict"]))
            for i in run["detail"]["issues"][:4]:
                print("    · %s" % i[:110])
        return 0 if run["verdict"] != "fail" else 1
    try:
        runs = _load_runs(args.runs)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc), 1)
    if sub == "compare":
        doc = bench.compare(runs)
        if args.json:
            print(_json.dumps({"kind": "bench-compare", **doc},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf bench compare（%d 跑）==" % doc["runs"])
            for r in doc["ranking"]:
                print("  %-14s %-16s %6s %s" % (r["run"], r["model"] or "-",
                                                r["total"], r["verdict"]))
            for k, v in sorted(doc["dims"].items()):
                print("    · %-14s 均值 %.4f 极差 %.4f" % (k, v["mean"], v["spread"]))
            if doc["regressions_vs_best"]:
                print("  相对最佳回落 %d 项（前 3）：" % len(doc["regressions_vs_best"]))
                for g in doc["regressions_vs_best"][:3]:
                    print("    · %s %s %.4f→%.4f" % (g["run"], g["dim"], g["from"], g["to"]))
        return 0
    md = bench.report_markdown(bench.compare(runs))
    print(md if not args.json else _json.dumps({"kind": "bench-report",
                                                "markdown": md},
                                               ensure_ascii=False, indent=2))
    return 0
